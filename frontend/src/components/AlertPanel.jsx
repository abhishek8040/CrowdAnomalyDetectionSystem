import { useEffect, useState } from 'react'
import './AlertPanel.css'

const AlertPanel = ({ alerts, maxAlerts = 10 }) => {
  const [displayAlerts, setDisplayAlerts] = useState([])
  const [audio] = useState(() => {
    const a = new Audio()
    // gentle weep tone; user can replace with custom file in /frontend/public
    a.src = '/weep.mp3'
    a.loop = false
    a.volume = 0.4
    return a
  })

  useEffect(() => {
    setDisplayAlerts(alerts.slice(-maxAlerts).reverse())
    const last = alerts[alerts.length - 1]
    if (last && last.event_type === 'suspicious_activity') {
      try { audio.currentTime = 0; audio.play() } catch (_) {}
    }
  }, [alerts, maxAlerts])

  const getAlertClass = (eventType) => {
    switch (eventType) {
      case 'overcrowding':
        return 'alert-danger'
      case 'loitering':
        return 'alert-warning'
      case 'zone_violation':
        return 'alert-danger'
      case 'suspicious_activity':
        return 'alert-danger'
      default:
        return 'alert-info'
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
        return '⚠️'
      default:
        return 'ℹ️'
    }
  }

  const formatEventType = (eventType) => {
    return eventType
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }

  return (
    <div className="alert-panel">
      <h3 className="panel-title">Recent Alerts</h3>
      {displayAlerts.length === 0 ? (
        <div className="no-alerts">No alerts detected</div>
      ) : (
        <div className="alerts-list">
          {displayAlerts.map((alert, idx) => (
            <div key={idx} className={`alert ${getAlertClass(alert.event_type)}`}>
              <div className="alert-header">
                <span className="alert-icon">{getAlertIcon(alert.event_type)}</span>
                <span className="alert-type">{formatEventType(alert.event_type)}</span>
                <span className="alert-time">
                  {new Date(alert.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div className="alert-details">
                Frame: {alert.frame_number}
                {alert.details && (
                  <>
                    {alert.details.track_id && ` | ID: ${alert.details.track_id}`}
                    {alert.details.current_count && ` | Count: ${alert.details.current_count}`}
                    {alert.event_type === 'suspicious_activity' && alert.details.subtype && ` | Type: ${formatEventType(alert.details.subtype)}`}
                    {alert.event_type === 'suspicious_activity' && typeof alert.details.nearest_distance === 'number' && ` | Nearest: ${Math.round(alert.details.nearest_distance)}px`}
                    {alert.event_type === 'suspicious_activity' && typeof alert.details.arm_velocity === 'number' && ` | Arm v: ${alert.details.arm_velocity.toFixed(1)}`}
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default AlertPanel
