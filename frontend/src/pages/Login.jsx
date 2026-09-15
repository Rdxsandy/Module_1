/**
 * pages/Login.jsx
 * Login form — username + password, submit → JWT stored in localStorage.
 * Shows generic error on 401 (never reveals which field is wrong).
 */
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const { login } = useAuth()
  const navigate  = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError('Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={page}>
      <div style={card}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 44, marginBottom: 8 }}>📹</div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#1e293b', margin: 0 }}>
            CCTV GIS — Central Registry
          </h1>
          <p style={{ color: '#6b7280', fontSize: 13, marginTop: 6 }}>
            Sign in to access the system
          </p>
        </div>

        {/* Error */}
        {error && (
          <div style={errorBox}>{error}</div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <label style={labelStyle}>
            Username
            <input
              autoFocus
              required
              style={inputStyle}
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="admin or operator"
            />
          </label>

          <label style={labelStyle}>
            Password
            <input
              required
              style={inputStyle}
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Enter your password"
            />
          </label>

          <button type="submit" disabled={loading} style={submitBtn}>
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        {/* Demo hint */}
        <div style={{ marginTop: 20, padding: '10px 14px', background: '#f0f9ff', borderRadius: 8, fontSize: 12, color: '#0369a1' }}>
          <strong>Demo credentials (password: 12345678)</strong><br />
          Admin: <code>admin</code> &nbsp;|&nbsp; Operator: <code>operator</code>
        </div>
      </div>
    </div>
  )
}

const page = {
  minHeight: '100vh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: '#f0f2f5',
}
const card = {
  background: '#fff',
  borderRadius: 12,
  padding: '36px 40px',
  width: '100%',
  maxWidth: 400,
  boxShadow: '0 4px 24px rgba(0,0,0,.10)',
}
const labelStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  marginBottom: 16,
  fontSize: 14,
  fontWeight: 500,
  color: '#374151',
}
const inputStyle = {
  padding: '10px 12px',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  fontSize: 14,
  outline: 'none',
}
const submitBtn = {
  width: '100%',
  padding: '11px 0',
  background: '#1a56db',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
  marginTop: 4,
}
const errorBox = {
  background: '#fef2f2',
  border: '1px solid #fca5a5',
  color: '#b91c1c',
  borderRadius: 6,
  padding: '10px 14px',
  fontSize: 13,
  marginBottom: 16,
}
