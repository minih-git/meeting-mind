import { useState, useEffect, useRef } from 'react'
import './App.css'
import { AudioProcessor } from './utils/audio-processor'
import { WebSocketClient } from './utils/websocket-client'
import ParticleBackground from './components/ParticleBackground'

import WaveformVisualizer from './components/WaveformVisualizer'
import HistoryPage from './components/HistoryPage'

function App() {
  const [meetingId, setMeetingId] = useState('')
  const [theme, setTheme] = useState('light') // Default to light as requested
  const [status, setStatus] = useState('idle') // idle, connecting, active, stopping
  const [transcripts, setTranscripts] = useState([])
  const [partialText, setPartialText] = useState('')
  const [analyser, setAnalyser] = useState(null)
  const [view, setView] = useState('recorder') // recorder, history
  const [duration, setDuration] = useState(0)

  
  const audioProcessor = useRef(null)
  const wsClient = useRef(null)
  const transcriptsEndRef = useRef(null)
  const fileInputRef = useRef(null)
  const statusRef = useRef(status) // Ref to track status in async loops

  useEffect(() => {
    statusRef.current = status
  }, [status])

  const scrollToBottom = () => {
    transcriptsEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [transcripts, partialText])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  useEffect(() => {
    let interval
    if (status === 'active') {
      interval = setInterval(() => {
        setDuration(prev => prev + 1)
      }, 1000)
    } else if (status === 'idle') {
      setDuration(0)
    }
    return () => clearInterval(interval)
  }, [status])

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  const clearRecords = () => {
    setTranscripts([])
    setPartialText('')
  }


  const startMeeting = async () => {
    try {
      setStatus('connecting')
      setDuration(0)
      clearRecords()

      
      // 1. Create Meeting via REST API
      const response = await fetch('/api/v1/meetings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: `Meeting ${new Date().toLocaleString()}`, participants: ['User'] })
      })
      
      if (!response.ok) throw new Error('Failed to create meeting')
      const meeting = await response.json()
      setMeetingId(meeting.id)
      console.log('Meeting created:', meeting.id)

      // 2. Initialize WebSocket
      wsClient.current = new WebSocketClient(
        `ws://${window.location.hostname}:8000/api/v1/ws`,
        (data) => {
          // Handle messages
          if (data.type === 'partial') {
            setPartialText(data.text)
          } else if (data.type === 'final') {
            setPartialText('')
            setTranscripts(prev => [...prev, {
              text: data.text,
              speaker: data.speaker || 'Unknown',
              timestamp: new Date().toLocaleTimeString()
            }])
          } else if (data.type === 'stopped') {
            console.log('Server stopped processing')
            if (wsClient.current) {
                wsClient.current.close()
                wsClient.current = null
            }
            setStatus('idle')
          } else if (data.type === 'ping') {
            // Respond to heartbeat
            if (wsClient.current) {
                wsClient.current.ws.send(JSON.stringify({ type: "pong" }));
            }
          }
        },
        () => {
          console.log('WS Open')
          setStatus('active')
          // 3. Start Audio Recording
          startAudio()
        },
        () => {
          console.log('WS Closed')
          setStatus('idle')
          stopAudio()
        },
        (err) => {
          console.error('WS Error', err)
          setStatus('error')
        }
      )
      
      wsClient.current.connect(meeting.id)

    } catch (err) {
      console.error('Start failed:', err)
      setStatus('error')
      alert('Failed to start meeting: ' + err.message)
    }
  }

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    try {
      setStatus('connecting');
      setDuration(0);
      clearRecords();
      console.log('Processing file:', file.name);

      // 1. Setup Playback for Visualization
      const arrayBuffer = await file.arrayBuffer();
      
      // Ensure audioProcessor instance exists
      if (!audioProcessor.current) {
        audioProcessor.current = new AudioProcessor(() => {});
      }
      
      const { analyser: newAnalyser } = await audioProcessor.current.setupPlayback(arrayBuffer.slice(0)); 
      setAnalyser(newAnalyser);

      // 2. Process Audio File for Sending
      const pcmBuffer = await AudioProcessor.processAudioFile(file);
      console.log('Audio processed, size:', pcmBuffer.byteLength);

      // 3. Create Meeting
      const response = await fetch('/api/v1/meetings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: `File Upload: ${file.name}`, participants: ['User'] })
      });
      
      if (!response.ok) throw new Error('Failed to create meeting');
      const meeting = await response.json();
      setMeetingId(meeting.id);

      // 4. Connect WebSocket
      wsClient.current = new WebSocketClient(
        `ws://${window.location.hostname}:8000/api/v1/ws`,
        (data) => {
           if (data.type === 'partial') {
            setPartialText(data.text)
          } else if (data.type === 'final') {
            setPartialText('')
            setTranscripts(prev => [...prev, {
              text: data.text,
              speaker: data.speaker || 'Unknown',
              timestamp: new Date().toLocaleTimeString()
            }])
          } else if (data.type === 'stopped') {
            console.log('Server stopped processing (File)')
            if (wsClient.current) {
                wsClient.current.close()
                wsClient.current = null
            }
            setStatus('idle')
          } else if (data.type === 'ping') {
            // Keep-alive, ignore
          }
        },
        async () => {
          console.log('WS Open - Sending File Audio');
          setStatus('active');
          
          // 5. Send Audio in chunks
          const chunkSize = 3200; // 100ms at 16k * 2 bytes
          const uint8Array = new Uint8Array(pcmBuffer);
          
          let aborted = false;
          for (let i = 0; i < uint8Array.length; i += chunkSize) {
            // Check if user stopped the meeting
            if (!wsClient.current || statusRef.current === 'stopping' || statusRef.current === 'idle') {
                console.log('Upload aborted by user');
                aborted = true;
                break;
            }
            
            const chunk = uint8Array.slice(i, i + chunkSize);
            wsClient.current.sendAudio(chunk);
            // Small delay to simulate stream and avoid overwhelming server/network
            await new Promise(r => setTimeout(r, 100));
          }
          
          if (!aborted) {
              console.log('File sent completely');
              // 6. Stop
              stopMeeting();
          }
        },
        () => {
          console.log('WS Closed');
          setStatus('idle');
        },
        (err) => {
          console.error('WS Error', err);
          setStatus('error');
        }
      );

      wsClient.current.connect(meeting.id);

    } catch (err) {
      console.error('File upload failed:', err);
      setStatus('error');
      alert('Failed to upload/process file: ' + err.message);
    } finally {
        // Reset input
        if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const startAudio = async () => {
    try {
      audioProcessor.current = new AudioProcessor((pcmData) => {
        if (wsClient.current) {
          wsClient.current.sendAudio(pcmData)
        }
      })

      await audioProcessor.current.start()
      setAnalyser(audioProcessor.current.getAnalyser())
    } catch (err) {
      console.error('Audio failed:', err)
      alert('Microphone access denied')
      stopMeeting()
    }
  }

  const stopAudio = () => {
    if (audioProcessor.current) {
      audioProcessor.current.stop()
      audioProcessor.current = null
      setAnalyser(null)
    }
  }

  const stopMeeting = async () => {
    setStatus('stopping')
    if (wsClient.current) {
      wsClient.current.sendStop()
    }
    stopAudio()
    // Call Stop API (optional, if backend needs it, but WS stop should be enough for session)
    if (meetingId) {
      try {
        await fetch(`/api/v1/meetings/${meetingId}/stop`, { method: 'POST' })
      } catch (e) {
        console.error('Stop API failed', e)
      }
    }
  }

  return (
    <div className="app-container">
      <ParticleBackground analyser={analyser} theme={theme} />
      
      <div className="glass-container">
        {view === 'history' ? (
            <HistoryPage onBack={() => setView('recorder')} />
        ) : (
        <>
        <header className="header">
            <div className="header-top">
                <h1>MeetingMind</h1>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <button 
                        className="btn btn-secondary" 
                        style={{ padding: '5px 10px', fontSize: '0.9rem' }}
                        onClick={() => setView('history')}
                        disabled={status !== 'idle'}
                    >
                        历史记录
                    </button>
                    <button 
                        className="btn btn-secondary" 
                        style={{ padding: '5px 10px', fontSize: '0.9rem' }}
                        onClick={toggleTheme}
                    >
                        {theme === 'light' ? '🌙' : '☀️'}
                    </button>
                    <div className="status-badge" data-status={status}>
                    {status === 'idle' && '就绪'}
                    {status === 'connecting' && '连接中...'}
                    {status === 'active' && '录音中'}
                    {status === 'stopping' && '正在停止，等待剩余结果...'}
                    {status === 'error' && '错误'}
                    </div>
                </div>
            </div>
            <div style={{ width: '100%', marginTop: '10px', display: 'flex', alignItems: 'center', gap: '15px' }}>
                <div style={{ flex: 1 }}>
                    <WaveformVisualizer analyser={analyser} theme={theme} />
                </div>
                <div className="timer-display">
                    {formatTime(duration)}
                </div>
            </div>
        </header>

        <main className="transcript-area">
            {transcripts.length === 0 && !partialText && (
            <div className="empty-state">
                <p>开始会议以查看实时转写。</p>
            </div>
            )}
            
            {transcripts.map((item, index) => (
            <div key={index} className="transcript-item">
                <div className="speaker-label">{item.speaker} <span className="timestamp">{item.timestamp}</span></div>
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

        <footer className="controls">
            {status === 'idle' || status === 'error' ? (
            <button className="btn btn-primary" onClick={startMeeting}>
                开始会议
            </button>
            ) : (
            <button className="btn btn-danger" onClick={stopMeeting} disabled={status === 'stopping'}>
                停止会议
            </button>
            )}
            
            <input 
                type="file" 
                ref={fileInputRef} 
                style={{ display: 'none' }} 
                accept="audio/*" 
                onChange={handleFileUpload} 
            />
            <button 
                className="btn btn-secondary" 
                onClick={() => fileInputRef.current?.click()}
                disabled={status !== 'idle'}
                style={{ marginLeft: '10px' }}
            >
                上传音频
            </button>
            <button 
                className="btn btn-secondary" 
                onClick={clearRecords}
                disabled={status !== 'idle' || (transcripts.length === 0 && !partialText)}
                style={{ marginLeft: '10px' }}
            >
                清除记录
            </button>
        </footer>
        </>
        )}
      </div>
    </div>
  )
}

export default App
