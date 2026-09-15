/**
 * pages/Alerts.jsx — Screen 5
 * Full alerts list with filter by status, severity, vehicle number.
 * Acknowledge button per alert.
 */
import React, { useEffect, useState } from 'react'
import { getAlerts } from '../api/client'
import AlertList from '../components/AlertList'

export default function Alerts() {
  const [alerts, setAlerts]   = useState([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus]   = useState('')
  const [vehicle, setVehicle] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const res = await getAlerts({
        status: status || undefined,
        vehicle_number: vehicle || undefined,
        limit: 200,
      })
      setAlerts(res.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [status, vehicle])

  return (
    <div>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16 }}>
        <h1 style={h1}>🚨 Alerts</h1>
        <button style={btn} onClick={load}>↻ Refresh</button>
      </div>

      {/* Filters */}
      <div style={{ display:'flex', gap:12, marginBottom:16, flexWrap:'wrap' }}>
        <select style={inp} value={status} onChange={e => setStatus(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="NEW">New</option>
          <option value="ACKNOWLEDGED">Acknowledged</option>
          <option value="RESOLVED">Resolved</option>
        </select>
        <input
          style={{ ...inp, flex:'1 1 200px' }}
          placeholder="🔍 Filter by vehicle number…"
          value={vehicle}
          onChange={e => setVehicle(e.target.value)}
        />
      </div>

      <div style={card}>
        {loading ? <p>Loading…</p> : (
          <>
            <AlertList alerts={alerts} onRefresh={load} />
            <p style={{ color:'var(--muted)', fontSize:12, marginTop:10 }}>{alerts.length} alert(s)</p>
          </>
        )}
      </div>
    </div>
  )
}

const h1 = { fontSize:24, fontWeight:700 }
const card = { background:'var(--card-bg)', borderRadius:10, padding:20, boxShadow:'0 1px 4px rgba(0,0,0,.08)' }
const inp = { padding:'8px 12px', border:'1px solid var(--border)', borderRadius:6, fontSize:14 }
const btn = { background:'var(--primary)', color:'#fff', border:'none', borderRadius:6, padding:'8px 14px', fontSize:14, cursor:'pointer', fontWeight:600 }
