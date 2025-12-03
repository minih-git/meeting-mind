import asyncio
import json
import os
import uuid
import websockets
from meeting_mind.app.core.logger import logger
from meeting_mind.app.core.config import settings


class CloudASRHandler:
    def __init__(self, callback):
        self.api_key = settings.CLOUD_LLM_API_KEY
        if not self.api_key:
            logger.error("DASHSCOPE_API_KEY not found in environment variables")
        self.url = settings.CLOUD_ASR_API_BASE
        self.callback = callback
        self.ws = None
        self.task_id = uuid.uuid4().hex
        self.running = False
        self.task_started = False

    async def connect(self):
        if not self.api_key:
            return False

        try:
            self.ws = await websockets.connect(
                self.url, extra_headers={"Authorization": f"bearer {self.api_key}"}
            )
            self.running = True
            logger.info(f"Connected to Cloud ASR: {self.task_id}")

            # Start receiving loop
            asyncio.create_task(self._receive_loop())

            # Send run-task
            await self._send_run_task()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Cloud ASR: {e}")
            return False

    async def _send_run_task(self):
        run_task_message = {
            "header": {
                "action": "run-task",
                "task_id": self.task_id,
                "streaming": "duplex",
            },
            "payload": {
                "task_group": "audio",
                "task": "asr",
                "function": "recognition",
                "model": settings.CLOUD_ASR_MODEL,
                "parameters": {
                    "sample_rate": 16000,
                    "format": "pcm",  # Using PCM for raw stream
                },
                "input": {},
            },
        }
        await self.ws.send(json.dumps(run_task_message))

    async def send_audio(self, audio_chunk):
        if self.ws and self.task_started:
            try:
                await self.ws.send(audio_chunk)
            except Exception as e:
                logger.error(f"Error sending audio to Cloud ASR: {e}")

    async def stop(self):
        if self.ws and self.running:
            try:
                finish_task_message = {
                    "header": {
                        "action": "finish-task",
                        "task_id": self.task_id,
                        "streaming": "duplex",
                    },
                    "payload": {"input": {}},
                }
                await self.ws.send(json.dumps(finish_task_message))
                # Wait a bit for final results? The loop will handle close.
            except Exception as e:
                logger.error(f"Error stopping Cloud ASR: {e}")

    async def _receive_loop(self):
        try:
            async for message in self.ws:
                data = json.loads(message)
                header = data.get("header", {})
                event = header.get("event")

                if event == "task-started":
                    logger.info(f"Cloud ASR Task Started: {self.task_id}")
                    self.task_started = True

                elif event == "result-generated":
                    payload = data.get("payload", {})
                    logger.info(f"Cloud ASR Payload: {json.dumps(payload)}")
                    output = payload.get("output", {})
                    sentence = output.get("sentence", {})
                    text = sentence.get("text", "")

                    if text:
                        # Check if sentence is finished
                        is_final = False
                        if sentence.get("end_time") is not None:
                            is_final = True
                            logger.info(f"Sentence finished: {text}")

                        try:
                            await self.callback(
                                {"text": text, "is_partial": not is_final}
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send callback: {e}")

                elif event == "task-finished":
                    logger.info(f"Cloud ASR Task Finished: {self.task_id}")
                    self.running = False
                    await self.ws.close()
                    break

                elif event == "task-failed":
                    logger.error(
                        f"Cloud ASR Task Failed: {header.get('error_message')}"
                    )
                    self.running = False
                    if self.ws:
                        await self.ws.close()
                    break

        except Exception as e:
            logger.error(f"Cloud ASR Receive Loop Error: {e}")
        finally:
            self.running = False
