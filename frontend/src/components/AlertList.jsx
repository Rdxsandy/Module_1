/**
 * components/AlertList.jsx
 * Table of alerts. Used on Dashboard (recent 5) and full Alerts page.
 */
import React, { useState } from 'react'
import { acknowledgeAlert, resolveAlert } from '../api/client'
import Modal from './Modal'

const severityColor = { critical: '#e02424', high: '#ff8800', medium: '#1a56db', low: '#0e9f6e' }

export default function AlertList({ alerts = [], onRefresh, compact = false }) {
  const [modal, setModal] = useState({ open: false, title: '', message: '', variant: 'info' })

  const handleAck = async (id) => {
    try {
      await acknowledgeAlert(id)
      onRefresh?.()
      setModal({ open: true, title: 'Alert Acknowledged', message: 'The alert was acknowledged successfully.', variant: 'success' })
    } catch {
      setModal({ open: true, title: 'Failed to Acknowledge', message: 'Please try again.', variant: 'error' })
    }
  }

  const handleResolve = async (id) => {
    try {
      await resolveAlert(id)
      onRefresh?.()
      setModal({ open: true, title: 'Alert Resolved', message: 'The alert was marked resolved successfully.', variant: 'success' })
    } catch {
      setModal({ open: true, title: 'Failed to Resolve', message: 'Please try again.', variant: 'error' })
    }
  }

  if (!alerts.length) {
    return <p style={{ color: 'var(--muted)', padding: 16 }}>No alerts to display.</p>
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ background: '#f8fafc', textAlign: 'left' }}>
            <th style={th}>Severity</th>
            <th style={th}>Vehicle</th>
            <th style={th}>Message</th>
            {!compact && <th style={th}>Status</th>}
            <th style={th}>Time</th>
            {!compact && <th style={th}>Action</th>}
          </tr>
        </thead>
        <tbody>
          {alerts.map(a => (
            <tr key={a.id} style={{ borderBottom: '1px solid var(--border)' }}>
              <td style={td}>
                <span style={{
                  background: severityColor[a.severity] || '#666',
                  color: '#fff',
                  padding: '2px 8px',
                  borderRadius: 4,
                  fontSize: 12,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                }}>
                  {a.severity}
                </span>
              </td>
              <td style={{ ...td, fontWeight: 600 }}>{a.vehicle_number}</td>
              <td style={{ ...td, maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {a.message}
              </td>
              {!compact && <td style={td}>{a.status}</td>}
              <td style={{ ...td, color: 'var(--muted)', fontSize: 12 }}>
                {new Date(a.created_at).toLocaleString()}
              </td>
              {!compact && (
                <td style={td}>
                  {a.status === 'NEW' && (
                    <button onClick={() => handleAck(a.id)} style={ackBtn}>Acknowledge</button>
                  )}
                  {a.status === 'ACKNOWLEDGED' && (
                    <button onClick={() => handleResolve(a.id)} style={{...ackBtn, background: '#0e9f6e'}}>Resolve</button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      <Modal
        open={modal.open}
        title={modal.title}
        message={modal.message}
        variant={modal.variant}
        autoCloseMs={modal.variant === 'success' ? 1600 : undefined}
        onClose={() => setModal(m => ({ ...m, open: false }))}
      />
    </div>
  )
}

const th = { padding: '10px 12px', fontWeight: 600, fontSize: 13, color: 'var(--muted)' }
const td = { padding: '10px 12px' }
const ackBtn = {
  background: '#1a56db', color: '#fff', border: 'none', borderRadius: 4,
  padding: '4px 10px', fontSize: 12, cursor: 'pointer'
}
