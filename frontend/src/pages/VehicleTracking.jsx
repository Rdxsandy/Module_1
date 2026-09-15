/**
 * pages/VehicleTracking.jsx — Screen 4
 * - Search by registration number
 * - Display timestamped camera history table
 * - Embedded mini-map with route polyline
 * - Shows watchlist status
 * - "Send new event" demo panel
 */
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getVehicleHistory, postEvent, getCameras } from '../api/client'
import MapView from '../components/MapView'
import VehicleRoute from '../components/VehicleRoute'

export default function VehicleTracking() {
  const [input, setInput]     = useState('DL01AB1234')
  const [result, setResult]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [fitRoute, setFitRoute] = useState(false)

  // Demo event sender
  const [cameras, setCameras] = useState([])
  const [evForm, setEvForm]   = useState({ camera_id:'7', vehicle_number:'DL01AB1234', latitude:'28.6200', longitude:'77.2150', confidence:'0.96', event_type:'ANPR' })
  const [evResult, setEvResult] = useState(null)
  const [showEventPanel, setShowEventPanel] = useState(false)
  const navigate = useNavigate()

  const search = async () => {
    setLoading(true); setError(''); setResult(null)
    try {
      const res = await getVehicleHistory(input.trim())
      setResult(res.data)
      setFitRoute(true)
    } catch {
      setError('No history found for this vehicle number.')
    } finally { setLoading(false) }
  }

  const sendEvent = async (e) => {
    e.preventDefault()
    const payload = {
      ...evForm,
      camera_id: parseInt(evForm.camera_id),
      latitude: parseFloat(evForm.latitude),
      longitude: parseFloat(evForm.longitude),
      confidence: parseFloat(evForm.confidence),
      event_time: new Date().toISOString(),
    }
    try {
      const res = await postEvent(payload)
      setEvResult(res.data)
      search() // refresh history
    } catch (err) {
      setEvResult({ error: err.response?.data?.detail || 'Error sending event' })
    }
  }

  return (
    <div>
      <h1 style={h1}>🚗 Vehicle Tracking</h1>

      {/* Search bar */}
      <div style={{ display:'flex', gap:10, marginBottom:20 }}>
        <input
          style={{ ...inp, flex:'1 1 260px' }}
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Enter registration number (e.g. DL01AB1234)"
          onKeyDown={e => e.key === 'Enter' && search()}
        />
        <button style={btn} onClick={search} disabled={loading}>
          {loading ? 'Tracking…' : '🔍 Track'}
        </button>
      </div>

      {error && <p style={{ color:'#e02424', marginBottom:12 }}>{error}</p>}

      {result && (
        <>
          {/* Watchlist badge */}
          <div style={{ marginBottom:16, display:'flex', gap:12, alignItems:'center', flexWrap:'wrap' }}>
            <span style={{ fontSize:18, fontWeight:700 }}>{result.vehicle_number}</span>
            {result.watchlist_status ? (
              <span style={{ background:'#e02424', color:'#fff', padding:'3px 12px', borderRadius:4, fontSize:13, fontWeight:600 }}>
                🚨 ON WATCHLIST ({result.watchlist_status.toUpperCase()})
              </span>
            ) : (
              <span style={{ background:'#0e9f6e', color:'#fff', padding:'3px 12px', borderRadius:4, fontSize:13, fontWeight:600 }}>
                ✅ Not on watchlist
              </span>
            )}
            {result.watchlist_reason && <span style={{ fontSize:13, color:'var(--muted)' }}>{result.watchlist_reason}</span>}
            <button style={{ ...btn, background:'#7c3aed', marginLeft:'auto' }} onClick={() => navigate(`/map?vehicle=${result.vehicle_number}`)}>
              View on Full Map
            </button>
          </div>

          {/* Mini map */}
          {result.history.length > 0 && (
            <div style={{ marginBottom:20 }}>
              <MapView height="300px">
                <VehicleRoute history={result.history} fitRoute={fitRoute} />
              </MapView>
              <p style={{ fontSize:12, color:'var(--muted)', marginTop:4 }}>
                🟢 Start &nbsp;🔴 End &nbsp;🔵 Intermediate stops
              </p>
            </div>
          )}

          {/* History table */}
          <div style={{ ...card, marginBottom:20, overflowX:'auto' }}>
            <h2 style={h2}>📋 Camera History ({result.history.length} stops)</h2>
            {result.history.length === 0 ? <p style={{ color:'var(--muted)' }}>No events recorded.</p> : (
              <table style={{ width:'100%', borderCollapse:'collapse', fontSize:14 }}>
                <thead>
                  <tr style={{ background:'#f8fafc', textAlign:'left' }}>
                    {['Stop','Camera','Time','Latitude','Longitude','Confidence'].map(col => (
                      <th key={col} style={th}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.history.map((h, idx) => (
                    <tr key={idx} style={{ borderBottom:'1px solid var(--border)' }}>
                      <td style={td}>{idx + 1}</td>
                      <td style={{ ...td, fontWeight:600 }}>{h.camera_name}</td>
                      <td style={td}>{new Date(h.event_time).toLocaleString()}</td>
                      <td style={td}>{h.latitude.toFixed(4)}</td>
                      <td style={td}>{h.longitude.toFixed(4)}</td>
                      <td style={td}>{h.confidence ? `${(h.confidence*100).toFixed(0)}%` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {/* Demo Event Sender */}
      <div style={card}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          <h2 style={h2}>🎬 Send Demo Event</h2>
          <button style={{ ...btn, fontSize:13, padding:'6px 12px' }} onClick={() => setShowEventPanel(v => !v)}>
            {showEventPanel ? 'Hide' : 'Show Panel'}
          </button>
        </div>
        {showEventPanel && (
          <form onSubmit={sendEvent} style={{ display:'flex', flexWrap:'wrap', gap:12, marginTop:12 }}>
            {[['camera_id','Camera ID'],['vehicle_number','Vehicle Number'],['latitude','Latitude'],['longitude','Longitude'],['confidence','Confidence']].map(([k,label]) => (
              <label key={k} style={formLabel}>
                {label}
                <input required style={inp} value={evForm[k]} onChange={e => setEvForm(f => ({...f,[k]:e.target.value}))} />
              </label>
            ))}
            <div style={{ width:'100%' }}>
              <button type="submit" style={{ ...btn, background:'#e02424' }}>🚀 Send Event & Match Watchlist</button>
            </div>
            {evResult && (
              <pre style={{ background:'#f8fafc', padding:12, borderRadius:6, fontSize:12, width:'100%', overflowX:'auto' }}>
                {JSON.stringify(evResult, null, 2)}
              </pre>
            )}
          </form>
        )}
      </div>
    </div>
  )
}

const h1 = { fontSize:24, fontWeight:700, marginBottom:16 }
const h2 = { fontSize:17, fontWeight:600, marginBottom:10 }
const card = { background:'var(--card-bg)', borderRadius:10, padding:20, boxShadow:'0 1px 4px rgba(0,0,0,.08)' }
const inp = { padding:'8px 12px', border:'1px solid var(--border)', borderRadius:6, fontSize:14, width:'100%' }
const btn = { background:'var(--primary)', color:'#fff', border:'none', borderRadius:6, padding:'9px 16px', fontSize:14, cursor:'pointer', fontWeight:600, whiteSpace:'nowrap' }
const th = { padding:'10px 12px', fontWeight:600, fontSize:13, color:'var(--muted)' }
const td = { padding:'10px 12px' }
const formLabel = { display:'flex', flexDirection:'column', gap:4, flex:'1 1 160px', fontSize:13, fontWeight:500 }
