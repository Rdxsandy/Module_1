/**
 * pages/Events.jsx
 * Raw vehicle-event feed — lets you watch the simulator (or any event
 * source) write rows in near real time, with optional auto-refresh.
 */
import React, { useEffect, useRef, useState } from 'react'
import {
  MdOutlineReceiptLong,
  MdRefresh,
  MdSearch,
  MdOutlinePlayCircleOutline,
  MdOutlinePauseCircleOutline,
} from 'react-icons/md'
import { getEvents, getCameras } from '../api/client'

export default function Events() {
  const [events, setEvents]   = useState([])
  const [cameras, setCameras] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')
  const [filter, setFilter]   = useState('')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const intervalRef = useRef(null)

  const fetchEvents = async () => {
    setError('')
    try {
      const res = await getEvents({ limit: 100 })
      setEvents(res.data)
    } catch {
      setError('Failed to fetch events. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEvents()
    getCameras().then(res => {
      const map = {}
      res.data.forEach(c => { map[c.id] = c.name })
      setCameras(map)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchEvents, 3000)
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current)
    }
    return () => intervalRef.current && clearInterval(intervalRef.current)
  }, [autoRefresh])

  const filtered = events.filter(e =>
    filter === '' ||
    e.vehicle_number.toLowerCase().includes(filter.toLowerCase()) ||
    (cameras[e.camera_id] || '').toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.iconWrap}>
            <MdOutlineReceiptLong size={24} color="#1d4ed8" />
          </div>
          <div>
            <h1 style={styles.title}>Raw Events</h1>
            <p style={styles.subtitle}>Live ANPR event feed — camera detections as they arrive</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            style={{ ...styles.refreshBtn, ...(autoRefresh ? styles.refreshBtnActive : {}) }}
            onClick={() => setAutoRefresh(a => !a)}
            title={autoRefresh ? 'Pause auto-refresh' : 'Auto-refresh every 3s'}
          >
            {autoRefresh ? <MdOutlinePauseCircleOutline size={18} /> : <MdOutlinePlayCircleOutline size={18} />}
            {autoRefresh ? 'Live' : 'Auto-refresh'}
          </button>
          <button style={styles.refreshBtn} onClick={fetchEvents} title="Refresh">
            <MdRefresh size={18} />
            Refresh
          </button>
        </div>
      </div>

      <div style={styles.card}>
        <div style={styles.tableHeader}>
          <h2 style={styles.cardTitle}>
            Events
            <span style={styles.countBadge}>{filtered.length}</span>
          </h2>
          <div style={styles.searchWrap}>
            <MdSearch size={16} color="#94a3b8" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }} />
            <input
              placeholder="Search vehicle, camera…"
              value={filter}
              onChange={e => setFilter(e.target.value)}
              style={styles.searchInput}
            />
          </div>
        </div>

        {error && <div style={styles.errorBox}>{error}</div>}

        {loading ? (
          <div style={styles.emptyState}>Loading events…</div>
        ) : filtered.length === 0 ? (
          <div style={styles.emptyState}>
            <MdOutlineReceiptLong size={40} color="#cbd5e1" />
            <p style={{ margin: '8px 0 0', color: '#94a3b8' }}>No events found. Try starting the simulator.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  {['ID', 'Vehicle', 'Camera', 'Event Time', 'Lat/Lon', 'Confidence', 'Type'].map(h => (
                    <th key={h} style={styles.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map(e => (
                  <tr key={e.id} style={styles.tr}>
                    <td style={{ ...styles.td, color: '#94a3b8' }}>{e.id}</td>
                    <td style={styles.td}><span style={styles.plate}>{e.vehicle_number}</span></td>
                    <td style={styles.td}>{cameras[e.camera_id] || `Camera #${e.camera_id}`}</td>
                    <td style={{ ...styles.td, color: '#64748b', fontSize: 13 }}>
                      {new Date(e.event_time).toLocaleString()}
                    </td>
                    <td style={{ ...styles.td, fontFamily: 'monospace', fontSize: 12, color: '#64748b' }}>
                      {e.latitude.toFixed(4)}, {e.longitude.toFixed(4)}
                    </td>
                    <td style={styles.td}>
                      {e.confidence != null ? `${Math.round(e.confidence * 100)}%` : '—'}
                    </td>
                    <td style={styles.td}>
                      <span style={styles.typeBadge}>{e.event_type}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

const styles = {
  page: { padding: '24px', maxWidth: 1200, margin: '0 auto' },

  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 12 },
  headerLeft: { display: 'flex', alignItems: 'center', gap: 14 },
  iconWrap: { width: 44, height: 44, borderRadius: 12, background: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 22, fontWeight: 700, color: '#0f172a', margin: 0 },
  subtitle: { fontSize: 13, color: '#64748b', margin: '2px 0 0' },

  refreshBtn: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '8px 16px', borderRadius: 8,
    border: '1px solid #e2e8f0', background: '#fff',
    color: '#475569', fontSize: 14, fontWeight: 500,
    cursor: 'pointer',
  },
  refreshBtnActive: {
    background: '#f0fdf4', color: '#16a34a', border: '1px solid #bbf7d0',
  },

  card: {
    background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0',
    padding: '20px 24px', marginBottom: 20,
    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
  },
  cardTitle: { fontSize: 16, fontWeight: 600, color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: 8 },
  countBadge: {
    fontSize: 12, fontWeight: 600, color: '#1d4ed8',
    background: '#eff6ff', border: '1px solid #bfdbfe',
    borderRadius: 20, padding: '2px 8px',
  },

  tableHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 10 },
  searchWrap: { position: 'relative' },
  searchInput: {
    paddingLeft: 32, paddingRight: 12, paddingTop: 8, paddingBottom: 8,
    borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 13,
    background: '#f8fafc', outline: 'none', width: 220,
  },

  errorBox: {
    background: '#fef2f2', border: '1px solid #fecaca',
    color: '#dc2626', borderRadius: 8, padding: '12px 16px',
    fontSize: 14, marginBottom: 16,
  },
  emptyState: {
    textAlign: 'center', padding: '48px 20px',
    color: '#94a3b8', fontSize: 15,
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
  },

  table: { width: '100%', borderCollapse: 'collapse', fontSize: 14 },
  th: {
    padding: '10px 14px', background: '#f8fafc',
    color: '#475569', fontWeight: 600, fontSize: 12,
    textTransform: 'uppercase', letterSpacing: '0.04em',
    borderBottom: '2px solid #e2e8f0', textAlign: 'left',
  },
  tr: { borderBottom: '1px solid #f1f5f9' },
  td: { padding: '11px 14px', verticalAlign: 'middle', color: '#1e293b' },

  plate: { fontWeight: 600, fontFamily: 'monospace', fontSize: 13, color: '#1e293b' },
  typeBadge: {
    display: 'inline-flex', padding: '3px 10px', borderRadius: 20,
    fontSize: 12, fontWeight: 600, color: '#1d4ed8', background: '#eff6ff',
  },
}
