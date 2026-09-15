/**
 * pages/MapPage.jsx — Screen 3: GIS Map
 * Displays all camera markers. If a vehicle is selected (via context or query param),
 * also shows the vehicle route polyline.
 */
import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import MapView from '../components/MapView'
import CameraMarker from '../components/CameraMarker'
import VehicleRoute from '../components/VehicleRoute'
import { getCameras, getVehicleHistory } from '../api/client'

export default function MapPage() {
  const [cameras, setCameras] = useState([])
  const [route, setRoute] = useState([])
  const [vehicle, setVehicle] = useState('')
  const [input, setInput] = useState('')
  const [fitRoute, setFitRoute] = useState(false)
  const [error, setError] = useState('')
  const [searchParams] = useSearchParams()

  useEffect(() => {
    getCameras().then(r => setCameras(r.data)).catch(console.error)
    const v = searchParams.get('vehicle')
    if (v) { setInput(v); loadRoute(v) }
  }, [])

  const loadRoute = async (vn) => {
    setError('')
    try {
      const res = await getVehicleHistory(vn || input)
      setVehicle(vn || input)
      setRoute(res.data.history)
      setFitRoute(true)
    } catch {
      setError('Vehicle not found or no history available.')
      setRoute([])
    }
  }

  const clearRoute = () => { setRoute([]); setVehicle(''); setInput(''); setFitRoute(false) }

  return (
    <div>
      <h1 style={h1}>🗺️ GIS Map</h1>

      {/* Vehicle route search */}
      <div style={{ display:'flex', gap:10, marginBottom:16, flexWrap:'wrap', alignItems:'center' }}>
        <input
          placeholder="Enter vehicle number to show route (e.g. DL01AB1234)"
          style={{ ...inp, flex:'1 1 260px' }}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && loadRoute()}
        />
        <button style={btn} onClick={() => loadRoute()}>Show Route</button>
        {route.length > 0 && <button style={{ ...btn, background:'#e02424' }} onClick={clearRoute}>Clear Route</button>}
        {route.length > 0 && <button style={{ ...btn, background:'#0e9f6e' }} onClick={() => setFitRoute(true)}>Fit Route</button>}
      </div>

      {error && <p style={{ color:'#e02424', marginBottom:12 }}>{error}</p>}
      {vehicle && route.length > 0 && (
        <p style={{ marginBottom:12, color:'var(--muted)', fontSize:13 }}>
          Showing route for <strong>{vehicle}</strong> — {route.length} stops
        </p>
      )}

      <MapView height="60vh">
        {cameras.map(cam => <CameraMarker key={cam.id} camera={cam} />)}
        {route.length > 0 && <VehicleRoute history={route} fitRoute={fitRoute} />}
      </MapView>

      <p style={{ fontSize:12, color:'var(--muted)', marginTop:8 }}>
        📹 {cameras.length} cameras shown &nbsp;|&nbsp;
        🟢 Online &nbsp;🔴 Offline &nbsp;🟡 Maintenance
      </p>
    </div>
  )
}

const h1 = { fontSize:24, fontWeight:700, marginBottom:16 }
const inp = { padding:'8px 12px', border:'1px solid var(--border)', borderRadius:6, fontSize:14 }
const btn = { background:'var(--primary)', color:'#fff', border:'none', borderRadius:6, padding:'9px 16px', fontSize:14, cursor:'pointer', fontWeight:600 }
