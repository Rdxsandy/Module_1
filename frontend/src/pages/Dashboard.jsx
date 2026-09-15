/**
 * pages/Dashboard.jsx — Screen 1
 * Shows stats cards, recent alerts, and quick navigation links.
 */
import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCameras, getAlerts } from '../api/client'
import StatsCards from '../components/StatsCards'
import AlertList from '../components/AlertList'

export default function Dashboard() {
  const [cameras, setCameras] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const [camRes, alertRes] = await Promise.all([getCameras(), getAlerts({ limit: 10 })])
      setCameras(camRes.data)
      setAlerts(alertRes.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div>
      <h1 style={h1}>🏠 Dashboard</h1>
      {loading ? <p>Loading…</p> : (
        <>
          <StatsCards cameras={cameras} alerts={alerts} />

          {/* Quick actions */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
            <QuickLink to="/map"      icon="🗺️"  label="View GIS Map" />
            <QuickLink to="/cameras"  icon="📹"  label="Camera Registry" />
            <QuickLink to="/tracking" icon="🚗"  label="Track Vehicle" />
            <QuickLink to="/alerts"   icon="🚨"  label="All Alerts" />
          </div>

          {/* Recent alerts */}
          <div style={card}>
            <h2 style={h2}>Recent Alerts</h2>
            <AlertList alerts={alerts.slice(0, 5)} onRefresh={load} compact />
          </div>
        </>
      )}
    </div>
  )
}

function QuickLink({ to, icon, label }) {
  return (
    <Link to={to} style={{
      display: 'flex', alignItems: 'center', gap: 8,
      background: 'var(--card-bg)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '12px 20px', textDecoration: 'none',
      color: 'var(--primary)', fontWeight: 600, fontSize: 15,
      boxShadow: '0 1px 3px rgba(0,0,0,.06)',
    }}>
      <span style={{ fontSize: 22 }}>{icon}</span> {label}
    </Link>
  )
}

const h1 = { fontSize: 24, fontWeight: 700, marginBottom: 20 }
const h2 = { fontSize: 17, fontWeight: 600, marginBottom: 14, color: '#1e293b' }
const card = { background: 'var(--card-bg)', borderRadius: 10, padding: 20, boxShadow: '0 1px 4px rgba(0,0,0,.08)' }
