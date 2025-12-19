import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { AudioProcessor } from "../utils/audio-processor";
import { WebSocketClient } from "../utils/websocket-client";

import WaveformVisualizer from "./WaveformVisualizer";
import Modal from "./Modal";
import OnboardingGuide from "./OnboardingGuide";

function RecorderPage({ theme, toggleTheme }) {
  const navigate = useNavigate();
  const [meetingId, setMeetingId] = useState("");
  const [status, setStatus] = useState("idle"); // idle, connecting, active, stopping
  const [transcripts, setTranscripts] = useState([]);
  const [partialText, setPartialText] = useState("");
  const [analyser, setAnalyser] = useState(null);
  const [duration, setDuration] = useState(0);
  const [secureMode, setSecureMode] = useState(true); // 默认涉密模式
  const [showWarningModal, setShowWarningModal] = useState(false);
  const [isAnimatingOut, setIsAnimatingOut] = useState(false);
  const [showProcessingToast, setShowProcessingToast] = useState(false);

  const audioProcessor = useRef(null);
  const wsClient = useRef(null);
  const transcriptsEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const statusRef = useRef(status);

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  const scrollToBottom = () => {
    transcriptsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [transcripts, partialText]);

  useEffect(() => {
    let interval;
    if (status === "active") {
      interval = setInterval(() => {
        setDuration((prev) => prev + 1);
      }, 1000);
    } else if (status === "idle") {
      setDuration(0);
    }
    return () => clearInterval(interval);
  }, [status]);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs
      .toString()
      .padStart(2, "0")}`;
  };

  const clearRecords = () => {
    setTranscripts([]);
    setPartialText("");
  };

  const startMeeting = async () => {
    try {
      setStatus("connecting");
      setDuration(0);
      clearRecords();

      // 1. Create Meeting via REST API
      const apiPrefix = import.meta.env.VITE_API_PREFIX || "/api/v1";
      const response = await fetch(`${apiPrefix}/meetings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: `Meeting ${new Date().toLocaleString()}`,
          participants: ["User"],
        }),
      });

      if (!response.ok) throw new Error("Failed to create meeting");
      const meeting = await response.json();
      setMeetingId(meeting.id);
      console.log("Meeting created:", meeting.id);

      // 2. Initialize WebSocket
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsPath = import.meta.env.VITE_WS_URI || "/ws/api/v1/ws";
      const wsUrl = `${protocol}//${window.location.host}${wsPath}`;

      wsClient.current = new WebSocketClient(
        wsUrl,
        (data) => {
          // Handle messages
          if (data.type === "partial") {
            setPartialText(data.text);
          } else if (data.type === "final") {
            setPartialText("");
            setTranscripts((prev) => [
              ...prev,
              {
                text: data.text,
                speaker: data.speaker || "Unknown",
                timestamp: new Date().toLocaleTimeString(),
              },
            ]);
          } else if (data.type === "stopped") {
            console.log("Server stopped processing");
            if (wsClient.current) {
              wsClient.current.close();
              wsClient.current = null;
            }
            setStatus("idle");
          } else if (data.type === "ping") {
            // Respond to heartbeat
            if (wsClient.current) {
              wsClient.current.ws.send(JSON.stringify({ type: "pong" }));
            }
          }
        },
        () => {
          console.log("WS Open");
          setStatus("active");
          // 3. Start Audio Recording
          startAudio();
        },
        () => {
          console.log("WS Closed");
          setStatus("idle");
          stopAudio();
        },
        (err) => {
          console.error("WS Error", err);
          setStatus("error");
        }
      );

      wsClient.current.connect(meeting.id, { useCloudAsr: !secureMode });
    } catch (err) {
      console.error("Start failed:", err);
      setStatus("error");
      alert("Failed to start meeting: " + err.message);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    try {
      setStatus("connecting");
      setDuration(0);
      clearRecords();
      console.log("Processing file:", file.name);

      // 1. Setup Playback for Visualization
      const arrayBuffer = await file.arrayBuffer();

      // Ensure audioProcessor instance exists
      if (!audioProcessor.current) {
        audioProcessor.current = new AudioProcessor(() => {});
      }

      const { analyser: newAnalyser } =
        await audioProcessor.current.setupPlayback(arrayBuffer.slice(0));
      setAnalyser(newAnalyser);

      // 2. Process Audio File for Sending
      const pcmBuffer = await AudioProcessor.processAudioFile(file);
      console.log("Audio processed, size:", pcmBuffer.byteLength);

      // 3. Create Meeting
      const apiPrefix = import.meta.env.VITE_API_PREFIX || "/api/v1";
      const response = await fetch(`${apiPrefix}/meetings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: `File Upload: ${file.name}`,
          participants: ["User"],
        }),
      });

      if (!response.ok) throw new Error("Failed to create meeting");
      const meeting = await response.json();
      setMeetingId(meeting.id);

      // 4. Connect WebSocket
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsPath = import.meta.env.VITE_WS_URI || "/ws/api/v1/ws";
      const wsUrl = `${protocol}//${window.location.host}${wsPath}`;

      wsClient.current = new WebSocketClient(
        wsUrl,
        (data) => {
          if (data.type === "partial") {
            setPartialText(data.text);
          } else if (data.type === "final") {
            setPartialText("");
            setTranscripts((prev) => [
              ...prev,
              {
                text: data.text,
                speaker: data.speaker || "Unknown",
                timestamp: new Date().toLocaleTimeString(),
              },
            ]);
          } else if (data.type === "stopped") {
            console.log("Server stopped processing (File)");
            if (wsClient.current) {
              wsClient.current.close();
              wsClient.current = null;
            }
            setStatus("idle");
          } else if (data.type === "ping") {
            // Keep-alive, ignore
          }
        },
        async () => {
          console.log("WS Open - Sending File Audio");
          setStatus("active");

          // 5. Send Audio in chunks
          const chunkSize = 3200; // 100ms at 16k * 2 bytes
          const uint8Array = new Uint8Array(pcmBuffer);

          // 发送所有已加载的音频，即使用户点击停止也继续发送
          // 只有在 WebSocket 断开时才中断
          for (let i = 0; i < uint8Array.length; i += chunkSize) {
            // 只在 WebSocket 断开或完全空闲时中断
            if (!wsClient.current || statusRef.current === "idle") {
              console.log("Upload interrupted - connection closed");
              break;
            }

            const chunk = uint8Array.slice(i, i + chunkSize);
            wsClient.current.sendAudio(chunk);
            // Small delay to simulate stream and avoid overwhelming server/network
            await new Promise((r) => setTimeout(r, 100));
          }

          console.log("File sent completely");
          // 6. Stop - 发送完成后通知后端
          stopMeeting();
        },
        () => {
          console.log("WS Closed");
          setStatus("idle");
        },
        (err) => {
          console.error("WS Error", err);
          setStatus("error");
        }
      );

      wsClient.current.connect(meeting.id, { useCloudAsr: !secureMode });
    } catch (err) {
      console.error("File upload failed:", err);
      setStatus("error");
      alert("Failed to upload/process file: " + err.message);
    } finally {
      // Reset input
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const startAudio = async () => {
    try {
      audioProcessor.current = new AudioProcessor((pcmData) => {
        if (wsClient.current) {
          wsClient.current.sendAudio(pcmData);
        }
      });

      await audioProcessor.current.start();
      setAnalyser(audioProcessor.current.getAnalyser());
    } catch (err) {
      console.error("Audio failed:", err);
      alert("Microphone access denied");
      stopMeeting();
    }
  };

  const stopAudio = () => {
    if (audioProcessor.current) {
      audioProcessor.current.stop();
      audioProcessor.current = null;
      setAnalyser(null);
    }
  };

  const stopMeeting = async () => {
    // 发送停止信号给后端，但不等待处理完成
    if (wsClient.current) {
      wsClient.current.sendStop();
      // 立即关闭 WebSocket，后端会在后台继续处理
      wsClient.current.close();
      wsClient.current = null;
    }
    stopAudio();
    
    // 触发淡出动画
    setIsAnimatingOut(true);
    
    // 显示处理中提示
    setShowProcessingToast(true);
    setTimeout(() => setShowProcessingToast(false), 3000);
    
    // 等待动画完成后重置状态
    setTimeout(() => {
      setIsAnimatingOut(false);
      setStatus("idle");
      setTranscripts([]);
      setPartialText("");
    }, 400);
    
    // 通知后端停止
    if (meetingId) {
      try {
        const apiPrefix = import.meta.env.VITE_API_PREFIX || "/api/v1";
        await fetch(`${apiPrefix}/meetings/${meetingId}/stop`, {
          method: "POST",
        });
      } catch (e) {
        console.error("Stop API failed", e);
      }
    }
  };

  return (
    <div className="app-container">


      <div className="glass-container">
        <header className="header">
          <div className="header-top">
            <h1>AI会议助手</h1>
            <div className="header-actions">
              <button
                id="btn-history"
                className="btn btn-secondary btn-header-text"
                onClick={() => navigate("/history")}
                disabled={status !== "idle"}
              >
                历史记录
              </button>
              <button
                className="btn btn-secondary btn-header-icon"
                onClick={toggleTheme}
              >
                {theme === "light" ? "🌙" : "☀️"}
              </button>
              <button
                id="btn-secure-mode"
                className="btn btn-secondary btn-header-icon"
                onClick={() => {
                  if (secureMode) {
                    setShowWarningModal(true);
                  }
                  setSecureMode(!secureMode);
                }}
                disabled={status !== "idle"}
                title={secureMode ? "涉密模式（本地推理）" : "非涉密模式（云端推理）"}
              >
                {secureMode ? "🛡️" : "🌐"}
              </button>
            </div>
          </div>
          {/* Unified Status Bar */}
          <div className="status-bar-container">
            <div className="status-indicator" data-status={status}>
              <span className="status-dot"></span>
              <span className="status-text">
                {status === "idle" && "就绪"}
                {status === "connecting" && "连接中"}
                {status === "active" && "录音中"}
                {status === "stopping" && "处理中"}
                {status === "error" && "错误"}
              </span>
            </div>
            
            <div className="visualizer-wrapper">
              <WaveformVisualizer analyser={analyser} theme={theme} />
            </div>

            <div className="timer-display">{formatTime(duration)}</div>
          </div>
        </header>

        <main className={`transcript-area ${isAnimatingOut ? 'fade-out-up' : ''}`}>
          {transcripts.length === 0 && !partialText && (
            <div className="empty-state">
              <p>开始会议以查看实时转写。</p>
            </div>
          )}

          {transcripts.map((item, index) => (
            <div key={index} className="transcript-item">
              <div className="speaker-label">
                {item.speaker}{" "}
                <span className="timestamp">{item.timestamp}</span>
              </div>
              <div className="text-content">{item.text}</div>
            </div>
          ))}

          {partialText && (
            <div className="transcript-item partial">
              <div className="speaker-label">正在识别...</div>
              <div className="text-content">{partialText}</div>
            </div>
          )}
          <div ref={transcriptsEndRef} />
        </main>

        <footer
          className="controls"
          style={{ flexDirection: "column", gap: "10px" }}
        >
          <div
            style={{
              display: "flex",
              gap: "4px",
              justifyContent: "center",
              width: "100%",
              flexWrap: "wrap",
            }}
          >
            {status === "idle" || status === "error" ? (
              <button id="btn-start-meeting" className="btn btn-primary" onClick={startMeeting}>
                开始会议
              </button>
            ) : (
              <button
                className="btn btn-danger"
                onClick={stopMeeting}
                disabled={status === "stopping"}
              >
                停止会议
              </button>
            )}

            <input
              type="file"
              ref={fileInputRef}
              style={{ display: "none" }}
              accept="audio/*"
              onChange={handleFileUpload}
            />
            <button
              className="btn btn-secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={status !== "idle"}
              style={{ marginLeft: "10px" }}
            >
              上传音频
            </button>

          </div>
        </footer>
      </div>

      {/* 涉密模式关闭警告弹窗 */}
      <Modal
        isOpen={showWarningModal}
        onClose={() => setShowWarningModal(false)}
        title="安全提醒"
        type="warning"
      >
        当前已关闭涉密保护。您的语音数据将传输至云端服务器进行高精度转录。请确保会议内容不涉企业核心机密。
      </Modal>

      {/* 新手引导 */}

      {/* 后台处理提示 Toast */}
      {showProcessingToast && (
        <div className="processing-toast">
          <span className="toast-icon">⏳</span>
          <span>录音已保存，后台正在处理中...</span>
        </div>
      )}

      <OnboardingGuide
        storageKey="meeting_mind_onboarding_v2"
        steps={[
          {
            targetSelector: "#btn-start-meeting",
            title: "开始录制会议",
            content: "点击此按钮开始实时转写，系统将自动记录您的语音内容。",
            position: "top",
          },
          {
            targetSelector: "#btn-secure-mode",
            title: "涉密模式切换",
            content: "🛡️ 涉密模式：数据本地处理\n🌐 非涉密：云端高精度转写",
            position: "bottom",
          },
          {
            targetSelector: "#btn-history",
            title: "查看历史记录",
            content: "会议结束后，点击这里查看详情并使用 AI 智能分析功能。",
            position: "bottom",
          },
        ]}
      />
    </div>
  );
}

export default RecorderPage;
