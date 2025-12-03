import React, { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import ParticleBackground from "./ParticleBackground";

const HistoryPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const meetingId = searchParams.get("id");

  const [history, setHistory] = useState([]);
  const [selectedMeeting, setSelectedMeeting] = useState(null);
  const [loading, setLoading] = useState(true);

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
      const res = await fetch("/api/v1/history");
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
      const res = await fetch(`/api/v1/history/${id}`);
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
      const res = await fetch(
        `/api/v1/meetings/${selectedMeeting.id}/analyze`,
        {
          method: "POST",
        }
      );
      if (!res.ok) throw new Error("Analysis failed");
      const analysis = await res.json();

      // Update local state
      setSelectedMeeting((prev) => ({
        ...prev,
        ai_analysis: analysis,
      }));
    } catch (err) {
      console.error("Analysis failed:", err);
      alert("分析失败，请稍后重试");
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
      const res = await fetch(
        `/api/v1/meetings/${selectedMeeting.id}/retranscribe`,
        {
          method: "POST",
        }
      );

      if (!res.ok) throw new Error("Retranscription request failed");

      const data = await res.json();
      alert(data.message || "后台转写任务已启动，请稍后刷新页面查看结果。");
    } catch (err) {
      console.error("Retranscription failed:", err);
      alert("请求失败，请检查网络或后端日志");
    } finally {
      setLoading(false);
    }
  };

  if (selectedMeeting) {
    return (
      <div className="app-container">
        <ParticleBackground theme={localStorage.getItem("theme") || "light"} />
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
                <a
                  href={`/api/v1/audio/${selectedMeeting.id}`}
                  download
                  className="download-btn"
                >
                  下载录音
                </a>
              ) : (
                <div style={{ width: "36px" }}></div>
              )}
            </div>
            <h3 style={{ margin: 0, color: "#4facfe", padding: "0 20px" }}>
              ✨ AI 会议分析
            </h3>

            {selectedMeeting.ai_analysis && (
              <div
                className="ai-analysis-section"
                style={{
                  background: "rgba(255, 255, 255, 0.1)",
                  padding: "20px",
                  borderRadius: "10px",
                  marginBottom: "20px",
                  border: "1px solid rgba(255, 255, 255, 0.2)",
                  margin: "0 20px",
                  maxHeight: "300px",
                  overflowY: "auto",
                  flexShrink: 0,
                }}
              >
                <div
                  className="analysis-grid"
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr 1fr",
                    gap: "20px",
                  }}
                >
                  <div className="analysis-card">
                    <h4>📝 会议总结</h4>
                    <p style={{ fontSize: "0.9rem", lineHeight: "1.5" }}>
                      {selectedMeeting.ai_analysis.summary}
                    </p>
                  </div>
                  <div className="analysis-card">
                    <h4>💡 关键要点</h4>
                    <div
                      style={{
                        fontSize: "0.9rem",
                        lineHeight: "1.5",
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
                        lineHeight: "1.5",
                        whiteSpace: "pre-wrap",
                      }}
                    >
                      {selectedMeeting.ai_analysis.action_items}
                    </div>
                  </div>
                </div>
              </div>
            )}
            <h3
              style={{
                margin: "10px",
                color: "#4facfe",
                marginBottom: "15px",
                padding: "0 20px",
              }}
            >
              💬 对话记录
            </h3>

            <div
              className="transcript-area"
              style={{
                margin: "0 20px",
                flex: "none",
                height: "auto",
                overflow: "visible",
                minHeight: "300px",
                flexShrink: 0,
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

            <div className="controls" style={{ flexShrink: 0 }}>
              <button
                className="btn btn-primary"
                onClick={analyzeMeeting}
                disabled={loading}
              >
                {loading ? "分析中..." : "✨ AI 智能分析"}
              </button>

              <button
                className="btn btn-secondary"
                onClick={retranscribeMeeting}
                disabled={loading}
                style={{ marginLeft: "10px" }}
              >
                🔄 重新转写
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <ParticleBackground theme={localStorage.getItem("theme") || "light"} />
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
                        data-status={
                          item.status === "finished" ? "idle" : "active"
                        }
                      >
                        {item.status === "finished" ? "已完成" : "进行中"}
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
