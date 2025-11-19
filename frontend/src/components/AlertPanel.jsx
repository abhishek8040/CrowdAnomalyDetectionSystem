import { useEffect, useState } from 'react'
import './AlertPanel.css'

const AlertPanel = ({ alerts, maxAlerts = 10 }) => {
  const [displayAlerts, setDisplayAlerts] = useState([])

  useEffect(() => {
    setDisplayAlerts(alerts.slice(-maxAlerts).reverse())
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
