import React, { useState, useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";


const HistoryPage = () => {
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
      alert("分析失败，请稍后重试");
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
            alert("转写完成！");
          } else if (data.status === "failed") {
            eventSource.close();
            setLoading(false);
            alert("转写失败: " + (data.error || "未知错误"));
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
      alert("请求失败，请检查网络或后端日志");
      setLoading(false);
      setRetranscribeProgress(null);
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
              <div
                style={{
                  flex: 1,
                  marginLeft: "10px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <h2 style={{ margin: 0 }} title={selectedMeeting.title}>
                  {selectedMeeting.title}
                </h2>
              </div>

              {selectedMeeting.audio_file ? (
                <div
                  style={{ display: "flex", gap: "10px", alignItems: "center" }}
                >
                  <button
                    className="btn btn-secondary"
                    style={{ padding: "5px 12px", fontSize: "0.85rem" }}
                    onClick={() => {
                      if (audioRef.current) {
                        if (isPlaying) {
                          audioRef.current.pause();
                        } else {
                          audioRef.current.play();
                        }
                        setIsPlaying(!isPlaying);
                      }
                    }}
                  >
                    {isPlaying ? "⏸️ 暂停" : "▶️ 播放"}
                  </button>
                  <a
                    href={`${apiPrefix}/audio/${selectedMeeting.id}`}
                    download
                    className="download-btn"
                  >
                    下载录音
                  </a>
                  <audio
                    ref={audioRef}
                    src={`${apiPrefix}/audio/${selectedMeeting.id}`}
                    onEnded={() => setIsPlaying(false)}
                    style={{ display: "none" }}
                  />
                </div>
              ) : (
                <div style={{ width: "36px" }}></div>
              )}
            </div>

            {/* Tab 导航 */}
            <div className="tab-nav" style={{
              display: "flex",
              justifyContent: "center",
              gap: "4px",
              margin: "12px 20px",
              padding: "4px",
              background: "var(--bg-tertiary)",
              borderRadius: "12px",
            }}>
              <button
                className={`tab-btn ${activeTab === "analysis" ? "active" : ""}`}
                onClick={() => setActiveTab("analysis")}
                style={{
                  padding: "8px 20px",
                  background: activeTab === "analysis" ? "var(--accent-primary)" : "transparent",
                  border: "none",
                  borderRadius: "8px",
                  color: activeTab === "analysis" ? "#fff" : "var(--text-secondary)",
                  fontSize: "0.9rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
              >
                ✨ AI 会议分析
              </button>
              <button
                className={`tab-btn ${activeTab === "transcript" ? "active" : ""}`}
                onClick={() => setActiveTab("transcript")}
                style={{
                  padding: "8px 20px",
                  background: activeTab === "transcript" ? "var(--accent-primary)" : "transparent",
                  border: "none",
                  borderRadius: "8px",
                  color: activeTab === "transcript" ? "#fff" : "var(--text-secondary)",
                  fontSize: "0.9rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
              >
                💬 对话记录
              </button>
            </div>

            {/* Tab 内容区域 */}
            <div className="tab-content" style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
              {/* AI 会议分析 Tab */}
              {activeTab === "analysis" && (
                <div style={{ flex: 1, overflow: "auto", padding: "15px 20px" }}>
                  {selectedMeeting.ai_analysis ? (
                    <div
                      className="ai-analysis-section"
                      style={{
                        background: "rgba(255, 255, 255, 0.1)",
                        padding: "20px",
                        borderRadius: "10px",
                        border: "1px solid rgba(255, 255, 255, 0.2)",
                      }}
                    >
                      <div
                        className="analysis-grid"
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr",
                          gap: "20px",
                        }}
                      >
                        <div className="analysis-card">
                          <h4>📝 会议总结</h4>
                          <p style={{ fontSize: "0.9rem", lineHeight: "1.6" }}>
                            {selectedMeeting.ai_analysis.summary}
                          </p>
                        </div>
                        <div className="analysis-card">
                          <h4>💡 关键要点</h4>
                          <div
                            style={{
                              fontSize: "0.9rem",
                              lineHeight: "1.6",
                              whiteSpace: "pre-wrap",
                            }}
                          >
                            {selectedMeeting.ai_analysis.key_points}
                          </div>
                        </div>
                        <div className="analysis-card">
                          <h4>✅ 行动项</h4>
                          <div
                            style={{
                              fontSize: "0.9rem",
                              lineHeight: "1.6",
                              whiteSpace: "pre-wrap",
                            }}
                          >
                            {selectedMeeting.ai_analysis.action_items}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="empty-state" style={{ 
                      display: "flex", 
                      flexDirection: "column", 
                      alignItems: "center",
                      justifyContent: "center",
                      height: "100%",
                      gap: "15px",
                      color: "var(--text-secondary)"
                    }}>
                      <span style={{ fontSize: "3rem" }}>✨</span>
                      <p>暂无分析结果</p>
                      <p style={{ fontSize: "0.85rem" }}>点击下方"AI 智能分析"按钮生成会议分析</p>
                    </div>
                  )}
                </div>
              )}

              {/* 对话记录 Tab */}
              {activeTab === "transcript" && (
                <div
                  className="transcript-area"
                  style={{
                    flex: 1,
                    margin: "15px 20px",
                    overflow: "auto",
                  }}
                >
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

            <div
              className="controls"
              style={{ flexShrink: 0, flexDirection: "column", gap: "10px" }}
            >
              <div
                style={{
                  display: "flex",
                  gap: "10px",
                  justifyContent: "center",
                }}
              >
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
                <div
                  style={{
                    width: "100%",
                    padding: "10px 20px",
                    background: "rgba(255,255,255,0.1)",
                    borderRadius: "8px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: "5px",
                      fontSize: "0.9rem",
                    }}
                  >
                    <span>{analyzeProgress.message}</span>
                    <span>{analyzeProgress.progress}%</span>
                  </div>
                  <div
                    style={{
                      width: "100%",
                      height: "8px",
                      background: "rgba(255,255,255,0.2)",
                      borderRadius: "4px",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${analyzeProgress.progress}%`,
                        height: "100%",
                        background: "linear-gradient(90deg, #ff9a9e, #fecfef)",
                        transition: "width 0.3s ease",
                      }}
                    />
                  </div>
                </div>
              )}

              {retranscribeProgress && (
                <div
                  style={{
                    width: "100%",
                    padding: "10px 20px",
                    background: "rgba(255,255,255,0.1)",
                    borderRadius: "8px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: "5px",
                      fontSize: "0.9rem",
                    }}
                  >
                    <span>{retranscribeProgress.message}</span>
                    <span>{retranscribeProgress.progress}%</span>
                  </div>
                  <div
                    style={{
                      width: "100%",
                      height: "8px",
                      background: "rgba(255,255,255,0.2)",
                      borderRadius: "4px",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${retranscribeProgress.progress}%`,
                        height: "100%",
                        background: "linear-gradient(90deg, #4facfe, #00f2fe)",
                        transition: "width 0.3s ease",
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
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
                    className="history-card"
                    onClick={() => navigate(`/history/detail?id=${item.id}`)}
                  >
                    <div className="card-header" title={item.title}>
                      <h2 className="card-title">{item.title}</h2>
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
    </div>
  );
};

export default HistoryPage;
