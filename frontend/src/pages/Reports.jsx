/**
 * pages/Reports.jsx
 * Gap-analysis report: ageing infrastructure (installation_date > 5yr) and
 * maintenance backlog (offline, or last_maintenance_date > 1yr / never set).
 */
import React, { useEffect, useState } from 'react'
import { getCamerasGapAnalysis } from '../api/client'

export default function Reports() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getCamerasGapAnalysis()
      .then(res => setData(res.data))
      .catch(() => setError('Failed to load gap-analysis report.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p>Loading report…</p>
  if (error) return <p style={{ color: '#e02424' }}>{error}</p>
  if (!data) return null

  return (
    <div>
      <h1 style={h1}>📊 Gap-Analysis Report</h1>
      <p style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 20 }}>
        Generated {new Date(data.generated_at).toLocaleString()} · {data.total_cameras} cameras in registry
      </p>

      <div style={cardGrid}>
        <StatCard
          label="Requires Upgrade"
          value={`${data.ageing.requires_upgrade_pct}%`}
          sub={`${data.ageing.requires_upgrade_count} camera${data.ageing.requires_upgrade_count === 1 ? '' : 's'} older than 5 years`}
          color="#d97706"
        />
        <StatCard
          label="Requires Maintenance"
          value={`${data.maintenance.requires_maintenance_pct}%`}
          sub={`${data.maintenance.requires_maintenance_count} camera${data.maintenance.requires_maintenance_count === 1 ? '' : 's'} offline or overdue`}
          color="#e02424"
        />
        <StatCard
          label="Offline Now"
          value={data.maintenance.offline_count}
          sub="cameras currently OFFLINE"
          color="#64748b"
        />
      </div>

      <ReportTable
        title="Ageing Infrastructure — Requires Upgrade"
        emptyText="No cameras older than 5 years."
        cameras={data.ageing.cameras}
        dateField="installation_date"
        dateLabel="Installed"
      />

      <ReportTable
        title="Maintenance Backlog"
        emptyText="No cameras need maintenance."
        cameras={data.maintenance.cameras}
        dateField="last_maintenance_date"
        dateLabel="Last Maintained"
      />
    </div>
  )
}

function StatCard({ label, value, sub, color }) {
  return (
    <div style={card}>
      <div style={{ fontSize: 13, color: 'var(--muted)', fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 32, fontWeight: 700, color, margin: '6px 0 2px' }}>{value}</div>
      <div style={{ fontSize: 12, color: 'var(--muted)' }}>{sub}</div>
    </div>
  )
}

function ReportTable({ title, emptyText, cameras, dateField, dateLabel }) {
  return (
    <div style={{ ...card, marginBottom: 20 }}>
      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '0 0 14px', color: '#1e293b' }}>{title}</h2>
      {cameras.length === 0 ? (
        <p style={{ color: 'var(--muted)', fontSize: 14 }}>{emptyText}</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={table}>
            <thead>
              <tr style={trHead}>
                <th style={th}>Name</th>
                <th style={th}>Department</th>
                <th style={th}>Status</th>
                <th style={th}>{dateLabel}</th>
              </tr>
            </thead>
            <tbody>
              {cameras.map(c => (
                <tr key={c.id} style={trBody}>
                  <td style={td}>{c.name}</td>
                  <td style={td}>{c.department}</td>
                  <td style={td}>{c.status}</td>
                  <td style={td}>{c[dateField] || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const h1 = { fontSize: 24, fontWeight: 700, margin: '0 0 4px', color: '#1e293b' }
const cardGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 24 }
const card = { background: '#fff', borderRadius: 8, border: '1px solid #e2e8f0', padding: '16px 20px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }
const table = { width: '100%', borderCollapse: 'collapse', fontSize: 14 }
const trHead = { background: '#f8fafc', borderBottom: '1px solid #e2e8f0', textAlign: 'left' }
const th = { padding: '10px 14px', fontWeight: 600, color: '#475569', fontSize: 12, textTransform: 'uppercase' }
const trBody = { borderBottom: '1px solid #f1f5f9' }
const td = { padding: '10px 14px', color: '#1e293b' }
