/**
 * components/WatchlistMarker.jsx
 * A Leaflet marker for a watchlisted vehicle's last known location — plotted
 * automatically on the GIS map for every active watchlist entry that has at
 * least one detection, no plate search required.
 * Color-coded by priority, with a distinct diamond shape so it reads as
 * different from a regular camera marker at a glance.
 */
import React from 'react'
import { Marker, Popup } from 'react-leaflet'
import L from 'leaflet'

const priorityColors = { CRITICAL: '#7f1d1d', HIGH: '#e02424', MEDIUM: '#ff8800', LOW: '#d4a017' }

function makeIcon(priority) {
  const color = priorityColors[String(priority).toUpperCase()] || '#e02424'
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30">
    <rect x="4" y="4" width="22" height="22" rx="4" transform="rotate(45 15 15)" fill="${color}" stroke="#fff" stroke-width="2"/>
    <text x="15" y="20" font-size="14" font-weight="700" fill="#fff" text-anchor="middle">!</text>
  </svg>`
  return L.divIcon({
    html: svg,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -15],
    className: '',
  })
}

export default function WatchlistMarker({ entry }) {
  if (!entry.last_seen) return null
  const { last_seen: seen } = entry

  return (
    <Marker position={[seen.latitude, seen.longitude]} icon={makeIcon(entry.priority)}>
      <Popup>
        <div style={{ minWidth: 190 }}>
          <strong style={{ fontSize: 15, fontFamily: 'monospace' }}>{entry.identifier}</strong>
          <hr style={{ margin: '6px 0', border: 'none', borderTop: '1px solid #eee' }} />
          <div>
            <b>Priority:</b>{' '}
            <span style={{ color: priorityColors[String(entry.priority).toUpperCase()] || '#e02424', fontWeight: 600 }}>
              {entry.priority}
            </span>
          </div>
          <div><b>Type:</b> {entry.entity_type}</div>
          {entry.description && <div><b>Note:</b> {entry.description}</div>}
          <div><b>Last seen:</b> {seen.camera_name}</div>
          <div style={{ fontSize: 12, color: '#555' }}>{new Date(seen.event_time).toLocaleString()}</div>
        </div>
      </Popup>
    </Marker>
  )
}
