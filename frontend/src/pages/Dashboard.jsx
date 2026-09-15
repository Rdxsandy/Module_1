/**
 * pages/Dashboard.jsx — Screen 1
 * Shows stats cards, recent alerts, and quick navigation links.
 */
import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDashboardSummary, getRecentAlerts, startSimulator, stopSimulator, getSimulatorStatus } from '../api/client'
import StatsCards from '../components/StatsCards'
import AlertList from '../components/AlertList'

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [simulatorRunning, setSimulatorRunning] = useState(false)

  const load = async () => {
    try {
      const [sumRes, alertRes, simRes] = await Promise.all([
        getDashboardSummary(),
        getRecentAlerts({ limit: 5 }),
        getSimulatorStatus().catch(() => ({ data: { running: false } }))
      ])
      setSummary(sumRes.data)
      setAlerts(alertRes.data)
      setSimulatorRunning(simRes.data.running)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const toggleSimulator = async () => {
    try {
      if (simulatorRunning) {
        await stopSimulator();
      } else {
        await startSimulator();
      }
      setSimulatorRunning(!simulatorRunning);
    } catch (e) {
      console.error(e);
      alert('Failed to toggle simulator');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 style={h1}>🏠 Dashboard</h1>
        <button 
          onClick={toggleSimulator}
          style={{
            padding: '8px 16px',
            borderRadius: '6px',
            border: 'none',
            background: simulatorRunning ? '#ef4444' : '#10b981',
            color: 'white',
            fontWeight: 'bold',
            cursor: 'pointer'
          }}
        >
          {simulatorRunning ? '⏹ Stop Simulator' : '▶ Start Simulator'}
        </button>
      </div>
      {loading ? <p>Loading…</p> : (
        <>
          <StatsCards summary={summary} />

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
            <AlertList alerts={alerts} onRefresh={load} compact />
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
