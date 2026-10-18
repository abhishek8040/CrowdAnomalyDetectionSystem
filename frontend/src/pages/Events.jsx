import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import './Events.css'

const Events = () => {
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  const [events, setEvents] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [summary, setSummary] = useState({ total_events: 0, by_type: {}, by_severity: {}, by_status: {} })
  const [selectedEventIndex, setSelectedEventIndex] = useState(null)
  const [loading, setLoading] = useState(false)
  const [resolutionNotes, setResolutionNotes] = useState('')

  // Filters
  const [filterType, setFilterType] = useState('all')
  const [filterSeverity, setFilterSeverity] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  // Fetch events from backend API
  const fetchEvents = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        limit: 100,
        offset: 0,
      }
      if (filterType !== 'all') params.event_type = filterType
      if (filterSeverity !== 'all') params.severity = filterSeverity
      if (filterStatus !== 'all') params.status = filterStatus
      if (searchQuery.trim()) params.search = searchQuery.trim()
      if (startDate) params.start_date = new Date(startDate).toISOString()
      if (endDate) params.end_date = new Date(endDate).toISOString()

      const res = await axios.get(`${API_BASE}/api/events/`, { params })
      setEvents(res.data.events || [])
      setTotalCount(res.data.total || 0)
      if (res.data.events && res.data.events.length > 0 && selectedEventIndex === null) {
        setSelectedEventIndex(0)
      }
    } catch (e) {
      console.error('Failed to fetch events:', e)
    } finally {
      setLoading(false)
    }
  }, [API_BASE, filterType, filterSeverity, filterStatus, searchQuery, startDate, endDate, selectedEventIndex])

  // Fetch summary counts
  const fetchSummary = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/events/stats`)
      setSummary(res.data)
    } catch (e) {
      console.error('Failed to fetch event stats:', e)
    }
  }, [API_BASE])

  useEffect(() => {
    fetchEvents()
    fetchSummary()
  }, [fetchEvents, fetchSummary])

  const selectedEvent = selectedEventIndex !== null && events[selectedEventIndex] ? events[selectedEventIndex] : null

  // Acknowledge alert
  const handleAcknowledge = async (eventId) => {
    try {
      await axios.patch(`${API_BASE}/api/events/${eventId}/acknowledge`, { acknowledged_by: 'operator' })
      fetchEvents()
      fetchSummary()
    } catch (e) {
      alert('Failed to acknowledge event: ' + e.message)
    }
  }

  // Resolve alert
  const handleResolve = async (eventId) => {
    try {
      await axios.patch(`${API_BASE}/api/events/${eventId}/resolve`, { notes: resolutionNotes })
      setResolutionNotes('')
      fetchEvents()
      fetchSummary()
    } catch (e) {
      alert('Failed to resolve event: ' + e.message)
    }
  }

  // Delete event
  const handleDelete = async (eventId) => {
    if (!window.confirm('Are you sure you want to delete this event record?')) return
    try {
      await axios.delete(`${API_BASE}/api/events/${eventId}`)
      setSelectedEventIndex(null)
      fetchEvents()
      fetchSummary()
    } catch (e) {
      alert('Failed to delete event: ' + e.message)
    }
  }

  // Clear all events
  const handleClearAll = async () => {
    if (!window.confirm('Are you sure you want to permanently clear ALL historical events?')) return
    try {
      await axios.delete(`${API_BASE}/api/events/`)
      setSelectedEventIndex(null)
      fetchEvents()
      fetchSummary()
    } catch (e) {
      alert('Failed to clear events: ' + e.message)
    }
  }

  // Export to CSV
  const exportToCSV = () => {
    if (events.length === 0) {
      alert('No events to export')
      return
    }
    const headers = ['Event ID', 'Type', 'Severity', 'Status', 'Timestamp', 'Frame', 'Camera ID', 'Details']
    const rows = events.map((e) => [
      e.event_id,
      e.event_type,
      e.severity,
      e.status,
      e.timestamp,
      e.frame_number,
      e.camera_id,
      JSON.stringify(e.details || {}).replace(/"/g, '""'),
    ])
    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((r) => `"${r.join('","')}"`)].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `anomaly_events_${Date.now()}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // Export to JSON
  const exportToJSON = () => {
    if (events.length === 0) {
      alert('No events to export')
      return
    }
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(events, null, 2))
    const dlAnchor = document.createElement('a')
    dlAnchor.setAttribute('href', dataStr)
    dlAnchor.setAttribute('download', `anomaly_events_${Date.now()}.json`)
    dlAnchor.click()
    dlAnchor.remove()
  }

  const formatEventType = (type) => {
    if (!type) return 'Unknown'
    return type
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ')
  }

  const getEventClass = (event) => {
    const sev = event.severity || 'medium'
    if (sev === 'critical') return 'event-critical'
    if (sev === 'high') return 'event-danger'
    if (sev === 'medium') return 'event-warning'
    return 'event-info'
  }

  return (
    <div className="events-page">
      <div className="events-header">
        <div>
          <h1>Incident Event History</h1>
          <p className="subtitle">Real-time audit log of all detected public anomalies and security events</p>
        </div>
        <div className="header-actions">
          <button className="btn btn-secondary" onClick={exportToCSV}>Export CSV</button>
          <button className="btn btn-secondary" onClick={exportToJSON}>Export JSON</button>
          <button className="btn btn-danger" onClick={handleClearAll}>Clear Log</button>
        </div>
      </div>

      {/* Stats Summary Bar */}
      <div className="stats-summary-bar">
        <div className="stat-pill">
          <span className="stat-pill-label">Total Logged</span>
          <span className="stat-pill-value">{summary.total_events || 0}</span>
        </div>
        <div className="stat-pill">
          <span className="stat-pill-label">New / Pending</span>
          <span className="stat-pill-value status-new">{summary.by_status?.new || 0}</span>
        </div>
        <div className="stat-pill">
          <span className="stat-pill-label">Acknowledged</span>
          <span className="stat-pill-value status-ack">{summary.by_status?.acknowledged || 0}</span>
        </div>
        <div className="stat-pill">
          <span className="stat-pill-label">Resolved</span>
          <span className="stat-pill-value status-res">{summary.by_status?.resolved || 0}</span>
        </div>
        <div className="stat-pill">
          <span className="stat-pill-label">Critical</span>
          <span className="stat-pill-value sev-crit">{summary.by_severity?.critical || 0}</span>
        </div>
      </div>

      {/* Filter Section */}
      <div className="filter-panel card">
        <div className="filter-grid">
          <div className="filter-group">
            <label>Search Query</label>
            <input
              type="text"
              placeholder="Filter by keyword, track ID, details..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label>Event Category</label>
            <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="filter-select">
              <option value="all">All Categories</option>
              <option value="snatching">🏍️ Drive-by Snatching / Theft</option>
              <option value="overcrowding">Overcrowding</option>
              <option value="loitering">Loitering</option>
              <option value="zone_violation">Zone Violations</option>
              <option value="suspicious_activity">Physical Altercation</option>
              <option value="fall">Fall / Person Down</option>
              <option value="panic">Panic / Crowd Dispersion</option>
              <option value="running">Rapid Running</option>
              <option value="custom_rule">Custom Rules</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Severity Level</label>
            <select value={filterSeverity} onChange={(e) => setFilterSeverity(e.target.value)} className="filter-select">
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Status</label>
            <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="filter-select">
              <option value="all">All Statuses</option>
              <option value="new">New (Unacknowledged)</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Grid: Event List & Details */}
      <div className="events-grid">
        <div className="events-list-container">
          <div className="list-status-header">
            <span>Showing {events.length} of {totalCount} incident(s)</span>
            {loading && <span className="loading-badge">Refreshing...</span>}
          </div>

          <div className="events-list">
            {events.length === 0 ? (
              <div className="no-events">
                <p>No matching events found</p>
                <small>Try adjusting your search criteria or triggering a detection</small>
              </div>
            ) : (
              events.map((event, idx) => (
                <div
                  key={event.event_id || idx}
                  className={`event-card ${getEventClass(event)} ${
                    selectedEventIndex === idx ? 'selected' : ''
                  }`}
                  onClick={() => setSelectedEventIndex(idx)}
                >
                  <div className="event-header">
                    <span className="event-type">{formatEventType(event.event_type)}</span>
                    <span className={`status-badge status-${event.status}`}>{event.status.toUpperCase()}</span>
                    <span className="event-time">{new Date(event.timestamp).toLocaleString()}</span>
                  </div>
                  <div className="event-info">
                    <span>Severity: <strong>{event.severity?.toUpperCase()}</strong></span>
                    <span>Frame: {event.frame_number}</span>
                    <span>Camera: {event.camera_id}</span>
                    {event.details?.track_id && <span>Track ID: #{event.details.track_id}</span>}
                    {event.details?.suspect_id && (
                      <span style={{ color: '#fca5a5' }}>
                        Suspect: #{event.details.suspect_id} ({event.details.suspect_class}) ➔ Victim: #{event.details.victim_id}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Selected Event Details Panel */}
        <div className="event-detail-panel">
          {selectedEvent ? (
            <div className="event-detail">
              <div className="detail-header">
                <h2>Incident #{selectedEvent.event_id?.slice(0, 8)}</h2>
                <div className="detail-actions">
                  {selectedEvent.status === 'new' && (
                    <button
                      className="btn btn-primary"
                      onClick={() => handleAcknowledge(selectedEvent.event_id)}
                    >
                      Acknowledge
                    </button>
                  )}
                  {selectedEvent.status !== 'resolved' && (
                    <button
                      className="btn btn-success"
                      onClick={() => handleResolve(selectedEvent.event_id)}
                    >
                      Mark Resolved
                    </button>
                  )}
                  <button
                    className="btn btn-danger"
                    onClick={() => handleDelete(selectedEvent.event_id)}
                  >
                    Delete
                  </button>
                </div>
              </div>

              <div className="detail-content">
                <div className="detail-row">
                  <span className="detail-label">Event Type</span>
                  <span className="detail-value">{formatEventType(selectedEvent.event_type)}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Severity</span>
                  <span className={`detail-value severity-badge-${selectedEvent.severity}`}>
                    {selectedEvent.severity?.toUpperCase()}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Status</span>
                  <span className="detail-value">{selectedEvent.status?.toUpperCase()}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Timestamp</span>
                  <span className="detail-value">{new Date(selectedEvent.timestamp).toLocaleString()}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Frame Number</span>
                  <span className="detail-value">{selectedEvent.frame_number}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Camera Identifier</span>
                  <span className="detail-value">{selectedEvent.camera_id}</span>
                </div>
                {selectedEvent.acknowledged_at && (
                  <div className="detail-row">
                    <span className="detail-label">Acknowledged At</span>
                    <span className="detail-value">
                      {new Date(selectedEvent.acknowledged_at).toLocaleString()} by {selectedEvent.acknowledged_by || 'operator'}
                    </span>
                  </div>
                )}
                {selectedEvent.resolved_at && (
                  <div className="detail-row">
                    <span className="detail-label">Resolved At</span>
                    <span className="detail-value">
                      {new Date(selectedEvent.resolved_at).toLocaleString()}
                    </span>
                  </div>
                )}

                {/* Operator Resolution Note input */}
                {selectedEvent.status !== 'resolved' && (
                  <div className="resolution-input-section">
                    <label>Operator Resolution Notes:</label>
                    <textarea
                      placeholder="Add investigation notes or action taken..."
                      value={resolutionNotes}
                      onChange={(e) => setResolutionNotes(e.target.value)}
                      rows={2}
                      className="notes-textarea"
                    />
                  </div>
                )}

                {selectedEvent.resolution_notes && (
                  <div className="detail-row">
                    <span className="detail-label">Resolution Notes</span>
                    <span className="detail-value">{selectedEvent.resolution_notes}</span>
                  </div>
                )}

                {/* Incident Snapshot Image */}
                {selectedEvent.snapshot && (
                  <div className="detail-section">
                    <h3>Incident Camera Snapshot</h3>
                    <img
                      src={selectedEvent.snapshot}
                      alt="Incident Snapshot"
                      className="event-snapshot"
                    />
                  </div>
                )}

                {/* Structured JSON Diagnostics */}
                {selectedEvent.details && (
                  <div className="detail-section">
                    <h3>Algorithmic Diagnostic Data</h3>
                    <pre className="detail-json">
                      {JSON.stringify(selectedEvent.details, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="event-detail empty-detail">
              <p>Select an incident from the log to view details, snapshots, and operator actions.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Events
