import { useState, useEffect } from 'react'
import axios from 'axios'
import useWebSocket from '../hooks/useWebSocket'
import AlertPanel from '../components/AlertPanel'
import ZoneDrawer from '../components/ZoneDrawer'
import { useRef } from 'react'
import LiveMjpegPlayer from '../components/LiveMjpegPlayer'
import './Dashboard.css'

const Dashboard = () => {
  // Base API URL (works in preview/prod without dev proxy)
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const [videoFile, setVideoFile] = useState(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisResult, setAnalysisResult] = useState(null)
  const [config, setConfig] = useState({
    overcrowding_threshold: 10,
    loitering_time: 300,
    loitering_distance: 50.0,
    velocity_threshold: 15.0,
    restricted_zones: [],
  })
  const [alerts, setAlerts] = useState([])
  const [lastAlert, setLastAlert] = useState(null)
  const [stats, setStats] = useState({
    totalDetections: 0,
    totalAlerts: 0,
    currentCount: 0,
  })
  const [liveSource, setLiveSource] = useState('')
  const [liveRunning, setLiveRunning] = useState(false)
  const [liveFrame, setLiveFrame] = useState({ src: null, width: 800, height: 600 })
  const [previewInterval, setPreviewInterval] = useState(10) // send every Nth frame
  const [useMjpeg, setUseMjpeg] = useState(true)
  const zoneRef = useRef(null)

  const wsUrl = (API_BASE.replace(/^http/, 'ws') + '/api/stream/ws').replace(/([^:])\/\//g, '$1//')
  const { messages, lastMessage, sendMessage, isConnected } = useWebSocket(wsUrl, { maxBuffer: 200 })

  useEffect(() => {
    // Process only the latest WebSocket message
    const msg = lastMessage
    if (!msg) return
      if (msg.type === 'alert') {
        setAlerts((prev) => [...prev, msg])
        setLastAlert(msg)
        setStats((prev) => ({
          ...prev,
          totalAlerts: prev.totalAlerts + 1,
        }))
        console.log('UI received alert:', msg.event_type, msg.details)
      } else if (msg.type === 'detection') {
        setStats((prev) => ({
          ...prev,
          totalDetections: prev.totalDetections + msg.count,
          currentCount: msg.count,
        }))
        // no-op UI logs for detection bursts; keep lightweight
      } else if (msg.type === 'live_started') {
        setLiveRunning(true)
      } else if (msg.type === 'live_stopped') {
        setLiveRunning(false)
      } else if (msg.type === 'stream_info') {
        if (msg.width && msg.height) {
          setLiveFrame((prev) => ({ ...prev, width: msg.width, height: msg.height }))
        }
      } else if (msg.type === 'frame') {
        if (msg.image) {
          const dataUrl = msg.image.startsWith('data:') ? msg.image : `data:image/jpeg;base64,${msg.image}`
          setLiveFrame({ src: dataUrl, width: msg.width || liveFrame.width, height: msg.height || liveFrame.height })
        }
      } else if (msg.type === 'error') {
        alert('Live stream error: ' + (msg.message || 'Unknown error'))
      }
  }, [lastMessage])

  // When zones change during live, push config update to backend
  useEffect(() => {
    if (liveRunning && isConnected) {
      try {
        sendMessage({ command: 'update_config', config })
      } catch (_) {}
    }
  }, [config.restricted_zones])

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    setVideoFile(file)
  }

  const handleZonesUpdate = (zones) => {
    setConfig((prev) => ({
      ...prev,
      restricted_zones: zones,
    }))
  }

  const handleAnalyze = async () => {
    if (!videoFile) {
      alert('Please select a video file')
      return
    }

    setIsAnalyzing(true)
    setAnalysisResult(null)
    setAlerts([])

    const formData = new FormData()
    formData.append('video', videoFile)
    formData.append('config', JSON.stringify(config))

    try {
      const response = await axios.post(`${API_BASE}/api/analyze/upload`, formData, {
        // Let the browser set proper multipart boundary
        timeout: 600000, // 10 minutes
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
      })

      setAnalysisResult(response.data)
      setAlerts(response.data.events || [])
      setStats({
        totalDetections: response.data.total_frames || 0,
        totalAlerts: response.data.events?.length || 0,
        currentCount: 0,
      })
    } catch (error) {
      console.error('Analysis failed:', error)
      alert('Analysis failed: ' + (error.response?.data?.detail || error.message))
    } finally {
      setIsAnalyzing(false)
    }
  }

  const startLive = () => {
    if (!liveSource) {
      alert('Please enter a live CCTV/IP camera URL (RTSP or HTTP).')
      return
    }
    try {
      const liveConfig = {
        ...config,
        preview_interval: previewInterval,
        preview_max_width: 960,
      }
      sendMessage({ command: 'start_stream', source: liveSource, config: liveConfig })
    } catch (e) {
      alert('Failed to start live stream: ' + e.message)
    }
  }

  const stopLive = () => {
    try {
      sendMessage({ command: 'stop_stream' })
    } catch (e) {
      alert('Failed to stop live stream: ' + e.message)
    }
  }

  return (
    <div className="dashboard">
      <div className="dashboard-grid">
        <div className="main-panel">
          <div className="card">
            <h2 className="card-title">Video Upload & Analysis</h2>
            
            <div className="upload-section">
              <input
                type="file"
                accept="video/*"
                onChange={handleFileChange}
                className="file-input"
                id="video-upload"
              />
              <label htmlFor="video-upload" className="file-label">
                {videoFile ? videoFile.name : 'Choose video file...'}
              </label>
            </div>

            <div className="config-section">
              <h3>Detection Configuration</h3>
              <div className="config-grid">
                <div className="config-item">
                  <label>Overcrowding Threshold</label>
                  <input
                    type="number"
                    value={config.overcrowding_threshold}
                    onChange={(e) =>
                      setConfig({ ...config, overcrowding_threshold: parseInt(e.target.value) })
                    }
                    min="1"
                  />
                </div>
                <div className="config-item">
                  <label>Loitering Time (seconds)</label>
                  <input
                    type="number"
                    value={config.loitering_time}
                    onChange={(e) =>
                      setConfig({ ...config, loitering_time: parseInt(e.target.value) })
                    }
                    min="10"
                  />
                </div>
                <div className="config-item">
                  <label>Loitering Distance (pixels)</label>
                  <input
                    type="number"
                    value={config.loitering_distance}
                    onChange={(e) =>
                      setConfig({ ...config, loitering_distance: parseFloat(e.target.value) })
                    }
                    min="1"
                    step="0.1"
                  />
                </div>
                <div className="config-item">
                  <label>Velocity Threshold</label>
                  <input
                    type="number"
                    value={config.velocity_threshold}
                    onChange={(e) =>
                      setConfig({ ...config, velocity_threshold: parseFloat(e.target.value) })
                    }
                    min="1"
                    step="0.1"
                  />
                </div>
              </div>
            </div>

            <button
              className="btn btn-primary analyze-btn"
              onClick={handleAnalyze}
              disabled={!videoFile || isAnalyzing}
            >
              {isAnalyzing ? 'Analyzing...' : 'Start Analysis'}
            </button>
          </div>

          <div className="card">
            <h2 className="card-title">Define Restricted Zones</h2>
            <div className="zone-controls" style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
              <button className="btn btn-primary" onClick={() => zoneRef.current?.startDrawing()}>
                Draw New Zone
              </button>
              <button className="btn btn-secondary" onClick={() => zoneRef.current?.finishZone()}>
                Finish Zone
              </button>
              <button className="btn btn-danger" onClick={() => zoneRef.current?.clearZones()}>
                Clear All Zones
              </button>
              <span className="zone-info" style={{ color: '#4dabf7' }}>
                {zoneRef.current?.isDrawing() ? 'Click on video to add points' : `${config.restricted_zones.length} zone(s) defined`}
              </span>
            </div>
              <div style={{ position: 'relative', width: '100%', border: '2px solid #2a5298', borderRadius: 8, overflow: 'hidden' }}>
                {useMjpeg && (
                  <LiveMjpegPlayer
                    src={`${API_BASE}/api/stream/mjpeg`}
                    onSize={({ width, height }) => setLiveFrame((prev) => ({ ...prev, width, height }))}
                  />
                )}
                <div style={{ position: 'absolute', inset: 0 }}>
                  <ZoneDrawer
                    ref={zoneRef}
                    onZonesUpdate={handleZonesUpdate}
                    initialZones={config.restricted_zones}
                    width={liveFrame.width}
                    height={liveFrame.height}
                    hideControls
                    backgroundImage={useMjpeg ? null : liveFrame.src}
                  />
                </div>
                {lastAlert && (
                  <div style={{ position: 'absolute', right: 8, bottom: 8, background: 'rgba(0,0,0,0.6)', color: '#fff', padding: '6px 10px', borderRadius: 6 }}>
                    Alert: {lastAlert.event_type} @ frame {lastAlert.frame_number}
                  </div>
                )}
              </div>
          </div>

          {analysisResult && (
            <div className="card">
              <h2 className="card-title">Analysis Summary</h2>
              <div className="summary-grid">
                <div className="summary-item">
                  <div className="summary-label">Total Frames</div>
                  <div className="summary-value">{analysisResult.total_frames}</div>
                </div>
                <div className="summary-item">
                  <div className="summary-label">Total Events</div>
                  <div className="summary-value">{analysisResult.summary.total_events}</div>
                </div>
                <div className="summary-item">
                  <div className="summary-label">Overcrowding</div>
                  <div className="summary-value">
                    {analysisResult.summary.event_breakdown.overcrowding}
                  </div>
                </div>
                <div className="summary-item">
                  <div className="summary-label">Loitering</div>
                  <div className="summary-value">
                    {analysisResult.summary.event_breakdown.loitering}
                  </div>
                </div>
                <div className="summary-item">
                  <div className="summary-label">Zone Violations</div>
                  <div className="summary-value">
                    {analysisResult.summary.event_breakdown.zone_violation}
                  </div>
                </div>
                <div className="summary-item">
                  <div className="summary-label">Suspicious Activity</div>
                  <div className="summary-value">
                    {analysisResult.summary.event_breakdown.suspicious_activity}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="card-title">Live CCTV / IP Camera</h2>
          <div className="config-section">
            <div className="config-grid">
              <div className="config-item" style={{ gridColumn: '1 / -1' }}>
                <label>Camera URL (RTSP/HTTP)</label>
                <input
                  type="text"
                  placeholder="e.g., rtsp://user:pass@ip:554/stream or http://ip:port/video"
                  value={liveSource}
                  onChange={(e) => setLiveSource(e.target.value)}
                />
              </div>
              <div className="config-item">
                <label>Preview Transport</label>
                <select value={useMjpeg ? 'mjpeg' : 'ws'} onChange={(e) => setUseMjpeg(e.target.value === 'mjpeg')}>
                  <option value="mjpeg">MJPEG (smooth)</option>
                  <option value="ws">WebSocket frames</option>
                </select>
              </div>
              <div className="config-item">
                <label>Preview Smoothness</label>
                <select value={previewInterval} onChange={(e) => setPreviewInterval(parseInt(e.target.value))}>
                  <option value={1}>High (every frame)</option>
                  <option value={2}>Medium-High (every 2nd)</option>
                  <option value={5}>Medium (every 5th)</option>
                  <option value={10}>Low (every 10th)</option>
                </select>
              </div>
            </div>
            <div style={{ marginTop: '12px' }}>
              <button className="btn" onClick={startLive} disabled={liveRunning}>Start Live</button>
              <button className="btn btn-secondary" onClick={stopLive} disabled={!liveRunning} style={{ marginLeft: '8px' }}>Stop Live</button>
            </div>
            <p style={{ marginTop: '8px' }}>Status: {liveRunning ? 'Running' : 'Stopped'}</p>
          </div>
        </div>

        <div className="side-panel">
          <div className="card">
            <h2 className="card-title">Live Stats</h2>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{stats.currentCount}</div>
                <div className="stat-label">Current Count</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.totalAlerts}</div>
                <div className="stat-label">Total Alerts</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{isConnected ? '🟢' : '🔴'}</div>
                <div className="stat-label">WebSocket</div>
              </div>
            </div>
          </div>

          <AlertPanel alerts={alerts} />
        </div>
      </div>
    </div>
  )
}

export default Dashboard
