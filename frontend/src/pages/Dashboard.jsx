import { useState, useEffect } from 'react'
import axios from 'axios'
import useWebSocket from '../hooks/useWebSocket'
import AlertPanel from '../components/AlertPanel'
import ZoneDrawer from '../components/ZoneDrawer'
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
  const [stats, setStats] = useState({
    totalDetections: 0,
    totalAlerts: 0,
    currentCount: 0,
  })

  const wsUrl = (API_BASE.replace(/^http/, 'ws') + '/api/stream/ws').replace(/([^:])\/\//g, '$1//')
  const { messages, sendMessage, isConnected } = useWebSocket(wsUrl)

  useEffect(() => {
    // Process WebSocket messages
    messages.forEach((msg) => {
      if (msg.type === 'alert') {
        setAlerts((prev) => [...prev, msg])
        setStats((prev) => ({
          ...prev,
          totalAlerts: prev.totalAlerts + 1,
        }))
      } else if (msg.type === 'detection') {
        setStats((prev) => ({
          ...prev,
          totalDetections: prev.totalDetections + msg.count,
          currentCount: msg.count,
        }))
      }
    })
  }, [messages])

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
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 600000, // 10 minutes
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
            <ZoneDrawer onZonesUpdate={handleZonesUpdate} initialZones={config.restricted_zones} />
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
