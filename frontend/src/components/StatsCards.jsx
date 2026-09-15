/**
 * components/StatsCards.jsx
 * Dashboard stats strip: total/online/offline/maintenance cameras + open alerts.
 */
import React from 'react'

const cardStyle = {
  background: 'var(--card-bg)',
  borderRadius: 10,
  padding: '20px 24px',
  flex: '1 1 160px',
  boxShadow: '0 1px 4px rgba(0,0,0,.08)',
  borderTop: '4px solid transparent',
}

function Card({ label, value, color, emoji }) {
  return (
    <div style={{ ...cardStyle, borderTopColor: color }}>
      <div style={{ fontSize: 28, fontWeight: 700, color }}>{emoji} {value}</div>
      <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>{label}</div>
    </div>
  )
}

export default function StatsCards({ summary }) {
  if (!summary) return null;

  return (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 24 }}>
      <Card label="Total Cameras"       value={summary.camera_count}      color="#1a56db" emoji="📹" />
      <Card label="Online"              value={summary.online_count}     color="#0e9f6e" emoji="🟢" />
      <Card label="Offline"             value={summary.offline_count}    color="#e02424" emoji="🔴" />
      <Card label="Maintenance"         value={summary.maintenance_count}      color="#ff8800" emoji="🟡" />
      <Card label="Events Today"        value={summary.events_today} color="#06b6d4" emoji="🚗" />
      <Card label="Open Alerts"         value={summary.new_alerts} color="#9333ea" emoji="🚨" />
    </div>
  )
}
