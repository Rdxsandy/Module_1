/**
 * pages/MapPage.jsx — Screen 3: GIS Map
 * Displays all camera markers. If a vehicle is selected (via context or query param),
 * also shows the vehicle route polyline.
 */
import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMap, Circle } from 'react-leaflet'
import MapView from '../components/MapView'
import CameraMarker from '../components/CameraMarker'
import VehicleRoute from '../components/VehicleRoute'
import WatchlistMarker from '../components/WatchlistMarker'
import { getCameras, getVehicleHistory, getWatchlistLocations } from '../api/client'

// Fits the viewport to all camera markers so cameras added far outside the
// default Delhi view (typo'd or otherwise) are still visible on load.
function FitAllCameras({ cameras }) {
  const map = useMap()
  useEffect(() => {
    if (cameras.length === 0) return
    const bounds = cameras.map(c => [c.latitude, c.longitude])
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 })
  }, [cameras, map])
  return null
}

export default function MapPage() {
  const [cameras, setCameras] = useState([])
  const [watchlistLocations, setWatchlistLocations] = useState([])
  const [route, setRoute] = useState([])
  const [vehicle, setVehicle] = useState('')
  const [input, setInput] = useState('')
  const [fitRoute, setFitRoute] = useState(false)
  const [error, setError] = useState('')
  const [showCoverage, setShowCoverage] = useState(false)
  const [searchParams] = useSearchParams()

  useEffect(() => {
    getCameras().then(r => setCameras(r.data)).catch(console.error)
    loadWatchlistLocations()
    const v = searchParams.get('vehicle')
    if (v) { setInput(v); loadRoute(v) }
    const interval = setInterval(loadWatchlistLocations, 15000)
    return () => clearInterval(interval)
  }, [])

  const loadWatchlistLocations = () => {
    getWatchlistLocations().then(r => setWatchlistLocations(r.data)).catch(console.error)
  }

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
        <button
          style={{ ...btn, background: showCoverage ? '#0e9f6e' : '#64748b' }}
          onClick={() => setShowCoverage(v => !v)}
        >
          {showCoverage ? '🟢 Hide Coverage Layer' : '⚪ Show Coverage Layer'}
        </button>
      </div>

      {error && <p style={{ color:'#e02424', marginBottom:12 }}>{error}</p>}
      {vehicle && route.length > 0 && (
        <p style={{ marginBottom:12, color:'var(--muted)', fontSize:13 }}>
          Showing route for <strong>{vehicle}</strong> — {route.length} stops
        </p>
      )}

      <MapView height="60vh">
        {showCoverage && cameras.map(cam => (
          <Circle
            key={`coverage-${cam.id}`}
            center={[cam.latitude, cam.longitude]}
            radius={cam.coverage_radius_meters || 50}
            pathOptions={{ color: '#16a34a', fillColor: '#22c55e', fillOpacity: 0.2, weight: 1 }}
          />
        ))}
        {cameras.map(cam => <CameraMarker key={cam.id} camera={cam} />)}
        {watchlistLocations.map(entry => <WatchlistMarker key={entry.id} entry={entry} />)}
        {route.length === 0 && <FitAllCameras cameras={cameras} />}
        {route.length > 0 && <VehicleRoute history={route} fitRoute={fitRoute} />}
      </MapView>

      <p style={{ fontSize:12, color:'var(--muted)', marginTop:8 }}>
        📹 {cameras.length} cameras shown &nbsp;|&nbsp;
        🟢 Online &nbsp;🔴 Offline &nbsp;🟡 Maintenance &nbsp;|&nbsp;
        🚨 {watchlistLocations.filter(w => w.last_seen).length} watchlist vehicle{watchlistLocations.filter(w => w.last_seen).length === 1 ? '' : 's'} shown
      </p>
    </div>
  )
}

const h1 = { fontSize:24, fontWeight:700, marginBottom:16 }
const inp = { padding:'8px 12px', border:'1px solid var(--border)', borderRadius:6, fontSize:14 }
const btn = { background:'var(--primary)', color:'#fff', border:'none', borderRadius:6, padding:'9px 16px', fontSize:14, cursor:'pointer', fontWeight:600 }
