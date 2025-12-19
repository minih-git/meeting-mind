import React, { useState, useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";

import WaveformVisualizer from "./WaveformVisualizer";
import Modal from "./Modal";

const HistoryPage = ({ theme }) => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const meetingId = searchParams.get("id");

  const [history, setHistory] = useState([]);
  const [selectedMeeting, setSelectedMeeting] = useState(null);
  const [loading, setLoading] = useState(true);
  const [retranscribeProgress, setRetranscribeProgress] = useState(null);
  const [analyzeProgress, setAnalyzeProgress] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeTab, setActiveTab] = useState("analysis"); // 'analysis' | 'transcript'
  const [notification, setNotification] = useState({ isOpen: false, title: "", message: "", type: "info" });
  const audioRef = useRef(null);
  
  // API前缀，支持环境变量配置
  const apiPrefix = import.meta.env.VITE_API_PREFIX || "/api/v1";

  useEffect(() => {
    if (meetingId) {
      fetchDetail(meetingId);
    } else {
      fetchHistory();
      setSelectedMeeting(null);
    }
  }, [meetingId]);

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${apiPrefix}/history`);
      const data = await res.json();
      setHistory(data);
    } catch (err) {
      console.error("Failed to fetch history:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchDetail = async (id) => {
    try {
      setLoading(true);
      const res = await fetch(`${apiPrefix}/history/${id}`);
      const data = await res.json();
      setSelectedMeeting(data);
    } catch (err) {
      console.error("Failed to fetch detail:", err);
    } finally {
      setLoading(false);
    }
  };

  const analyzeMeeting = async () => {
    try {
      setLoading(true);
      setAnalyzeProgress({ progress: 0, message: "正在准备分析..." });

      // 模拟进度增长
      const progressInterval = setInterval(() => {
        setAnalyzeProgress((prev) => {
          if (!prev || prev.progress >= 90) return prev;
          return {
            progress: Math.min(prev.progress + 10, 90),
            message:
              prev.progress < 30
                ? "正在分析对话内容..."
                : prev.progress < 60
                ? "正在生成总结..."
                : "正在提取要点...",
          };
        });
      }, 800);

      const res = await fetch(
        `${apiPrefix}/meetings/${selectedMeeting.id}/analyze`,
        { method: "POST" }
      );

      clearInterval(progressInterval);

      if (!res.ok) throw new Error("Analysis failed");
      const analysis = await res.json();

      setAnalyzeProgress({ progress: 100, message: "分析完成！" });

      // Update local state
      setSelectedMeeting((prev) => ({
        ...prev,
        ai_analysis: analysis,
      }));

      // 延迟清除进度条
      setTimeout(() => setAnalyzeProgress(null), 1000);
    } catch (err) {
      console.error("Analysis failed:", err);
      setNotification({
        isOpen: true,
        title: "分析失败",
        message: "分析失败，请稍后重试",
        type: "error"
      });
      setAnalyzeProgress(null);
    } finally {
      setLoading(false);
    }
  };

  const retranscribeMeeting = async () => {
    if (
      !window.confirm(
        "重新转写将覆盖当前的对话记录，确定要继续吗？这可能需要几分钟时间。"
      )
    ) {
      return;
    }

    try {
      setLoading(true);
      setRetranscribeProgress({
        status: "starting",
        progress: 0,
        message: "正在启动...",
      });

      // 启动转写任务
      const res = await fetch(
        `${apiPrefix}/meetings/${selectedMeeting.id}/retranscribe`,
        { method: "POST" }
      );

      if (!res.ok) throw new Error("Retranscription request failed");

      // 使用 SSE 监听进度
      const eventSource = new EventSource(
        `${apiPrefix}/meetings/${selectedMeeting.id}/retranscribe/stream`
      );

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setRetranscribeProgress(data);

          if (data.status === "completed") {
            eventSource.close();
            setLoading(false);
            // 刷新页面数据
            fetchDetail(selectedMeeting.id);
            setNotification({
              isOpen: true,
              title: "成功",
              message: "转写完成！",
              type: "success"
            });
          } else if (data.status === "failed") {
            eventSource.close();
            setLoading(false);
            setNotification({
              isOpen: true,
              title: "转写失败",
              message: "转写失败: " + (data.error || "未知错误"),
              type: "error"
            });
          }
        } catch (e) {
          console.error("SSE parse error:", e);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setLoading(false);
        setRetranscribeProgress(null);
      };
    } catch (err) {
      console.error("Retranscription failed:", err);
      setNotification({
        isOpen: true,
        title: "请求失败",
        message: "请求失败，请检查网络或后端日志",
        type: "error"
      });
      setLoading(false);
      setRetranscribeProgress(null);
    }
  };

  // Audio Visualizer State
  const audioContextRef = useRef(null);
  const sourceRef = useRef(null);
  const analyserRef = useRef(null);
  const [analyser, setAnalyser] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Initialize Audio Context for Visualizer
  useEffect(() => {
    if (selectedMeeting?.audio_file && audioRef.current) {
      const audio = audioRef.current;
      audio.crossOrigin = "anonymous";
      
      const initAudioContext = () => {
        if (!audioContextRef.current) {
          audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
          analyserRef.current = audioContextRef.current.createAnalyser();
          analyserRef.current.fftSize = 256;
          
          sourceRef.current = audioContextRef.current.createMediaElementSource(audio);
          sourceRef.current.connect(analyserRef.current);
          analyserRef.current.connect(audioContextRef.current.destination);
          
          setAnalyser(analyserRef.current);
        } else if (audioContextRef.current.state === 'suspended') {
          audioContextRef.current.resume();
        }
      };

      // Interact to start AudioContext (browser policy)
      const handlePlayFn = () => {
        initAudioContext();
        setIsPlaying(true);
      };
      
      const handlePauseFn = () => setIsPlaying(false);
      const handleEndedFn = () => setIsPlaying(false);
      const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
      const handleLoadedMetadata = () => setDuration(audio.duration);

      audio.addEventListener('play', handlePlayFn);
      audio.addEventListener('pause', handlePauseFn);
      audio.addEventListener('ended', handleEndedFn);
      audio.addEventListener('timeupdate', handleTimeUpdate);
      audio.addEventListener('loadedmetadata', handleLoadedMetadata);

      return () => {
        audio.removeEventListener('play', handlePlayFn);
        audio.removeEventListener('pause', handlePauseFn);
        audio.removeEventListener('ended', handleEndedFn);
        audio.removeEventListener('timeupdate', handleTimeUpdate);
        audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
        // Do not close AudioContext here to avoid re-creation issues on re-renders, 
        // or manage it carefully. For simple SPA, keeping it is usually fine or close on unmount.
      };
    }
  }, [selectedMeeting]);

  // Pickup cleanup on unmount
  useEffect(() => {
    return () => {
        if (audioContextRef.current) {
            audioContextRef.current.close();
        }
    }
  }, []);

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
    }
  };

  if (selectedMeeting) {
    return (
      <div className="app-container">

        <div className="glass-container">
          <div className="history-detail">
            <div className="history-header" style={{ flexShrink: 0 }}>
              <button
                className="back-btn"
                onClick={() => navigate("/history")}
                title="返回列表"
              >
                ←
              </button>
              <div className="header-title-container">
                <h2 style={{ margin: 0 }} title={selectedMeeting.title}>
                  {selectedMeeting.title}
                </h2>
                {/* 涉密标识 */}
                {selectedMeeting.is_confidential ? (
                  <span 
                    className="confidential-badge"
                    title="涉密会议（本地处理）" 
                  >
                    🛡️ 涉密会议
                  </span>
                ) : (
                  <span 
                    className="cloud-badge"
                    title="常规会议（云端处理）" 
                  >
                    ☁️ 常规会议
                  </span>
                )}
              </div>

               {/* New Audio Player UI - Stacked on Mobile via CSS */}
               {selectedMeeting.audio_file && (
                <div className="header-audio-player">
                  <div className="status-bar-container player-bar">
                    <button
                      className="player-control-btn"
                      onClick={togglePlay}
                    >
                       {isPlaying ? "⏸️" : "▶️"}
                    </button>
                    
                    <div className="visualizer-wrapper">
                      <WaveformVisualizer analyser={analyser} theme={theme} />
                    </div>

                    <div className="player-time">
                      {formatTime(currentTime)} / {formatTime(duration)}
                    </div>
                    
                     <a
                      href={`${apiPrefix}/audio/${selectedMeeting.id}`}
                      download
                      className="download-icon-btn"
                      title="下载录音"
                    >
                      ⬇️
                    </a>
                  </div>

                  <audio
                    ref={audioRef}
                    src={`${apiPrefix}/audio/${selectedMeeting.id}`}
                    crossOrigin="anonymous"
                    style={{ display: "none" }}
                  />
                </div>
              )}
            </div>

            {/* Tab 导航 */}
            <div className="tab-nav">
              <button
                className={`tab-btn ${activeTab === "analysis" ? "active" : ""}`}
                onClick={() => setActiveTab("analysis")}
              >
                ✨ AI 会议分析
              </button>
              <button
                className={`tab-btn ${activeTab === "transcript" ? "active" : ""}`}
                onClick={() => setActiveTab("transcript")}
              >
                💬 对话记录
              </button>
            </div>

            {/* Tab 内容区域 */}
            <div className="tab-content">
              {/* AI 会议分析 Tab */}
              {activeTab === "analysis" && (
                <div className="tab-pane">
                  {selectedMeeting.ai_analysis ? (
                    <div className="ai-analysis-section">
                      <div className="analysis-grid">
                        <div className="analysis-card">
                          <h4>📝 会议总结</h4>
                          <p className="analysis-text">
                            {selectedMeeting.ai_analysis.summary}
                          </p>
                        </div>
                        <div className="analysis-card">
                          <h4>💡 关键要点</h4>
                          <div className="analysis-text-block">
                            {selectedMeeting.ai_analysis.key_points}
                          </div>
                        </div>
                        <div className="analysis-card">
                          <h4>✅ 行动项</h4>
                          <div className="analysis-text-block">
                            {selectedMeeting.ai_analysis.action_items}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="empty-state-content">
                      <span style={{ fontSize: "3rem" }}>✨</span>
                      <p>暂无分析结果</p>
                      <p className="empty-state-hint">点击下方"AI 智能分析"按钮生成会议分析</p>
                    </div>
                  )}
                </div>
              )}

              {/* 对话记录 Tab */}
              {activeTab === "transcript" && (
                <div className="transcript-area">
                  {selectedMeeting.transcripts &&
                    selectedMeeting.transcripts.map((item, index) => (
                      <div key={index} className="transcript-item">
                        <div className="speaker-label">
                          {item.speaker}
                          <span className="timestamp">
                            {new Date(item.timestamp * 1000).toLocaleTimeString()}
                          </span>
                        </div>
                        <div className="text-content">{item.text}</div>
                      </div>
                    ))}
                  {(!selectedMeeting.transcripts ||
                    selectedMeeting.transcripts.length === 0) && (
                    <div className="empty-state">无转写记录</div>
                  )}
                </div>
              )}
            </div>

            <div className="controls history-controls">
              <div className="controls-group">
                <button
                  className="btn btn-primary"
                  onClick={analyzeMeeting}
                  disabled={loading || selectedMeeting.status === "processing"}
                  title={selectedMeeting.status === "processing" ? "语音处理中，请稍后" : ""}
                >
                  {analyzeProgress ? "分析中..." : selectedMeeting.status === "processing" ? "⏳ 处理中..." : "✨ AI 智能分析"}
                </button>

                <button
                  className="btn btn-secondary"
                  onClick={retranscribeMeeting}
                  disabled={loading || selectedMeeting.status === "processing"}
                  title={selectedMeeting.status === "processing" ? "语音处理中，请稍后" : ""}
                >
                  {selectedMeeting.status === "processing" ? "⏳ 处理中..." : "🔄 重新转写"}
                </button>
              </div>

              {analyzeProgress && (
                <div className="progress-container">
                  <div className="progress-label">
                    <span>{analyzeProgress.message}</span>
                    <span>{analyzeProgress.progress}%</span>
                  </div>
                  <div className="progress-bar">
                    <div
                      className="progress-bar-fill analyze"
                      style={{ width: `${analyzeProgress.progress}%` }}
                    />
                  </div>
                </div>
              )}

              {retranscribeProgress && (
                <div className="progress-container">
                  <div className="progress-label">
                    <span>{retranscribeProgress.message}</span>
                    <span>{retranscribeProgress.progress}%</span>
                  </div>
                  <div className="progress-bar">
                    <div
                      className="progress-bar-fill retranscribe"
                      style={{ width: `${retranscribeProgress.progress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <Modal
          isOpen={notification.isOpen}
          onClose={() => setNotification({ ...notification, isOpen: false })}
          title={notification.title}
          type={notification.type}
        >
          {notification.message}
        </Modal>
      </div>
    );
  }

  return (
    <div className="app-container">

      <div className="glass-container">
        <div className="history-container">
          <div className="history-header">
            <button
              className="back-btn"
              onClick={() => navigate("/home")}
              title="返回录音"
            >
              ←
            </button>
            <h2>历史记录</h2>
            <div style={{ width: "36px" }}></div> {/* Spacer for centering */}
          </div>

          <div className="history-list">
            {loading ? (
              <div className="empty-state">加载中...</div>
            ) : history.length === 0 ? (
              <div className="empty-state">暂无历史记录</div>
            ) : (
              <div className="history-grid">
                {history.map((item) => (
                  <div
                    key={item.id}
                    className={`history-card ${item.is_confidential ? 'confidential-card' : ''}`}
                    onClick={() => {
                      if (item.status === "active" || item.status === "processing") {
                        setNotification({
                          isOpen: true,
                          title: "无法查看详情",
                          message: "该会议正在录音或处理中，暂时无法查看详情",
                          type: "warning"
                        });
                        return;
                      }
                      navigate(`/history/detail?id=${item.id}`);
                    }}
                    style={item.is_confidential ? {
                      border: "2px solid rgba(255, 71, 87, 0.6)",
                      boxShadow: "0 0 15px rgba(255, 71, 87, 0.2)",
                    } : {}}
                  >
                    <div className="card-header" title={item.title} style={{ alignItems: "center" }}>
                      <h2 className="card-title">
                        {item.is_confidential ? (
                          <span className="confidential-text">
                            🛡️涉密
                          </span>
                        ) : (
                          <span className="cloud-text">
                            ☁️常规
                          </span>
                        )}
                        {item.title}
                      </h2>
                      <span
                        className="status-badge"
                        data-status={item.status}
                      >
                        {item.status === "finished" && "已完成"}
                        {item.status === "active" && "录音中"}
                        {item.status === "processing" && "处理中"}
                      </span>
                    </div>
                    <div className="card-meta">
                      <div className="meta-item">
                        <span>📅</span>
                        {new Date(item.start_time * 1000).toLocaleDateString()}
                      </div>
                      <div className="meta-item">
                        <span>🕒</span>
                        {new Date(item.start_time * 1000).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <Modal
        isOpen={notification.isOpen}
        onClose={() => setNotification({ ...notification, isOpen: false })}
        title={notification.title}
        type={notification.type}
      >
        {notification.message}
      </Modal>
    </div>
  );
};

export default HistoryPage;
