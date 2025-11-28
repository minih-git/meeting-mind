import React, { useState, useEffect } from 'react';

const HistoryPage = ({ onBack }) => {
  const [history, setHistory] = useState([]);
  const [selectedMeeting, setSelectedMeeting] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch('/api/v1/history');
      const data = await res.json();
      setHistory(data);
    } catch (err) {
      console.error('Failed to fetch history:', err);
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
      console.error('Failed to fetch detail:', err);
    } finally {
      setLoading(false);
    }
  };

  if (selectedMeeting) {
    return (
      <div className="history-detail">
        <div className="history-header">
            <button className="back-btn" onClick={() => setSelectedMeeting(null)} title="返回列表">
                ←
            </button>
            <h2>{selectedMeeting.title}</h2>
            {selectedMeeting.audio_file ? (
                <a 
                    href={`/api/v1/audio/${selectedMeeting.id}`} 
                    download
                    className="download-btn"
                >
                    下载录音
                </a>
            ) : (
                <div style={{ width: '36px' }}></div>
            )}
        </div>
        
        <div className="transcript-area">
            {selectedMeeting.transcripts && selectedMeeting.transcripts.map((item, index) => (
            <div key={index} className="transcript-item">
                <div className="speaker-label">
                    {item.speaker} 
                    <span className="timestamp">{new Date(item.timestamp * 1000).toLocaleTimeString()}</span>
                </div>
                <div className="text-content">{item.text}</div>
            </div>
            ))}
            {(!selectedMeeting.transcripts || selectedMeeting.transcripts.length === 0) && (
                <div className="empty-state">无转写记录</div>
            )}
        </div>
      </div>
    );
  }

  return (
    <div className="history-container">
      <div className="history-header">
        <button className="back-btn" onClick={onBack} title="返回录音">
            ←
        </button>
        <h2>历史记录</h2>
        <div style={{ width: '36px' }}></div> {/* Spacer for centering */}
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
                        onClick={() => fetchDetail(item.id)}
                    >
                        <div className="card-header" title={item.title}>
                            <h3 className="card-title" >{item.title}</h3>
                            <span className="status-badge" data-status={item.status === 'finished' ? 'idle' : 'active'}>
                                {item.status === 'finished' ? '已完成' : '进行中'}
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
  );
};

export default HistoryPage;
