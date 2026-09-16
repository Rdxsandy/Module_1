/**
 * components/CameraMarker.jsx
 * A single Leaflet marker for a camera.
 * Popup shows name, department, type, status.
 * Color-coded by status: green=online, red=offline, orange=maintenance.
 */
import React from 'react'
import { Marker, Popup } from 'react-leaflet'
import L from 'leaflet'

const statusColors = { online: '#0e9f6e', offline: '#e02424', maintenance: '#ff8800' }

function makeIcon(status) {
  const color = statusColors[String(status).toLowerCase()] || '#1a56db'
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="36" viewBox="0 0 28 36">
    <path d="M14 0C6.27 0 0 6.27 0 14c0 10.5 14 22 14 22S28 24.5 28 14C28 6.27 21.73 0 14 0z" fill="${color}"/>
    <circle cx="14" cy="14" r="6" fill="white"/>
  </svg>`
  return L.divIcon({
    html: svg,
    iconSize: [28, 36],
    iconAnchor: [14, 36],
    popupAnchor: [0, -36],
    className: '',
  })
}

export default function CameraMarker({ camera, onClick }) {
  return (
    <Marker
      position={[camera.latitude, camera.longitude]}
      icon={makeIcon(camera.status)}
      eventHandlers={{ click: () => onClick?.(camera) }}
    >
      <Popup>
        <div style={{ minWidth: 180 }}>
          <strong style={{ fontSize: 15 }}>{camera.name}</strong>
          <hr style={{ margin: '6px 0', border: 'none', borderTop: '1px solid #eee' }} />
          <div><b>Department:</b> {camera.department}</div>
          <div><b>Type:</b> {camera.camera_type}</div>
          <div><b>Owner:</b> {camera.owner || '—'}</div>
          <div>
            <b>Status:</b>{' '}
            <span style={{ color: statusColors[String(camera.status).toLowerCase()] || '#666', fontWeight: 600 }}>
              {camera.status}
            </span>
          </div>
          <div style={{ marginTop: 6, fontSize: 11, color: '#888' }}>
            {camera.latitude.toFixed(4)}, {camera.longitude.toFixed(4)}
          </div>
        </div>
      </Popup>
    </Marker>
  )
}
