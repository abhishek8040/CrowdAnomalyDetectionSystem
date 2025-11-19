import { useState, useEffect } from 'react'
import './Events.css'

const Events = () => {
  const [events, setEvents] = useState([])
  const [filter, setFilter] = useState('all')
  const [selectedEvent, setSelectedEvent] = useState(null)

  // Load events from localStorage (in production, this would be from a database)
  useEffect(() => {
    const storedEvents = localStorage.getItem('anomalyEvents')
    if (storedEvents) {
      setEvents(JSON.parse(storedEvents))
    }
  }, [])

  const filteredEvents =
    filter === 'all' ? events : events.filter((e) => e.event_type === filter)

  const eventTypes = [
    { value: 'all', label: 'All Events' },
    { value: 'overcrowding', label: 'Overcrowding' },
    { value: 'loitering', label: 'Loitering' },
    { value: 'zone_violation', label: 'Zone Violations' },
    { value: 'suspicious_activity', label: 'Suspicious Activity' },
  ]

  const getEventClass = (eventType) => {
    switch (eventType) {
      case 'overcrowding':
        return 'event-danger'
      case 'loitering':
        return 'event-warning'
      case 'zone_violation':
        return 'event-danger'
      case 'suspicious_activity':
        return 'event-danger'
      default:
        return 'event-info'
    }
  }

  const formatEventType = (eventType) => {
    return eventType
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }

  return (
    <div className="events-page">
      <div className="events-header">
        <h1>Event History</h1>
        <div className="filter-section">
          <label>Filter by type:</label>
          <select value={filter} onChange={(e) => setFilter(e.target.value)} className="filter-select">
            {eventTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="events-grid">
        <div className="events-list">
          {filteredEvents.length === 0 ? (
            <div className="no-events">
              <p>No events found</p>
            </div>
          ) : (
            filteredEvents.map((event, idx) => (
              <div
                key={idx}
                className={`event-card ${getEventClass(event.event_type)} ${
                  selectedEvent === idx ? 'selected' : ''
                }`}
                onClick={() => setSelectedEvent(idx)}
              >
                <div className="event-header">
                  <span className="event-type">{formatEventType(event.event_type)}</span>
                  <span className="event-time">
                    {new Date(event.timestamp).toLocaleString()}
                  </span>
                </div>
                <div className="event-info">
                  <span>Frame: {event.frame_number}</span>
                  {event.details?.track_id && <span>Track ID: {event.details.track_id}</span>}
                </div>
              </div>
            ))
          )}
        </div>

        {selectedEvent !== null && filteredEvents[selectedEvent] && (
          <div className="event-detail">
            <h2>Event Details</h2>
            <div className="detail-content">
              <div className="detail-row">
                <span className="detail-label">Type:</span>
                <span className="detail-value">
                  {formatEventType(filteredEvents[selectedEvent].event_type)}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Timestamp:</span>
                <span className="detail-value">
                  {new Date(filteredEvents[selectedEvent].timestamp).toLocaleString()}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Frame:</span>
                <span className="detail-value">{filteredEvents[selectedEvent].frame_number}</span>
              </div>

              {filteredEvents[selectedEvent].details && (
                <div className="detail-section">
                  <h3>Additional Information</h3>
                  <pre className="detail-json">
                    {JSON.stringify(filteredEvents[selectedEvent].details, null, 2)}
                  </pre>
                </div>
              )}

              {filteredEvents[selectedEvent].snapshot && (
                <div className="detail-section">
                  <h3>Snapshot</h3>
                  <img
                    src={filteredEvents[selectedEvent].snapshot}
                    alt="Event snapshot"
                    className="event-snapshot"
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Events
