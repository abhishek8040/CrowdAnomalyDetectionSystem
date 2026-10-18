import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import useWebSocket from '../hooks/useWebSocket'
import AlertPanel from '../components/AlertPanel'
import ZoneDrawer from '../components/ZoneDrawer'
import LiveMjpegPlayer from '../components/LiveMjpegPlayer'
import VideoPlayer from '../components/VideoPlayer'
import './Dashboard.css'

const Dashboard = () => {
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  // Video File Upload & Playback
  const [videoFile, setVideoFile] = useState(null)
  const [videoObjectUrl, setVideoObjectUrl] = useState(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysisResult, setAnalysisResult] = useState(null)

  // Configuration
  const [config, setConfig] = useState({
    overcrowding_threshold: 10,
    loitering_time: 300,
    loitering_distance: 50.0,
    velocity_threshold: 15.0,
    restricted_zones: [],
    tripwire: null,
  })

  // Live Stream State
  const [liveSource, setLiveSource] = useState('0')
  const [liveRunning, setLiveRunning] = useState(false)
  const [liveFrame, setLiveFrame] = useState({ src: null, width: 800, height: 600 })
  const [useMjpeg, setUseMjpeg] = useState(true)
  const zoneRef = useRef(null)

  // Alerts & Live Stats
  const [alerts, setAlerts] = useState([])
  const [lastAlert, setLastAlert] = useState(null)
  const [stats, setStats] = useState({
    totalDetections: 0,
    totalAlerts: 0,
    currentCount: 0,
    densityRatio: 0,
    densityLevel: 'low',
    entryCount: 0,
    exitCount: 0,
  })

  // Natural Language Rule Engine State
  const [nlRulePrompt, setNlRulePrompt] = useState('')
  const [parsedRuleResult, setParsedRuleResult] = useState(null)
  const [isParsingRule, setIsParsingRule] = useState(false)
  const [activeRules, setActiveRules] = useState([])

  // WebSocket Connection
  const wsUrl = (API_BASE.replace(/^http/, 'ws') + '/api/stream/ws').replace(/([^:])\/\//g, '$1//')
  const { lastMessage, sendMessage, isConnected } = useWebSocket(wsUrl, { maxBuffer: 200 })

  // Fetch active rules from backend
  const fetchRules = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/rules/`)
      setActiveRules(res.data || [])
    } catch (e) {
      console.error('Failed to fetch rules:', e)
    }
  }, [API_BASE])

  useEffect(() => {
    fetchRules()
  }, [fetchRules])

  // Handle incoming WebSocket messages
  useEffect(() => {
    const msg = lastMessage
    if (!msg) return

    if (msg.type === 'alert') {
      setAlerts((prev) => [...prev, msg])
      setLastAlert(msg)
      setStats((prev) => ({
        ...prev,
        totalAlerts: prev.totalAlerts + 1,
      }))
    } else if (msg.type === 'detection') {
      setStats((prev) => ({
        ...prev,
        totalDetections: prev.totalDetections + msg.count,
        currentCount: msg.count,
        densityRatio: msg.crowd_density?.density_ratio || 0,
        densityLevel: msg.crowd_density?.density_level || 'low',
        entryCount: msg.entry_count || prev.entryCount,
        exitCount: msg.exit_count || prev.exitCount,
      }))
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

  // Update backend config when zones change during live stream
  useEffect(() => {
    if (liveRunning && isConnected) {
      try {
        sendMessage({ command: 'update_config', config })
      } catch (_) {}
    }
  }, [config.restricted_zones, liveRunning, isConnected, sendMessage])

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    setVideoFile(file)
    if (file) {
      const url = URL.createObjectURL(file)
      setVideoObjectUrl(url)
    }
  }

  const handleZonesUpdate = (zones) => {
    setConfig((prev) => ({
      ...prev,
      restricted_zones: zones,
    }))
  }

  // Upload and analyze video
  const handleAnalyze = async () => {
    if (!videoFile) {
      alert('Please select a video file')
      return
    }

    setIsAnalyzing(true)
    setAnalysisResult(null)

    const formData = new FormData()
    formData.append('video', videoFile)
    formData.append('config', JSON.stringify(config))

    try {
      const response = await axios.post(`${API_BASE}/api/analyze/upload`, formData, {
        timeout: 600000,
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
      })

      setAnalysisResult(response.data)
      setAlerts((prev) => [...prev, ...(response.data.events || [])])
      setStats((prev) => ({
        ...prev,
        totalDetections: response.data.total_frames || 0,
        totalAlerts: prev.totalAlerts + (response.data.events?.length || 0),
        entryCount: response.data.summary?.entry_count || 0,
        exitCount: response.data.summary?.exit_count || 0,
      }))
    } catch (error) {
      console.error('Analysis failed:', error)
      alert('Analysis failed: ' + (error.response?.data?.detail || error.message))
    } finally {
      setIsAnalyzing(false)
    }
  }

  // Live Stream Controls
  const startLive = () => {
    if (!liveSource && liveSource !== 0) {
      alert('Please select or enter a video source.')
      return
    }
    try {
      sendMessage({
        command: 'start_stream',
        source: liveSource,
        config: {
          ...config,
          preview_interval: 10,
          preview_max_width: 960,
        },
      })
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

  // Natural Language Rule Parser & Activation
  const handleParseNlRule = async () => {
    if (!nlRulePrompt.trim()) return
    setIsParsingRule(true)
    try {
      const res = await axios.post(`${API_BASE}/api/rules/parse`, { text: nlRulePrompt.trim() })
      setParsedRuleResult(res.data)
    } catch (e) {
      alert('Failed to parse rule: ' + (e.response?.data?.detail || e.message))
    } finally {
      setIsParsingRule(false)
    }
  }

  const handleActivateRule = async () => {
    if (!parsedRuleResult || !parsedRuleResult.is_supported) return
    try {
      await axios.post(`${API_BASE}/api/rules/`, {
        name: parsedRuleResult.name || 'Custom Rule',
        rule_type: parsedRuleResult.rule_type,
        config: parsedRuleResult.parameters || {},
        natural_language: parsedRuleResult.raw_text,
      })
      setNlRulePrompt('')
      setParsedRuleResult(null)
      fetchRules()
      alert('Rule activated successfully!')
    } catch (e) {
      alert('Failed to activate rule: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleDeleteRule = async (ruleId) => {
    try {
      await axios.delete(`${API_BASE}/api/rules/${ruleId}`)
      fetchRules()
    } catch (e) {
      alert('Failed to delete rule: ' + e.message)
    }
  }

  const handleToggleRule = async (ruleId, currentActive) => {
    try {
      await axios.patch(`${API_BASE}/api/rules/${ruleId}/toggle`, { is_active: !currentActive })
      fetchRules()
    } catch (e) {
      alert('Failed to toggle rule: ' + e.message)
    }
  }

  return (
    <div className="dashboard">
      <div className="dashboard-grid">
        {/* Main Monitoring & Controls Panel */}
        <div className="main-panel">
          {/* Live CCTV & Webcam Monitoring Card */}
          <div className="card">
            <div className="card-header-flex">
              <h2 className="card-title">Live Video Feed & Zone Security</h2>
              <div className="live-status-indicator">
                <span className={`status-dot ${liveRunning ? 'live' : ''}`} />
                <span>{liveRunning ? 'STREAM ACTIVE' : 'STREAM OFFLINE'}</span>
              </div>
            </div>

            {/* Camera Source Selector */}
            <div className="source-selector-bar">
              <span className="source-label">Source:</span>
              <button
                className={`btn btn-source ${liveSource === '0' ? 'active' : ''}`}
                onClick={() => setLiveSource('0')}
              >
                Webcam (Device 0)
              </button>
              <button
                className={`btn btn-source ${liveSource === '1' ? 'active' : ''}`}
                onClick={() => setLiveSource('1')}
              >
                Webcam (Device 1)
              </button>
              <input
                type="text"
                placeholder="or enter RTSP / HTTP URL (e.g. rtsp://192.168.1.10:554/live)"
                value={liveSource}
                onChange={(e) => setLiveSource(e.target.value)}
                className="source-input"
              />
              <button
                className="btn btn-primary"
                onClick={startLive}
                disabled={liveRunning}
              >
                Start Stream
              </button>
              <button
                className="btn btn-secondary"
                onClick={stopLive}
                disabled={!liveRunning}
              >
                Stop
              </button>
            </div>

            {/* Zone & Tripwire Action Controls */}
            <div className="zone-controls-bar">
              <button className="btn btn-primary" onClick={() => zoneRef.current?.startDrawing()}>
                + Draw Restricted Zone
              </button>
              <button className="btn btn-secondary" onClick={() => zoneRef.current?.finishZone()}>
                Finish Zone
              </button>
              <button className="btn btn-danger" onClick={() => zoneRef.current?.clearZones()}>
                Clear Zones
              </button>
              <span className="zone-badge">
                {zoneRef.current?.isDrawing() ? 'Drawing (Click video)' : `${config.restricted_zones.length} zone(s) active`}
              </span>
            </div>

            {/* Video Canvas Container */}
            <div className="stream-viewport-container">
              {useMjpeg && (
                <LiveMjpegPlayer
                  src={`${API_BASE}/api/stream/mjpeg`}
                  onSize={({ width, height }) => setLiveFrame((prev) => ({ ...prev, width, height }))}
                />
              )}
              <div className="zone-drawer-overlay">
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
                <div className="live-alert-overlay">
                  ⚠️ Alert: {lastAlert.event_type?.toUpperCase()} @ frame {lastAlert.frame_number}
                </div>
              )}
            </div>
          </div>

          {/* Upload & Replay Video Analysis Card */}
          <div className="card">
            <h2 className="card-title">Recorded Video Analysis & Overlay Replay</h2>
            <div className="upload-section">
              <input
                type="file"
                accept="video/*"
                onChange={handleFileChange}
                className="file-input"
                id="video-upload"
              />
              <label htmlFor="video-upload" className="file-label">
                {videoFile ? `Selected: ${videoFile.name}` : '📁 Choose video file to analyze...'}
              </label>
            </div>

            <div className="config-grid">
              <div className="config-item">
                <label>Overcrowding Threshold (people)</label>
                <input
                  type="number"
                  value={config.overcrowding_threshold}
                  onChange={(e) =>
                    setConfig({ ...config, overcrowding_threshold: parseInt(e.target.value) || 10 })
                  }
                  min="1"
                />
              </div>
              <div className="config-item">
                <label>Loitering Dwell Time (seconds)</label>
                <input
                  type="number"
                  value={config.loitering_time}
                  onChange={(e) =>
                    setConfig({ ...config, loitering_time: parseInt(e.target.value) || 60 })
                  }
                  min="5"
                />
              </div>
              <div className="config-item">
                <label>Loitering Radius (pixels)</label>
                <input
                  type="number"
                  value={config.loitering_distance}
                  onChange={(e) =>
                    setConfig({ ...config, loitering_distance: parseFloat(e.target.value) || 50.0 })
                  }
                  min="1"
                  step="5"
                />
              </div>
              <div className="config-item">
                <label>Motion Velocity Threshold</label>
                <input
                  type="number"
                  value={config.velocity_threshold}
                  onChange={(e) =>
                    setConfig({ ...config, velocity_threshold: parseFloat(e.target.value) || 15.0 })
                  }
                  min="1"
                  step="1"
                />
              </div>
            </div>

            <button
              className="btn btn-primary analyze-btn"
              onClick={handleAnalyze}
              disabled={!videoFile || isAnalyzing}
              style={{ marginTop: '1rem' }}
            >
              {isAnalyzing ? 'Processing Video (Inference & Tracking Running)...' : 'Start Video Analysis'}
            </button>

            {/* Video Player Replay with Detection Overlay */}
            {analysisResult && videoObjectUrl && (
              <div className="video-replay-section" style={{ marginTop: '1.5rem' }}>
                <h3 style={{ color: '#4dabf7', marginBottom: '0.8rem' }}>
                  Synchronized Detection Playback
                </h3>
                <VideoPlayer
                  src={videoObjectUrl}
                  frameTracks={analysisResult.frame_tracks || {}}
                  fps={analysisResult.fps || 30}
                  activeZones={config.restricted_zones}
                />
              </div>
            )}

            {/* Analysis Summary Breakdown */}
            {analysisResult && (
              <div className="analysis-summary-section" style={{ marginTop: '1.5rem' }}>
                <h3 style={{ color: '#4dabf7', marginBottom: '0.8rem' }}>Analysis Results Breakdown</h3>
                <div className="summary-grid">
                  <div className="summary-item">
                    <div className="summary-label">Frames Analyzed</div>
                    <div className="summary-value">{analysisResult.total_frames}</div>
                  </div>
                  <div className="summary-item">
                    <div className="summary-label">Total Incidents</div>
                    <div className="summary-value">{analysisResult.summary?.total_events || 0}</div>
                  </div>
                  <div className="summary-item">
                    <div className="summary-label">Overcrowding</div>
                    <div className="summary-value">{analysisResult.summary?.event_breakdown?.overcrowding || 0}</div>
                  </div>
                  <div className="summary-item">
                    <div className="summary-label">Loitering</div>
                    <div className="summary-value">{analysisResult.summary?.event_breakdown?.loitering || 0}</div>
                  </div>
                  <div className="summary-item">
                    <div className="summary-label">Zone Violations</div>
                    <div className="summary-value">{analysisResult.summary?.event_breakdown?.zone_violation || 0}</div>
                  </div>
                  <div className="summary-item">
                    <div className="summary-label">Altercations</div>
                    <div className="summary-value">{analysisResult.summary?.event_breakdown?.suspicious_activity || 0}</div>
                  </div>
                  <div className="summary-item">
                    <div className="summary-label">Falls / Downed</div>
                    <div className="summary-value">{analysisResult.summary?.event_breakdown?.fall || 0}</div>
                  </div>
                  <div className="summary-item">
                    <div className="summary-label">Panic / Running</div>
                    <div className="summary-value">
                      {(analysisResult.summary?.event_breakdown?.panic || 0) + (analysisResult.summary?.event_breakdown?.running || 0)}
                    </div>
                  </div>
                  <div className="summary-item" style={analysisResult.summary?.event_breakdown?.snatching > 0 ? { border: '1px solid #ef4444', backgroundColor: 'rgba(239, 68, 68, 0.12)' } : {}}>
                    <div className="summary-label" style={analysisResult.summary?.event_breakdown?.snatching > 0 ? { color: '#ef4444', fontWeight: 'bold' } : {}}>🏍️ Snatching / Theft</div>
                    <div className="summary-value" style={analysisResult.summary?.event_breakdown?.snatching > 0 ? { color: '#ef4444', fontWeight: 'bold' } : {}}>
                      {analysisResult.summary?.event_breakdown?.snatching || 0}
                    </div>
                  </div>
                </div>

                {analysisResult.summary?.event_breakdown?.snatching > 0 && (
                  <div style={{ marginTop: '1rem', padding: '0.85rem 1.25rem', borderRadius: '8px', backgroundColor: 'rgba(239, 68, 68, 0.18)', border: '1px solid #ef4444', color: '#fca5a5', display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                    <span style={{ fontSize: '1.75rem' }}>🚨</span>
                    <div>
                      <strong style={{ color: '#ffffff', fontSize: '1rem' }}>Drive-by Snatching / Theft Detected!</strong>
                      <div style={{ fontSize: '0.85rem', marginTop: '0.2rem', color: '#fecaca' }}>
                        The system detected {analysisResult.summary.event_breakdown.snatching} high-speed drive-by intercept(s) matching motorcycle/bicycle snatching kinematics. Review the incident logs and video replay below.
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Natural Language Rule Engine Panel */}
          <div className="card">
            <h2 className="card-title">Natural-Language Security Rules</h2>
            <p className="subtitle" style={{ marginBottom: '1rem' }}>
              Define behavioral security requirements in plain English. The rule engine translates them into explicit thresholds and validates feasibility.
            </p>

            <div className="nl-rule-input-group">
              <input
                type="text"
                placeholder='e.g. "Alert when crowd exceeds 8 people in zone 1" or "Alert if someone falls"'
                value={nlRulePrompt}
                onChange={(e) => setNlRulePrompt(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleParseNlRule()}
                className="nl-input"
              />
              <button
                className="btn btn-primary"
                onClick={handleParseNlRule}
                disabled={isParsingRule || !nlRulePrompt.trim()}
              >
                {isParsingRule ? 'Validating...' : 'Parse & Validate'}
              </button>
            </div>

            {/* Parsed Rule Feedback Card */}
            {parsedRuleResult && (
              <div className={`parsed-rule-card ${parsedRuleResult.is_supported ? 'supported' : 'unsupported'}`}>
                <div className="parsed-header">
                  <span className="parsed-status">
                    {parsedRuleResult.is_supported ? '✅ Supported Capability' : '⚠️ Unsupported Capability'}
                  </span>
                  {parsedRuleResult.name && <span className="parsed-name">{parsedRuleResult.name}</span>}
                </div>
                <p className="parsed-explanation">{parsedRuleResult.explanation}</p>
                {parsedRuleResult.unsupported_reason && (
                  <div className="unsupported-rationale">
                    <strong>Technical Rationale:</strong> {parsedRuleResult.unsupported_reason}
                  </div>
                )}
                {parsedRuleResult.is_supported && (
                  <button className="btn btn-success" onClick={handleActivateRule} style={{ marginTop: '0.8rem' }}>
                    Activate Rule
                  </button>
                )}
              </div>
            )}

            {/* Active Rules List */}
            {activeRules.length > 0 && (
              <div className="active-rules-list" style={{ marginTop: '1.2rem' }}>
                <h4 style={{ color: '#4dabf7', marginBottom: '0.6rem' }}>Active Operator Rules</h4>
                {activeRules.map((r) => (
                  <div key={r.rule_id} className="active-rule-item">
                    <div className="rule-info">
                      <strong>{r.name}</strong>
                      <span className="rule-nl-text">"{r.natural_language || r.rule_type}"</span>
                    </div>
                    <div className="rule-actions">
                      <button
                        className={`btn-toggle ${r.is_active ? 'active' : ''}`}
                        onClick={() => handleToggleRule(r.rule_id, r.is_active)}
                      >
                        {r.is_active ? 'Active' : 'Disabled'}
                      </button>
                      <button className="btn-del" onClick={() => handleDeleteRule(r.rule_id)}>
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Side Panel: Telemetry & Live Alerts */}
        <div className="side-panel">
          {/* Real-time Telemetry Stats Card */}
          <div className="card">
            <h2 className="card-title">Real-Time Telemetry</h2>
            <div className="telemetry-grid">
              <div className="stat-card">
                <div className="stat-value">{stats.currentCount}</div>
                <div className="stat-label">Visible Persons</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.densityLevel.toUpperCase()}</div>
                <div className="stat-label">Crowd Density ({Math.round(stats.densityRatio * 100)}%)</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.entryCount} / {stats.exitCount}</div>
                <div className="stat-label">Tripwire In / Out</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{isConnected ? '🟢 Online' : '🔴 Offline'}</div>
                <div className="stat-label">WebSocket Stream</div>
              </div>
            </div>
          </div>

          {/* Alert Notification Panel */}
          <AlertPanel alerts={alerts} apiBase={API_BASE} />
        </div>
      </div>
    </div>
  )
}

export default Dashboard
