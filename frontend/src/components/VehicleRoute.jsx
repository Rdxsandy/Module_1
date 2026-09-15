/**
 * components/VehicleRoute.jsx
 * Renders a vehicle's movement history as:
 *  - A Polyline connecting camera coordinates in chronological order
 *  - CircleMarkers at each stop with a popup showing camera name & timestamp
 */
import React, { useEffect } from 'react'
import { Polyline, CircleMarker, Popup, useMap } from 'react-leaflet'

export default function VehicleRoute({ history = [], fitRoute = false }) {
  const map = useMap()

  const positions = history.map(h => [h.latitude, h.longitude])

  // Fit map to the full route when requested
  useEffect(() => {
    if (fitRoute && positions.length > 0) {
      map.fitBounds(positions, { padding: [40, 40] })
    }
  }, [fitRoute, positions, map])

  if (positions.length === 0) return null

  return (
    <>
      {/* Route polyline */}
      <Polyline positions={positions} color="#1a56db" weight={3} opacity={0.8} />

      {/* Stop markers */}
      {history.map((stop, idx) => (
        <CircleMarker
          key={idx}
          center={[stop.latitude, stop.longitude]}
          radius={idx === 0 ? 10 : idx === history.length - 1 ? 10 : 7}
          fillColor={idx === 0 ? '#0e9f6e' : idx === history.length - 1 ? '#e02424' : '#1a56db'}
          color="#fff"
          weight={2}
          fillOpacity={0.9}
        >
          <Popup>
            <div style={{ minWidth: 170 }}>
              <strong>Stop {idx + 1}: {stop.camera_name}</strong>
              <br />
              <span style={{ fontSize: 12, color: '#555' }}>
                {new Date(stop.event_time).toLocaleString()}
              </span>
              <br />
              <span style={{ fontSize: 11, color: '#888' }}>
                Confidence: {stop.confidence ? `${(stop.confidence * 100).toFixed(0)}%` : '—'}
              </span>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  )
}
