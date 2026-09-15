/**
 * components/ProtectedRoute.jsx
 * Wraps routes that require authentication.
 * Shows a loading spinner while validating the stored token.
 * Redirects to /login if not authenticated.
 */
import React from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute({ children, adminOnly = false }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <div style={{ textAlign: 'center', color: '#1a56db' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🔒</div>
          <div>Authenticating…</div>
        </div>
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />

  if (adminOnly && user.role !== 'ADMIN') {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ fontSize: 48 }}>🚫</div>
        <h2 style={{ color: '#e02424', marginTop: 12 }}>Access Denied</h2>
        <p style={{ color: '#6b7280' }}>Admin privileges required.</p>
      </div>
    )
  }

  return children
}
