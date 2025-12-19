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
  const [showMeetingTypeModal, setShowMeetingTypeModal] = useState(false);
  const [pendingAction, setPendingAction] = useState(null); // 'start' | 'upload'
  const [pendingFile, setPendingFile] = useState(null);
  const [isAnimatingOut, setIsAnimatingOut] = useState(false);
  const [showProcessingToast, setShowProcessingToast] = useState(false);
  const [notification, setNotification] = useState({ isOpen: false, title: "", message: "", type: "info" });

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

  // 用户选择会议类型后开始会议
  const handleStartMeeting = (isConfidential) => {
    setSecureMode(isConfidential);
    setShowMeetingTypeModal(false);
    
    if (pendingAction === 'upload' && pendingFile) {
      // 处理文件上传
      setTimeout(() => processFileUpload(pendingFile, isConfidential), 50);
    } else {
      // 开始录音
      setTimeout(() => startMeetingWithMode(isConfidential), 50);
    }
    setPendingAction(null);
    setPendingFile(null);
  };

  const startMeetingWithMode = async (isConfidential) => {
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
          is_confidential: isConfidential,
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

      wsClient.current.connect(meeting.id);
    } catch (err) {
      console.error("Start failed:", err);
      setStatus("error");
      setNotification({
        isOpen: true,
        title: "启动失败",
        message: "Failed to start meeting: " + err.message,
        type: "error"
      });
    }
  };

  // 点击上传按钮时，先选择文件
  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    // 存储文件并显示类型选择框
    setPendingFile(file);
    setPendingAction('upload');
    setShowMeetingTypeModal(true);
    
    // 清空 input 以便可以重新选择同一文件
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const processFileUpload = async (file, isConfidential) => {
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
          is_confidential: isConfidential,
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

      wsClient.current.connect(meeting.id);
    } catch (err) {
      console.error("File upload failed:", err);
      setStatus("error");
      setNotification({
        isOpen: true,
        title: "上传失败",
        message: "Failed to upload/process file: " + err.message,
        type: "error"
      });
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
      setNotification({
        isOpen: true,
        title: "权限错误",
        message: "Microphone access denied",
        type: "error"
      });
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
                onClick={() => {
                  if (status === "active" || status === "stopping" || status === "connecting") {
                    setNotification({
                      isOpen: true,
                      title: "无法跳转",
                      message: "当前正在录音或处理中，请稍后再试",
                      type: "warning"
                    });
                    return;
                  }
                  navigate("/history");
                }}
              >
                历史记录
              </button>
              <button
                className="btn btn-secondary btn-header-icon"
                onClick={toggleTheme}
              >
                {theme === "light" ? "🌙" : "☀️"}
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
              <button id="btn-start-meeting" className="btn btn-primary" onClick={() => setShowMeetingTypeModal(true)}>
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
              onChange={handleFileChange}
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

      {/* 会议类型选择弹窗 */}
      {showMeetingTypeModal && (
        <div className="modal-overlay" onClick={() => {
          setShowMeetingTypeModal(false);
          setPendingAction(null);
          setPendingFile(null);
        }}>
          <div 
            className="modal-container" 
            style={{ maxWidth: "500px" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header" style={{ marginBottom: "20px" }}>
              <span className="modal-icon">🎙️</span>
              <h2 className="modal-title">选择会议类型</h2>
            </div>
            
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {/* 涉密会议选项 */}
              <div 
                className="meeting-type-option"
                onClick={() => handleStartMeeting(true)}
                style={{
                  padding: "16px 20px",
                  borderRadius: "12px",
                  border: "2px solid rgba(255, 71, 87, 0.4)",
                  background: "linear-gradient(135deg, rgba(255, 71, 87, 0.1), rgba(255, 107, 129, 0.05))",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
                  <span style={{ fontSize: "1.5rem" }}>🛡️</span>
                  <span style={{ fontSize: "1.1rem", fontWeight: "600", color: "#ff4757" }}>涉密会议</span>
                </div>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: "1.5" }}>
                  数据完全在本地处理，不上传云端。适合涉及企业机密、个人隐私等敏感内容的会议。
                </p>
              </div>

              {/* 常规会议选项 */}
              <div 
                className="meeting-type-option"
                onClick={() => handleStartMeeting(false)}
                style={{
                  padding: "16px 20px",
                  borderRadius: "12px",
                  border: "2px solid rgba(59, 130, 246, 0.4)",
                  background: "linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(96, 165, 250, 0.05))",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
                  <span style={{ fontSize: "1.5rem" }}>☁️</span>
                  <span style={{ fontSize: "1.1rem", fontWeight: "600", color: "#3b82f6" }}>常规会议</span>
                </div>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: "1.5" }}>
                  使用云端 AI 服务，提供更高精度的语音转写和智能分析。适合日常会议、培训等场景。
                </p>
              </div>
            </div>

            <button 
              className="btn btn-secondary" 
              onClick={() => setShowMeetingTypeModal(false)}
              style={{ marginTop: "16px", width: "100%" }}
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* Notification Modal */}
      <Modal
        isOpen={notification.isOpen}
        onClose={() => setNotification({ ...notification, isOpen: false })}
        title={notification.title}
        type={notification.type}
      >
        {notification.message}
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
            content: "点击此按钮选择会议类型并开始实时转写。",
            position: "top",
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
