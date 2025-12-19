from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketState
import json
import time
import asyncio
import numpy as np
from meeting_mind.app.services.asr_engine import asr_engine
from meeting_mind.app.schemas.protocol import HandshakeMessage, RecognitionResult

import wave
import os
import datetime
from meeting_mind.app.services.session_mgr import session_manager
from meeting_mind.app.services.cloud_asr import CloudASRHandler
from meeting_mind.app.core.logger import logger

router = APIRouter()


@router.get("/history")
async def get_history():
    """获取历史会议列表"""
    return session_manager.get_history_list()


@router.get("/history/{meeting_id}")
async def get_history_detail(meeting_id: str):
    """获取特定会议的详细记录"""
    detail = session_manager.get_history_detail(meeting_id)
    if not detail:
        return {"error": "Meeting not found"}
    return detail


@router.get("/audio/{meeting_id}")
async def get_audio(meeting_id: str):
    """下载会议录音"""
    detail = session_manager.get_history_detail(meeting_id)
    if not detail or not detail.get("audio_file"):
        return {"error": "Audio not found"}

    filename = detail["audio_file"]
    filepath = os.path.join(os.getcwd(), "recordings", filename)

    if not os.path.exists(filepath):
        return {"error": "File not found on server"}

    return FileResponse(filepath, media_type="audio/wav", filename=filename)


MAX_WAIT_TIME = 0.5


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = None
    cloud_handler = None
    use_cloud = False
    connection_closed = False  # 追踪连接状态

    # Event to signal when all processing is done
    processing_finished = asyncio.Event()

    # Callback to send results back to WebSocket
    async def send_results(results, is_final=False):
        nonlocal connection_closed

        try:
            if results:
                if isinstance(results, list):
                    for res in results:
                        if res.get("text"):
                            is_partial = res.get("is_partial", False)
                            msg_type = "partial" if is_partial else "final"

                            if not is_partial:
                                logger.info(f"ASR Result (Callback): {res['text']}")

                            response = RecognitionResult(
                                type=msg_type,
                                text=res["text"],
                                speaker=res.get("speaker_id") or "Unknown",
                                timestamp=res.get("timestamp") or time.time(),
                                vad_segments=(
                                    [res.get("vad_segment")]
                                    if res.get("vad_segment")
                                    else []
                                ),
                                session_id=session_id,
                            )

                            # 始终保存最终结果到历史记录（即使连接已关闭）
                            if not is_partial:
                                session_manager.add_transcript(
                                    session_id, response.text, response.speaker
                                )

                            # 仅在连接仍然打开时发送到 WebSocket
                            if (
                                not connection_closed
                                and websocket.client_state == WebSocketState.CONNECTED
                            ):
                                try:
                                    await websocket.send_text(
                                        response.model_dump_json()
                                    )
                                except Exception as send_err:
                                    # 发送失败但不影响处理流程
                                    logger.debug(
                                        f"WebSocket send skipped (closed): {send_err}"
                                    )

                elif isinstance(results, dict) and "error" in results:
                    logger.error(f"Inference error: {results['error']}")

            # If this was the final chunk, signal completion and cleanup
            if is_final:
                logger.info(f"Final processing completed for {session_id}")
                # 处理完成，设置状态为 finished
                session_manager.set_status(session_id, "finished")
                if not use_cloud:
                    asr_engine.unregister_callback(session_id)
                processing_finished.set()

        except Exception as e:
            logger.error(f"Error in send_results callback: {e}")
            # Ensure we don't hang if error occurs during final processing
            if is_final:
                if not use_cloud:
                    asr_engine.unregister_callback(session_id)
                processing_finished.set()

    # Callback for Cloud ASR
    async def cloud_callback(result):
        # Adapt cloud result to our format
        # result is {"text": "...", "is_partial": bool}
        # We need to wrap it in a list as send_results expects
        await send_results([result], is_final=False)

    try:
        # 1. Handshake
        data = await websocket.receive_text()
        try:
            handshake_data = json.loads(data)
            handshake = HandshakeMessage(**handshake_data)
            session_id = handshake.meeting_id

            # Validate meeting ID
            meeting = session_manager.get_meeting(session_id)
            if not meeting:
                logger.warning(f"Invalid meeting ID: {session_id}")
                await websocket.close(code=1008, reason="Invalid meeting ID")
                return

            if meeting.status != "active":
                logger.warning(f"Meeting {session_id} not active")
                await websocket.close(code=1008, reason="Meeting not active")
                return

            logger.info(
                f"Session {session_id} connected. Sample rate: {handshake.sample_rate}"
            )

            # 1.1 Init recording file
            recordings_dir = os.path.join(os.getcwd(), "recordings")
            os.makedirs(recordings_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            wav_filename = f"{session_id}_{timestamp}.wav"
            wav_path = os.path.join(recordings_dir, wav_filename)

            wav_file = wave.open(wav_path, "wb")
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(handshake.sample_rate)
            logger.info(f"Recording started: {wav_path}")

            # Record file to session
            session_manager.set_audio_file(session_id, wav_filename)
            session_manager.update_meeting_settings(session_id, handshake.use_cloud_asr)

            # Register callback or setup Cloud ASR
            if handshake.use_cloud_asr:
                use_cloud = True
                cloud_handler = CloudASRHandler(cloud_callback)
                connected = await cloud_handler.connect()
                if not connected:
                    logger.error(
                        "Failed to connect to Cloud ASR, falling back to local?"
                    )
                    # For now, just error out or close
                    await websocket.close(
                        code=1011, reason="Cloud ASR connection failed"
                    )
                    return
                logger.info(f"Session {session_id} using Cloud ASR")
            else:
                asr_engine.register_callback(session_id, send_results)
                # Ensure worker is running
                asr_engine.start_worker()

        except Exception as e:
            logger.error(f"Handshake failed: {e}")
            await websocket.close(code=1003)
            return

        # 2. Audio Stream Loop
        while True:
            message = None
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=5.0)
            except asyncio.TimeoutError:
                # Send ping
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
                continue
            except Exception as e:
                logger.error(f"Receive error: {e}")
                break
            if message and message["type"] == "websocket.receive":
                if "bytes" in message:
                    audio_chunk = message["bytes"]
                    # Write to recording file
                    if wav_file:
                        wav_file.writeframes(audio_chunk)

                    # Enqueue for processing
                    if use_cloud and cloud_handler:
                        await cloud_handler.send_audio(audio_chunk)
                    else:
                        await asr_engine.enqueue_audio(
                            session_id, audio_chunk, is_final=False
                        )

                elif message and "text" in message and message["text"]:
                    # Handle control messages
                    try:
                        control = json.loads(message["text"])
                        if control.get("type") == "stop":
                            logger.info(f"Session {session_id} stopped by client.")

                            # 设置状态为处理中
                            session_manager.set_status(session_id, "processing")

                            # Trigger final processing
                            if use_cloud and cloud_handler:
                                await cloud_handler.stop()
                                # Cloud handler stop might be async and we might need to wait for final results?
                                # For simplicity, we assume cloud_handler.stop() triggers necessary cleanup/final msg
                                # But we still need to signal processing_finished for the wait below.
                                # Actually, cloud_handler loop will close and we might not get a "final" callback in the same way.
                                # Let's just set it here for cloud case.
                                processing_finished.set()
                            else:
                                await asr_engine.enqueue_audio(
                                    session_id, b"", is_final=True
                                )

                            # Wait for processing to complete
                            logger.info(
                                "Waiting for background processing to finish..."
                            )
                            try:
                                await asyncio.wait_for(
                                    processing_finished.wait(), timeout=30.0
                                )  # 30s timeout
                                logger.info("Background processing finished.")
                            except asyncio.TimeoutError:
                                logger.warning(
                                    "Timeout waiting for background processing."
                                )

                            break  # Exit loop, close connection
                    except Exception as e:
                        logger.error(f"Control message error: {e}")

    except WebSocketDisconnect:
        connection_closed = True
        logger.info(f"Client disconnected: {session_id}")

        # 设置状态为处理中
        if session_id:
            session_manager.set_status(session_id, "processing")

        # 立即注销回调以阻止更多的发送尝试
        if session_id and not use_cloud:
            asr_engine.unregister_callback(session_id)

        # Do NOT reset session immediately, let the queue drain
        if session_id:
            # Enqueue final empty chunk to ensure any remaining buffer is processed
            # We fire and forget here since we can't await if the loop is broken?
            # Actually we can await since we are in async function.
            # Enqueue final empty chunk to ensure any remaining buffer is processed
            # We fire and forget here since we can't await if the loop is broken?
            # Actually we can await since we are in async function.
            if use_cloud and cloud_handler:
                await cloud_handler.stop()
            else:
                await asr_engine.enqueue_audio(session_id, b"", is_final=True)

            # Do NOT unregister callback here.
            # Let the worker finish processing and call send_results(..., is_final=True),
            # which will handle unregistering and saving to history.

            await session_manager.generate_analysis(session_id)

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if session_id:
            if use_cloud and cloud_handler:
                pass  # Already handled or connection broken
            else:
                await asr_engine.enqueue_audio(session_id, b"", is_final=True)
            # Don't unregister here either, let it finish if possible

        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
    finally:
        connection_closed = True
        if "wav_file" in locals() and wav_file:
            wav_file.close()
            logger.info(f"Recording saved: {wav_path}")

        if session_id:
            # 确保注销回调
            if not use_cloud:
                asr_engine.unregister_callback(session_id)
            await session_manager.generate_analysis(session_id)

            # 注意：不在这里设置 finished 状态，由 send_results(is_final=True) 在处理完成时设置

            # 只有在连接仍然打开时才发送停止消息
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text('{"type": "stopped"}')
                    await websocket.close()
                except Exception:
                    pass
