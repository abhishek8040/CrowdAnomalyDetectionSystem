import { useEffect, useState, useRef, useCallback } from 'react'
import axios from 'axios'
import './AlertPanel.css'

const AlertPanel = ({ alerts = [], maxAlerts = 15, apiBase = 'http://localhost:8000' }) => {
  const [displayAlerts, setDisplayAlerts] = useState([])
  const [volume, setVolume] = useState(0.5)
  const [isMuted, setIsMuted] = useState(false)
  const [browserNotifications, setBrowserNotifications] = useState(false)
  const [audioError, setAudioError] = useState(null)
  const audioCtxRef = useRef(null)

  // Initialize or resume Web Audio context
  const getAudioContext = useCallback(() => {
    if (!audioCtxRef.current) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext
      if (AudioCtx) {
        audioCtxRef.current = new AudioCtx()
      }
    }
    if (audioCtxRef.current && audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume().catch(() => {})
    }
    return audioCtxRef.current
  }, [])

  // Synthesize multi-tone audio beeps using Web Audio API
  const playSynthesizedBeep = useCallback((pattern = 'medium') => {
    if (isMuted || volume <= 0) return
    try {
      const ctx = getAudioContext()
      if (!ctx) return

      const now = ctx.currentTime
      let tones = [] // list of { freq, start, duration }

      if (pattern === 'critical') {
        // High urgency 3-pulse alarm (880Hz)
        tones = [
          { freq: 880, start: now, dur: 0.1 },
          { freq: 880, start: now + 0.15, dur: 0.1 },
          { freq: 880, start: now + 0.3, dur: 0.15 },
        ]
      } else if (pattern === 'high') {
        // 2-pulse warning (660Hz)
        tones = [
          { freq: 660, start: now, dur: 0.12 },
          { freq: 660, start: now + 0.18, dur: 0.12 },
        ]
      } else if (pattern === 'medium') {
        // Single medium beep (520Hz)
        tones = [{ freq: 520, start: now, dur: 0.18 }]
      } else {
        // Low reminder (440Hz)
        tones = [{ freq: 440, start: now, dur: 0.15 }]
      }

      tones.forEach(({ freq, start, dur }) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.type = pattern === 'critical' ? 'sawtooth' : 'sine'
        osc.frequency.setValueAtTime(freq, start)

        gain.gain.setValueAtTime(0.001, start)
        gain.gain.exponentialRampToValueAtTime(volume * 0.4, start + 0.02)
        gain.gain.exponentialRampToValueAtTime(0.0001, start + dur)

        osc.connect(gain)
        gain.connect(ctx.destination)

        osc.start(start)
        osc.stop(start + dur + 0.05)
      })
      setAudioError(null)
    } catch (err) {
      console.warn('Audio playback not permitted or unavailable:', err)
      setAudioError('Audio device unavailable')
    }
  }, [getAudioContext, isMuted, volume])

  // Request browser notification permissions
  const toggleNotifications = async () => {
    if (!('Notification' in window)) {
      alert('This browser does not support desktop notifications.')
      return
    }
    if (Notification.permission === 'granted') {
      setBrowserNotifications(!browserNotifications)
    } else if (Notification.permission !== 'denied') {
      const permission = await Notification.requestPermission()
      if (permission === 'granted') {
        setBrowserNotifications(true)
      }
    } else {
      alert('Notifications are blocked in your browser settings. Please enable them to receive desktop alerts.')
    }
  }

  // Handle incoming alerts
  useEffect(() => {
    setDisplayAlerts(alerts.slice(-maxAlerts).reverse())

    const last = alerts[alerts.length - 1]
    if (!last) return

    // Determine sound pattern based on severity or event type
    const severity = last.severity || (last.details && last.details.severity) || 'medium'
    const eventType = last.event_type

    let pattern = 'medium'
    if (severity === 'critical' || eventType === 'suspicious_activity' || eventType === 'fight' || eventType === 'panic') {
      pattern = 'critical'
    } else if (severity === 'high' || eventType === 'fall' || eventType === 'overcrowding' || eventType === 'zone_violation') {
      pattern = 'high'
    } else if (severity === 'low') {
      pattern = 'low'
    }

    playSynthesizedBeep(pattern)

    // Trigger desktop browser notification
    if (browserNotifications && Notification.permission === 'granted') {
      try {
        new Notification(`Anomaly Alert: ${formatEventType(last.event_type)}`, {
          body: `Severity: ${severity.toUpperCase()} | Frame: ${last.frame_number}`,
          icon: '/favicon.ico',
        })
      } catch (_) {}
    }
  }, [alerts, maxAlerts, browserNotifications, playSynthesizedBeep])

  const handleAcknowledge = async (alertItem) => {
    const eventId = alertItem.event_id || (alertItem.details && alertItem.details.event_id)
    if (!eventId) return
    try {
      await axios.patch(`${apiBase}/api/events/${eventId}/acknowledge`, { acknowledged_by: 'operator' })
      setDisplayAlerts((prev) =>
        prev.map((a) => (a.event_id === eventId ? { ...a, acknowledged: true } : a))
      )
    } catch (e) {
      console.error('Failed to acknowledge event:', e)
    }
  }

  const getAlertClass = (alertItem) => {
    const severity = alertItem.severity || (alertItem.details && alertItem.details.severity) || 'medium'
    switch (severity) {
      case 'critical':
      case 'high':
        return 'alert-danger'
      case 'medium':
        return 'alert-warning'
      case 'low':
        return 'alert-info'
      default:
        return 'alert-danger'
    }
  }

  const getAlertIcon = (eventType) => {
    switch (eventType) {
      case 'overcrowding':
        return '👥'
      case 'loitering':
        return '⏱️'
      case 'zone_violation':
        return '🚫'
      case 'suspicious_activity':
      case 'fight':
        return '⚔️'
      case 'snatching':
        return '🏍️'
      case 'fall':
        return '🩹'
      case 'panic':
      case 'running':
        return '🏃'
      case 'custom_rule':
        return '⚡'
      default:
        return '⚠️'
    }
  }

  const formatEventType = (eventType) => {
    if (!eventType) return 'Alert'
    return eventType
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }

  return (
    <div className="alert-panel">
      <div className="alert-panel-header">
        <h3 className="panel-title">Recent Alerts</h3>
        <div className="alert-controls">
          <button
            className={`btn-icon ${isMuted ? 'muted' : ''}`}
            onClick={() => setIsMuted(!isMuted)}
            title={isMuted ? 'Unmute Audio' : 'Mute Audio'}
          >
            {isMuted ? '🔇' : '🔊'}
          </button>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={volume}
            onChange={(e) => {
              setVolume(parseFloat(e.target.value))
              if (isMuted) setIsMuted(false)
            }}
            className="volume-slider"
            title={`Volume: Math.round(volume * 100)%`}
          />
          <button
            className={`btn-icon ${browserNotifications ? 'active' : ''}`}
            onClick={toggleNotifications}
            title={browserNotifications ? 'Browser Notifications Enabled' : 'Enable Browser Notifications'}
          >
            🔔
          </button>
          <button
            className="btn-test-sound"
            onClick={() => playSynthesizedBeep('critical')}
            title="Test alert beep"
          >
            Test
          </button>
        </div>
      </div>

      {audioError && <div className="audio-notice">{audioError}</div>}

      {displayAlerts.length === 0 ? (
        <div className="no-alerts">No alerts detected</div>
      ) : (
        <div className="alerts-list">
          {displayAlerts.map((alert, idx) => {
            const severity = alert.severity || (alert.details && alert.details.severity) || 'medium'
            return (
              <div key={alert.event_id || idx} className={`alert ${getAlertClass(alert)}`}>
                <div className="alert-header">
                  <span className="alert-icon">{getAlertIcon(alert.event_type)}</span>
                  <span className="alert-type">{formatEventType(alert.event_type)}</span>
                  <span className={`severity-tag severity-${severity}`}>{severity.toUpperCase()}</span>
                  <span className="alert-time">
                    {new Date(alert.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div className="alert-details">
                  <span>Frame: {alert.frame_number}</span>
                  {alert.details && (
                    <>
                      {alert.details.track_id && <span> | ID: {alert.details.track_id}</span>}
                      {alert.details.current_count && <span> | Count: {alert.details.current_count}</span>}
                      {alert.details.subtype && <span> | Type: {formatEventType(alert.details.subtype)}</span>}
                      {alert.details.duration_seconds && (
                        <span> | Dwell: {Math.round(alert.details.duration_seconds)}s</span>
                      )}
                      {alert.details.message && <span> | {alert.details.message}</span>}
                    </>
                  )}
                  {alert.event_id && !alert.acknowledged && (
                    <button
                      className="btn-ack"
                      onClick={() => handleAcknowledge(alert)}
                      title="Acknowledge this alert"
                    >
                      Acknowledge
                    </button>
                  )}
                  {alert.acknowledged && <span className="ack-label">✓ Acknowledged</span>}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default AlertPanel
