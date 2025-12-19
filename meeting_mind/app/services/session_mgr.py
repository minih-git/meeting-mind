import uuid
import time
import json
import os
import asyncio
from typing import Dict, List, Optional
from meeting_mind.app.schemas.meeting import MeetingResponse, TranscriptItem
from meeting_mind.app.core.logger import logger
from meeting_mind.app.services.llm_engine import llm_engine


class SessionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            cls._instance.meetings: Dict[str, dict] = {}
            cls._instance.transcripts: Dict[str, List[TranscriptItem]] = {}
            # 重新转写任务状态追踪
            cls._instance.retranscribe_tasks: Dict[str, dict] = {}
            # 初始化数据目录
            cls._instance.data_dir = os.path.join(os.getcwd(), "data", "history")
            os.makedirs(cls._instance.data_dir, exist_ok=True)
            # 加载现有历史记录
            cls._instance._load_history()

        return cls._instance

    def _load_history(self):
        """从磁盘加载所有历史记录"""
        try:
            for filename in os.listdir(self.data_dir):
                if filename.endswith(".json"):
                    filepath = os.path.join(self.data_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            meeting_id = data.get("id")
                            if meeting_id:
                                self.meetings[meeting_id] = data
                    except Exception as e:
                        logger.error(f"加载历史文件失败 {filename}: {e}")
        except Exception as e:
            logger.error(f"加载历史目录出错: {e}")

    def save_session(self, meeting_id: str):
        """保存会话到磁盘"""
        if meeting_id not in self.meetings:
            return

        data = self.meetings[meeting_id].copy()
        # 添加转录到数据中
        if meeting_id in self.transcripts:
            data["transcripts"] = [t.model_dump() for t in self.transcripts[meeting_id]]

        filepath = os.path.join(self.data_dir, f"{meeting_id}.json")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存会话失败 {meeting_id}: {e}")

    def create_meeting(
        self, title: str, participants: List[str], is_confidential: bool = False
    ) -> MeetingResponse:
        """创建新会议

        Args:
            title: 会议标题
            participants: 参与者列表
            is_confidential: 涉密模式，True=使用本地模型，False=使用云端模型
        """
        meeting_id = str(uuid.uuid4())
        now = time.time()

        meeting_info = {
            "id": meeting_id,
            "title": title,
            "status": "active",
            "start_time": now,
            "participants": participants,
            "audio_file": None,
            "ai_analysis": None,
            "is_confidential": is_confidential,
        }

        self.meetings[meeting_id] = meeting_info
        self.transcripts[meeting_id] = []

        return MeetingResponse(**meeting_info)

    def get_meeting(self, meeting_id: str) -> Optional[MeetingResponse]:
        info = self.meetings.get(meeting_id)
        if info:
            return MeetingResponse(**info)
        return None

    def stop_meeting(self, meeting_id: str) -> bool:
        """标记会议为处理中（录音已停止，后台仍在处理）"""
        if meeting_id in self.meetings:
            # 设置为 processing 而非 finished，因为后台可能仍在处理音频
            # finished 状态由 ASR 回调在处理完成时设置
            self.meetings[meeting_id]["status"] = "processing"
            self.save_session(meeting_id)
            return True
        return False

    def set_status(self, meeting_id: str, status: str) -> bool:
        """设置会议状态 (active, processing, finished)"""
        if meeting_id in self.meetings:
            self.meetings[meeting_id]["status"] = status
            self.save_session(meeting_id)
            return True
        return False

    def set_audio_file(self, meeting_id: str, filename: str):
        if meeting_id in self.meetings:
            self.meetings[meeting_id]["audio_file"] = filename
            self.save_session(meeting_id)

    def set_confidential(self, meeting_id: str, is_confidential: bool) -> bool:
        """设置会议涉密状态

        Args:
            meeting_id: 会议ID
            is_confidential: 涉密模式，True=使用本地模型，False=使用云端模型
        """
        if meeting_id in self.meetings:
            self.meetings[meeting_id]["is_confidential"] = is_confidential
            self.save_session(meeting_id)
            return True
        return False

    def add_transcript(self, meeting_id: str, text: str, speaker: Optional[str] = None):
        if meeting_id in self.transcripts:
            item = TranscriptItem(text=text, speaker=speaker, timestamp=time.time())
            self.transcripts[meeting_id].append(item)
            self.save_session(meeting_id)

    def get_transcript(self, meeting_id: str) -> List[TranscriptItem]:
        # 1. Memory cache hit
        if meeting_id in self.transcripts:
            return self.transcripts[meeting_id]

        # 2. Check loaded meetings dict
        if meeting_id in self.meetings:
            meeting_data = self.meetings[meeting_id]
            if "transcripts" in meeting_data:
                try:
                    items = [TranscriptItem(**t) for t in meeting_data["transcripts"]]
                    self.transcripts[meeting_id] = items
                    return items
                except Exception as e:
                    logger.error(
                        f"Error parsing transcripts from memory for {meeting_id}: {e}"
                    )

        # 3. Fallback to disk read
        filepath = os.path.join(self.data_dir, f"{meeting_id}.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "transcripts" in data:
                        items = [TranscriptItem(**t) for t in data["transcripts"]]
                        self.transcripts[meeting_id] = items
                        # Ensure meeting metadata is loaded if missing
                        if meeting_id not in self.meetings:
                            self.meetings[meeting_id] = data
                        return items
            except Exception as e:
                logger.error(f"Failed to load transcript from file {filepath}: {e}")

        return []

    def get_history_list(self) -> List[dict]:
        """获取会议历史列表，按时间倒序排列"""
        history = []
        for m in self.meetings.values():
            history.append(
                {
                    "id": m["id"],
                    "title": m["title"],
                    "start_time": m["start_time"],
                    "status": m["status"],
                    "participants": m["participants"],
                    "audio_file": m.get("audio_file"),
                    "is_confidential": m.get("is_confidential", False),
                }
            )
        return sorted(history, key=lambda x: x["start_time"], reverse=True)

    def get_history_detail(self, meeting_id: str) -> Optional[dict]:
        """Get full meeting detail including transcripts"""
        if meeting_id in self.meetings:
            data = self.meetings[meeting_id].copy()
            # 如果转录内容在内存中，直接使用
            if meeting_id in self.transcripts:
                data["transcripts"] = [
                    t.model_dump() for t in self.transcripts[meeting_id]
                ]
            # 否则尝试从文件加载
            elif "transcripts" not in data:
                filepath = os.path.join(self.data_dir, f"{meeting_id}.json")
                if os.path.exists(filepath):
                    with open(filepath, "r", encoding="utf-8") as f:
                        full_data = json.load(f)
                        data["transcripts"] = full_data.get("transcripts", [])

            # 遗留支持：如果 audio_file 缺失，尝试在录音目录中查找
            if not data.get("audio_file"):
                recordings_dir = os.path.join(os.getcwd(), "recordings")
                if os.path.exists(recordings_dir):
                    for filename in os.listdir(recordings_dir):
                        if filename.startswith(f"{meeting_id}_") and filename.endswith(
                            ".wav"
                        ):
                            data["audio_file"] = filename
                            self.meetings[meeting_id]["audio_file"] = filename
                            self.save_session(meeting_id)
            return data
        return None

    async def generate_analysis(self, meeting_id: str):
        """
        生成会议分析：总结、要点、行动项
        """
        meeting = self.get_meeting(meeting_id)
        if not meeting:
            return None

        # 获取转录内容
        transcripts = self.get_transcript(meeting_id)
        if not transcripts:
            return None

        # 拼接全文
        full_text = "\n".join([f"{t.speaker}: {t.text}" for t in transcripts])

        if not full_text.strip():
            return None

        system_prompt = """你是一个专业的会议记录助手。请根据提供的会议对话内容，生成以下分析结果：
1. 会议总结 (Summary): 简要概括会议的主要内容。
2. 关键要点 (Key Points): 列出会议中讨论的关键信息点。
3. 行动项 (Action Items): 提取需要后续跟进的任务或行动。

请以 JSON 格式返回，格式如下：
{
    "summary": "...",
    "key_points": "...",
    "action_items": "..."
}
注意：请直接返回 JSON 字符串，不要包含 markdown 代码块标记。
"""

        try:
            response = await llm_engine.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_text},
                ],
                stream=False,
                force_cloud=not meeting.is_confidential,  # 涉密会议使用本地模型
            )

            content = response["content"]
            # 清理可能的 markdown 标记
            content = content.replace("```json", "").replace("```", "").strip()

            import json

            analysis_data = json.loads(content)

            # 兼容处理：如果 LLM 返回的是列表，转换为字符串
            for key in ["key_points", "action_items", "summary"]:
                if key in analysis_data and isinstance(analysis_data[key], list):
                    analysis_data[key] = "\n".join(
                        [str(item) for item in analysis_data[key]]
                    )

            from meeting_mind.app.schemas.meeting import AIAnalysis

            # 更新会议数据
            meeting.ai_analysis = AIAnalysis(**analysis_data)

            # 更新内存中的源数据
            if meeting_id in self.meetings:
                self.meetings[meeting_id]["ai_analysis"] = analysis_data

            # 自动更新标题 (如果还是默认标题)
            if meeting.title.startswith("Meeting_") or meeting.title == "New Meeting":
                summary = analysis_data.get("summary", "")
                if summary:
                    new_title = summary[:20] + "..."
                    meeting.title = new_title
                    if meeting_id in self.meetings:
                        self.meetings[meeting_id]["title"] = new_title

            self.save_session(meeting_id)
            return meeting.ai_analysis

        except Exception as e:
            logger.error(f"AI Analysis failed: {e}")
            return None

    async def generate_title(self, meeting_id: str):
        """
        生成简短标题
        """
        meeting = self.get_meeting(meeting_id)
        if not meeting:
            return None

        # 获取转录内容
        transcripts = self.get_transcript(meeting_id)
        if not transcripts:
            return None

        # 拼接全文 (截取前 2000 字符以节省 context)
        full_text = "\n".join([f"{t.speaker}: {t.text}" for t in transcripts])[:2000]

        system_prompt = "你是一个会议助手。请根据以下会议内容，生成一个简短、精准的会议标题（不超过15个字）。只返回标题文本，不要包含引号或其他内容。"

        try:
            response = await llm_engine.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_text},
                ],
                stream=False,
                force_cloud=not meeting.is_confidential,  # 涉密会议使用本地模型
            )

            title = response["content"].strip().strip('"').strip("《").strip("》")

            # 更新标题
            meeting.title = title
            if meeting_id in self.meetings:
                self.meetings[meeting_id]["title"] = title

            self.save_session(meeting_id)
            return title

        except Exception as e:
            logger.error(f"Title generation failed: {e}")
            return None

    async def retranscribe_meeting(self, meeting_id: str):
        """
        重新转写会议音频，带进度追踪
        """
        meeting = self.get_meeting(meeting_id)
        if not meeting or not meeting.audio_file:
            raise ValueError("Meeting not found or no audio file")

        from meeting_mind.app.core.config import settings

        audio_path = os.path.join(
            settings.BASE_DIR, "..", "recordings", meeting.audio_file
        )
        if not os.path.exists(audio_path):
            # Try absolute path if stored differently or relative to cwd
            audio_path = os.path.join(os.getcwd(), "recordings", meeting.audio_file)
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {meeting.audio_file}")

        logger.info(f"Retranscribing meeting {meeting_id} from {audio_path}")

        # 初始化任务状态
        self.retranscribe_tasks[meeting_id] = {
            "status": "running",
            "progress": 0,
            "message": "正在初始化...",
            "error": None,
        }

        # 运行转写
        from meeting_mind.app.services.asr_engine import asr_engine
        import asyncio

        loop = asyncio.get_running_loop()

        try:
            self.retranscribe_tasks[meeting_id]["message"] = "正在加载音频文件..."
            self.retranscribe_tasks[meeting_id]["progress"] = 10

            # 运行转写
            results = await loop.run_in_executor(
                None, lambda: asr_engine.transcribe_file(audio_path)
            )

            self.retranscribe_tasks[meeting_id]["message"] = "转写完成，正在保存..."
            self.retranscribe_tasks[meeting_id]["progress"] = 80

            # 转换为 TranscriptItem 对象
            from meeting_mind.app.schemas.meeting import TranscriptItem

            new_transcripts = [TranscriptItem(**item) for item in results]

            # 直接更新内存中的 transcripts
            self.transcripts[meeting_id] = new_transcripts
            # 保存到磁盘
            self.save_session(meeting_id)

            self.retranscribe_tasks[meeting_id]["message"] = "正在生成标题..."
            self.retranscribe_tasks[meeting_id]["progress"] = 90

            # 自动生成标题
            try:
                await self.generate_title(meeting_id)
            except Exception as e:
                logger.warning(f"Auto title generation failed: {e}")

            # 完成
            self.retranscribe_tasks[meeting_id] = {
                "status": "completed",
                "progress": 100,
                "message": "转写完成",
                "error": None,
            }

            return new_transcripts

        except Exception as e:
            logger.error(f"Retranscription failed: {e}")
            self.retranscribe_tasks[meeting_id] = {
                "status": "failed",
                "progress": 0,
                "message": "转写失败",
                "error": str(e),
            }
            raise e

    def get_retranscribe_status(self, meeting_id: str) -> dict:
        """获取重新转写任务状态"""
        return self.retranscribe_tasks.get(
            meeting_id,
            {
                "status": "not_started",
                "progress": 0,
                "message": "任务未启动",
                "error": None,
            },
        )


session_manager = SessionManager()
