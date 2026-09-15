/**
 * components/MapView.jsx
 * Reusable Leaflet map centered on Delhi.
 * Renders camera markers and optionally a vehicle route.
 * Children are rendered inside the MapContainer (use react-leaflet components).
 */
import React from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'

const DELHI_CENTER = [28.6139, 77.2090]
const DEFAULT_ZOOM = 13

export default function MapView({ height = '500px', zoom = DEFAULT_ZOOM, center = DELHI_CENTER, children }) {
  return (
    <MapContainer
      center={center}
      zoom={zoom}
      style={{ height, width: '100%', borderRadius: 8, zIndex: 0 }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {children}
    </MapContainer>
  )
}
