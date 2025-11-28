import uuid
import time
import json
import os
from typing import Dict, List, Optional
from openai import OpenAI
from meeting_mind.app.schemas.meeting import MeetingResponse, TranscriptItem
from meeting_mind.app.core.logger import logger

class SessionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            cls._instance.meetings: Dict[str, dict] = {}
            cls._instance.transcripts: Dict[str, List[TranscriptItem]] = {}
            # 初始化数据目录
            cls._instance.data_dir = os.path.join(os.getcwd(), "data", "history")
            os.makedirs(cls._instance.data_dir, exist_ok=True)
            # 加载现有历史记录
            cls._instance._load_history()
            
            # 初始化 OpenAI 客户端
            api_key = "sk-fdc4a1cd6e714790b400c5a07f6c293c"
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            if api_key:
                cls._instance.openai_client = OpenAI(api_key=api_key, base_url=base_url)
                logger.info("OpenAI 客户端初始化成功")
            else:
                cls._instance.openai_client = None
                logger.warning("未找到 OPENAI_API_KEY，自动摘要功能将不可用")
                
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
                                # 转录内容按需加载，或者如果是活跃状态则保留在内存中
                                # 为了简单起见，除非访问，否则我们不会立即将历史项目的转录加载到内存中。
                                # 但这里我们可以只加载元数据。
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

    def create_meeting(self, title: str, participants: List[str]) -> MeetingResponse:
        meeting_id = str(uuid.uuid4())
        now = time.time()
        
        meeting_info = {
            "id": meeting_id,
            "title": title,
            "status": "active",
            "start_time": now,
            "participants": participants,
            "audio_file": None
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
        if meeting_id in self.meetings:
            self.meetings[meeting_id]["status"] = "finished"
            self.save_session(meeting_id)
            return True
        return False

    def set_audio_file(self, meeting_id: str, filename: str):
        if meeting_id in self.meetings:
            self.meetings[meeting_id]["audio_file"] = filename
            self.save_session(meeting_id)

    def add_transcript(self, meeting_id: str, text: str, speaker: Optional[str] = None):
        if meeting_id in self.transcripts:
            item = TranscriptItem(
                text=text,
                speaker=speaker,
                timestamp=time.time()
            )
            self.transcripts[meeting_id].append(item)
            self.save_session(meeting_id)

    def get_transcript(self, meeting_id: str) -> List[TranscriptItem]:
        return self.transcripts.get(meeting_id, [])

    def get_history_list(self) -> List[dict]:
        """Get list of meeting summaries sorted by time desc"""
        history = []
        for m in self.meetings.values():
            history.append({
                "id": m["id"],
                "title": m["title"],
                "start_time": m["start_time"],
                "status": m["status"],
                "participants": m["participants"],
                "audio_file": m.get("audio_file")
            })
        return sorted(history, key=lambda x: x["start_time"], reverse=True)

    def get_history_detail(self, meeting_id: str) -> Optional[dict]:
        """Get full meeting detail including transcripts"""
        if meeting_id in self.meetings:
            data = self.meetings[meeting_id].copy()
            # 如果转录内容在内存中，直接使用
            if meeting_id in self.transcripts:
                data["transcripts"] = [t.model_dump() for t in self.transcripts[meeting_id]]
            # 否则尝试从文件加载（例如服务器重启后）
            elif "transcripts" not in data:
                 # 如果 _load_history 中未加载转录，则再次尝试从文件加载
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
                        if filename.startswith(f"{meeting_id}_") and filename.endswith(".wav"):
                            data["audio_file"] = filename
                            # 更新内存并保存到磁盘以备将来使用
                            self.meetings[meeting_id]["audio_file"] = filename
                            self.save_session(meeting_id)
                            break

            return data
            return data
        return None

    def generate_meeting_summary(self, meeting_id: str):
        """生成会议摘要标题"""
        if not self.openai_client:
            logger.warning("OpenAI 客户端未初始化，跳过摘要生成")
            return

        logger.info(f"正在为会议 {meeting_id} 生成智能标题...")
        
        # 获取完整的会议内容
        detail = self.get_history_detail(meeting_id)
        if not detail or not detail.get("transcripts"):
            logger.info("会议内容为空，无法生成摘要")
            return

        # 拼接转录文本
        full_text = "\n".join([f"{t['speaker']}: {t['text']}" for t in detail["transcripts"]])
        
        # 截断过长的文本以避免 token 超限 (简单处理，取前 8000 字符)
        if len(full_text) > 8000:
            full_text = full_text[:8000] + "..."

        try:
            response = self.openai_client.chat.completions.create(
                model="qwen3-max", # 或者使用 gpt-4o / gpt-4-turbo
                messages=[
                    {"role": "system", "content": "你是一个专业的会议助手。请根据以下会议记录，生成一个简短、精准的会议标题（不超过 20 个字）。直接返回标题，不要包含引号或其他废话。"},
                    {"role": "user", "content": full_text}
                ],
                temperature=0.7,
                max_tokens=50
            )
            
            title = response.choices[0].message.content.strip()
            logger.info(f"生成的会议标题: {title}")
            
            # 更新会议标题
            if meeting_id in self.meetings:
                self.meetings[meeting_id]["title"] = title
                self.save_session(meeting_id)
                
        except Exception as e:
            logger.error(f"生成会议摘要失败: {e}")

session_manager = SessionManager()
