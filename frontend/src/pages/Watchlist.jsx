import React, { useState, useEffect } from 'react'
import {
  MdOutlinePlaylistAddCheck,
  MdOutlineAdd,
  MdDeleteOutline,
  MdDirectionsCar,
  MdPerson,
  MdCheckCircleOutline,
  MdHighlightOff,
  MdSearch,
  MdRefresh,
} from 'react-icons/md'
import {
  RiAlertLine,
  RiArrowUpLine,
  RiArrowDownLine,
  RiSubtractLine,
} from 'react-icons/ri'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'

const normalizePlate = (v) => v.toUpperCase().replace(/[^A-Z0-9]/g, '')

// ── Priority config ──────────────────────────────────────────────
const PRIORITY_CONFIG = {
  CRITICAL: { bg: '#fef2f2', color: '#dc2626', border: '#fecaca', Icon: RiAlertLine },
  HIGH:     { bg: '#fff7ed', color: '#ea580c', border: '#fed7aa', Icon: RiArrowUpLine },
  MEDIUM:   { bg: '#fefce8', color: '#ca8a04', border: '#fde68a', Icon: RiSubtractLine },
  LOW:      { bg: '#f0fdf4', color: '#16a34a', border: '#bbf7d0', Icon: RiArrowDownLine },
}

// ── Type config ──────────────────────────────────────────────────
const TYPE_CONFIG = {
  VEHICLE: { Icon: MdDirectionsCar, color: '#1d4ed8', bg: '#eff6ff' },
  PERSON:  { Icon: MdPerson,        color: '#7c3aed', bg: '#f5f3ff' },
}

export default function Watchlist() {
  const [entries, setEntries]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')
  const [filter, setFilter]     = useState('')
  const { user }                = useAuth()
  const isAdmin                 = user?.role === 'ADMIN'

  // Form state
  const [identifier,  setIdentifier]  = useState('')
  const [entityType,  setEntityType]  = useState('VEHICLE')
  const [priority,    setPriority]    = useState('HIGH')
  const [description, setDescription] = useState('')
  const [submitting,  setSubmitting]  = useState(false)
  const [modal, setModal] = useState({ open: false, title: '', message: '', variant: 'info' })

  const fetchWatchlist = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get('/watchlist')
      setEntries(res.data)
    } catch {
      setError('Failed to fetch watchlist. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchWatchlist() }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!identifier.trim()) return

    const normalised = normalizePlate(identifier)
    const duplicate = entries.find(en => en.active && en.identifier === normalised)
    if (duplicate) {
      setModal({
        open: true,
        title: 'Already on Watchlist',
        message: `${normalised} is already an active entry in the watchlist.`,
        variant: 'warning',
      })
      return
    }

    setSubmitting(true)
    try {
      await api.post('/watchlist', {
        identifier: identifier.trim(),
        entity_type: entityType,
        priority,
        description,
        active: true,
      })
      setIdentifier('')
      setDescription('')
      fetchWatchlist()
      setModal({
        open: true,
        title: 'Added to Watchlist',
        message: `${normalised} was added to the watchlist successfully.`,
        variant: 'success',
      })
    } catch (err) {
      const detail = err.response?.data?.detail
      setModal({
        open: true,
        title: 'Failed to Add Entry',
        message: Array.isArray(detail) ? detail.map(d => d.msg).join('\n') : detail || 'Please try again.',
        variant: 'error',
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Remove this entry from the watchlist?')) return
    try {
      await api.delete(`/watchlist/${id}`)
      fetchWatchlist()
      setModal({ open: true, title: 'Entry Removed', message: 'The watchlist entry was removed successfully.', variant: 'success' })
    } catch {
      setModal({ open: true, title: 'Failed to Remove Entry', message: 'Please try again.', variant: 'error' })
    }
  }

  const filtered = entries.filter(e =>
    filter === '' ||
    e.identifier.toLowerCase().includes(filter.toLowerCase()) ||
    e.entity_type.toLowerCase().includes(filter.toLowerCase()) ||
    e.priority.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div style={styles.page}>

      {/* ── Header ── */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.iconWrap}>
            <MdOutlinePlaylistAddCheck size={24} color="#1d4ed8" />
          </div>
          <div>
            <h1 style={styles.title}>Watchlist Registry</h1>
            <p style={styles.subtitle}>
              Monitor flagged vehicles &amp; persons across all cameras
            </p>
          </div>
        </div>
        <button style={styles.refreshBtn} onClick={fetchWatchlist} title="Refresh">
          <MdRefresh size={18} />
          Refresh
        </button>
      </div>

      {/* ── Stats row ── */}
      <div style={styles.statsRow}>
        {[
          { label: 'Total Entries', value: entries.length, color: '#1d4ed8' },
          { label: 'Active',        value: entries.filter(e => e.active).length,  color: '#16a34a' },
          { label: 'Critical / High', value: entries.filter(e => ['CRITICAL','HIGH'].includes(e.priority)).length, color: '#dc2626' },
          { label: 'Vehicles',      value: entries.filter(e => e.entity_type === 'VEHICLE').length, color: '#7c3aed' },
        ].map(s => (
          <div key={s.label} style={styles.statCard}>
            <span style={{ ...styles.statValue, color: s.color }}>{s.value}</span>
            <span style={styles.statLabel}>{s.label}</span>
          </div>
        ))}
      </div>

      {/* ── Add Form (ADMIN only) ── */}
      {isAdmin && (
        <div style={styles.card}>
          <div style={styles.cardHeader}>
            <MdOutlineAdd size={20} color="#1d4ed8" />
            <h2 style={styles.cardTitle}>Add to Watchlist</h2>
          </div>
          <form onSubmit={handleSubmit} style={styles.form}>
            <div style={styles.formGrid}>
              <label style={styles.label}>
                Identifier *
                <input
                  required
                  placeholder="e.g. DL01AB1234"
                  value={identifier}
                  onChange={e => setIdentifier(e.target.value)}
                  style={styles.input}
                />
              </label>
              <label style={styles.label}>
                Type
                <select value={entityType} onChange={e => setEntityType(e.target.value)} style={styles.input}>
                  <option value="VEHICLE">VEHICLE</option>
                  <option value="PERSON">PERSON</option>
                </select>
              </label>
              <label style={styles.label}>
                Priority
                <select value={priority} onChange={e => setPriority(e.target.value)} style={styles.input}>
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </label>
              <label style={styles.label}>
                Description
                <input
                  placeholder="Reason / notes (optional)"
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  style={styles.input}
                />
              </label>
            </div>
            <button type="submit" disabled={submitting} style={styles.addBtn}>
              <MdOutlineAdd size={18} />
              {submitting ? 'Adding…' : 'Add Entry'}
            </button>
          </form>
        </div>
      )}

      {/* ── Table Card ── */}
      <div style={styles.card}>
        {/* Search bar */}
        <div style={styles.tableHeader}>
          <h2 style={styles.cardTitle}>
            Watchlist Entries
            <span style={styles.countBadge}>{filtered.length}</span>
          </h2>
          <div style={styles.searchWrap}>
            <MdSearch size={16} color="#94a3b8" style={{ position:'absolute', left:10, top:'50%', transform:'translateY(-50%)' }} />
            <input
              placeholder="Search identifier, type, priority…"
              value={filter}
              onChange={e => setFilter(e.target.value)}
              style={styles.searchInput}
            />
          </div>
        </div>

        {/* Error */}
        {error && (
          <div style={styles.errorBox}>
            <MdHighlightOff size={18} />
            {error}
          </div>
        )}

        {/* Loading */}
        {loading ? (
          <div style={styles.emptyState}>Loading watchlist…</div>
        ) : filtered.length === 0 ? (
          <div style={styles.emptyState}>
            <MdOutlinePlaylistAddCheck size={40} color="#cbd5e1" />
            <p style={{ margin:'8px 0 0', color:'#94a3b8' }}>No watchlist entries found.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  {['Identifier', 'Type', 'Priority', 'Description', 'Status', isAdmin ? 'Actions' : ''].map(h => h && (
                    <th key={h} style={styles.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map(entry => {
                  const pc   = PRIORITY_CONFIG[entry.priority] || PRIORITY_CONFIG.MEDIUM
                  const tc   = TYPE_CONFIG[entry.entity_type]  || TYPE_CONFIG.VEHICLE
                  const PIcon = pc.Icon
                  const TIcon = tc.Icon
                  return (
                    <tr key={entry.id} style={styles.tr}>
                      <td style={styles.td}>
                        <span style={styles.identifierText}>{entry.identifier}</span>
                      </td>
                      <td style={styles.td}>
                        <span style={{ ...styles.typeBadge, color: tc.color, background: tc.bg }}>
                          <TIcon size={13} />
                          {entry.entity_type}
                        </span>
                      </td>
                      <td style={styles.td}>
                        <span style={{ ...styles.priorityBadge, color: pc.color, background: pc.bg, border: `1px solid ${pc.border}` }}>
                          <PIcon size={12} />
                          {entry.priority}
                        </span>
                      </td>
                      <td style={{ ...styles.td, color:'#64748b', maxWidth: 280 }}>
                        {entry.description || <span style={{ color:'#cbd5e1' }}>—</span>}
                      </td>
                      <td style={styles.td}>
                        {entry.active ? (
                          <span style={styles.statusActive}>
                            <MdCheckCircleOutline size={13} /> Active
                          </span>
                        ) : (
                          <span style={styles.statusInactive}>
                            <MdHighlightOff size={13} /> Inactive
                          </span>
                        )}
                      </td>
                      {isAdmin && (
                        <td style={styles.td}>
                          <button
                            onClick={() => handleDelete(entry.id)}
                            disabled={!entry.active}
                            style={entry.active ? styles.removeBtn : styles.removeBtnDisabled}
                            title="Remove from watchlist"
                          >
                            <MdDeleteOutline size={15} />
                            Remove
                          </button>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal
        open={modal.open}
        title={modal.title}
        message={modal.message}
        variant={modal.variant}
        autoCloseMs={modal.variant === 'success' ? 2000 : undefined}
        onClose={() => setModal(m => ({ ...m, open: false }))}
      />
    </div>
  )
}

// ── Styles ──────────────────────────────────────────────────────
const styles = {
  page: { padding: '24px', maxWidth: 1100, margin: '0 auto' },

  header: { display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:24 },
  headerLeft: { display:'flex', alignItems:'center', gap:14 },
  iconWrap: { width:44, height:44, borderRadius:12, background:'#eff6ff', display:'flex', alignItems:'center', justifyContent:'center' },
  title: { fontSize:22, fontWeight:700, color:'#0f172a', margin:0 },
  subtitle: { fontSize:13, color:'#64748b', margin:'2px 0 0' },

  refreshBtn: {
    display:'flex', alignItems:'center', gap:6,
    padding:'8px 16px', borderRadius:8,
    border:'1px solid #e2e8f0', background:'#fff',
    color:'#475569', fontSize:14, fontWeight:500,
    cursor:'pointer',
  },

  statsRow: { display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12, marginBottom:20 },
  statCard: {
    background:'#fff', borderRadius:12, padding:'16px 20px',
    border:'1px solid #e2e8f0',
    display:'flex', flexDirection:'column', gap:4,
  },
  statValue: { fontSize:26, fontWeight:700 },
  statLabel: { fontSize:12, color:'#94a3b8', fontWeight:500 },

  card: {
    background:'#fff', borderRadius:12, border:'1px solid #e2e8f0',
    padding:'20px 24px', marginBottom:20,
    boxShadow:'0 1px 3px rgba(0,0,0,0.05)',
  },
  cardHeader: { display:'flex', alignItems:'center', gap:8, marginBottom:16 },
  cardTitle: { fontSize:16, fontWeight:600, color:'#0f172a', margin:0, display:'flex', alignItems:'center', gap:8 },
  countBadge: {
    fontSize:12, fontWeight:600, color:'#1d4ed8',
    background:'#eff6ff', border:'1px solid #bfdbfe',
    borderRadius:20, padding:'2px 8px',
  },

  form: {},
  formGrid: { display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(200px,1fr))', gap:12, marginBottom:16 },
  label: { display:'flex', flexDirection:'column', gap:5, fontSize:12, fontWeight:600, color:'#475569' },
  input: {
    padding:'9px 12px', borderRadius:8, border:'1px solid #e2e8f0',
    fontSize:14, color:'#0f172a', outline:'none',
    background:'#f8fafc', fontFamily:'inherit',
  },
  addBtn: {
    display:'inline-flex', alignItems:'center', gap:6,
    padding:'9px 20px', borderRadius:8,
    background:'#1d4ed8', color:'#fff', border:'none',
    fontSize:14, fontWeight:600, cursor:'pointer',
  },

  tableHeader: { display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16, flexWrap:'wrap', gap:10 },
  searchWrap: { position:'relative' },
  searchInput: {
    paddingLeft:32, paddingRight:12, paddingTop:8, paddingBottom:8,
    borderRadius:8, border:'1px solid #e2e8f0', fontSize:13,
    background:'#f8fafc', outline:'none', width:220,
  },

  errorBox: {
    display:'flex', alignItems:'center', gap:8,
    background:'#fef2f2', border:'1px solid #fecaca',
    color:'#dc2626', borderRadius:8, padding:'12px 16px',
    fontSize:14, marginBottom:16,
  },
  emptyState: {
    textAlign:'center', padding:'48px 20px',
    color:'#94a3b8', fontSize:15,
    display:'flex', flexDirection:'column', alignItems:'center', gap:4,
  },

  table: { width:'100%', borderCollapse:'collapse', fontSize:14 },
  th: {
    padding:'10px 14px', background:'#f8fafc',
    color:'#475569', fontWeight:600, fontSize:12,
    textTransform:'uppercase', letterSpacing:'0.04em',
    borderBottom:'2px solid #e2e8f0', textAlign:'left',
  },
  tr: { borderBottom:'1px solid #f1f5f9', transition:'background 0.15s' },
  td: { padding:'13px 14px', verticalAlign:'middle', color:'#1e293b' },

  identifierText: { fontWeight:600, fontFamily:'monospace', fontSize:14, color:'#1e293b' },

  typeBadge: {
    display:'inline-flex', alignItems:'center', gap:4,
    padding:'3px 10px', borderRadius:20, fontSize:12, fontWeight:600,
  },
  priorityBadge: {
    display:'inline-flex', alignItems:'center', gap:4,
    padding:'3px 10px', borderRadius:20, fontSize:12, fontWeight:700,
  },

  statusActive: {
    display:'inline-flex', alignItems:'center', gap:4,
    color:'#16a34a', background:'#f0fdf4',
    border:'1px solid #bbf7d0', borderRadius:20,
    padding:'3px 10px', fontSize:12, fontWeight:600,
  },
  statusInactive: {
    display:'inline-flex', alignItems:'center', gap:4,
    color:'#dc2626', background:'#fef2f2',
    border:'1px solid #fecaca', borderRadius:20,
    padding:'3px 10px', fontSize:12, fontWeight:600,
  },

  removeBtn: {
    display:'inline-flex', alignItems:'center', gap:5,
    padding:'6px 12px', borderRadius:7,
    background:'#fef2f2', color:'#dc2626',
    border:'1px solid #fecaca', fontSize:12,
    fontWeight:600, cursor:'pointer',
  },
  removeBtnDisabled: {
    display:'inline-flex', alignItems:'center', gap:5,
    padding:'6px 12px', borderRadius:7,
    background:'#f8fafc', color:'#cbd5e1',
    border:'1px solid #e2e8f0', fontSize:12,
    fontWeight:600, cursor:'not-allowed',
  },
}
