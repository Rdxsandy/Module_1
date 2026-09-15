/**
 * context/AuthContext.jsx
 * Centralised authentication state for the whole app.
 *
 * Provides: { user, token, loading, login, logout }
 * - token is persisted in localStorage
 * - On mount calls /api/auth/me; clears session if token invalid/expired
 * - login() stores token + user in state and localStorage
 * - logout() clears everything and redirects to /login
 */
import React, { createContext, useContext, useEffect, useState } from 'react'
import axios from 'axios'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [token, setToken]     = useState(() => localStorage.getItem('cctv_token'))
  const [loading, setLoading] = useState(true)

  // On mount: validate stored token
  useEffect(() => {
    if (!token) { setLoading(false); return }
    axios.get('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => setUser(r.data))
      .catch(() => { localStorage.removeItem('cctv_token'); setToken(null) })
      .finally(() => setLoading(false))
  }, [])

  const login = async (username, password) => {
    const res = await axios.post('/api/auth/login', { username, password })
    const { access_token, user: userData } = res.data
    localStorage.setItem('cctv_token', access_token)
    setToken(access_token)
    setUser(userData)
    return userData
  }

  const logout = () => {
    localStorage.removeItem('cctv_token')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
