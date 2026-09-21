/**
 * App.jsx - Root component with Auth + React Router nav and sidebar layout.
 *
 * Auth flow:
 *  - AuthProvider wraps everything
 *  - /login is public
 *  - All other routes wrapped in ProtectedRoute
 *  - Sidebar shows logged-in username, role badge, and Logout button
 *  - OPERATOR: camera add/watchlist actions hidden (enforced in backend too)
 */
import React from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Login          from './pages/Login'
import Dashboard      from './pages/Dashboard'
import Cameras        from './pages/Cameras'
import Live           from './pages/Live'
import Feed           from './pages/Feed'
import MapPage        from './pages/MapPage'
import VehicleTracking from './pages/VehicleTracking'
import Alerts         from './pages/Alerts'
import Watchlist      from './pages/Watchlist'
import Events          from './pages/Events'
import Reports         from './pages/Reports'

const NAV_LINKS = [
  { to: '/',         label: '🏠 Dashboard'       },
  { to: '/cameras',  label: '📹 Cameras'          },
  { to: '/live',     label: '🟢 Live Cameras'      },
  { to: '/feed',     label: '🎥 Feed Monitor'      },
  { to: '/map',      label: '🗺️  GIS Map'          },
  { to: '/tracking', label: '🚗 Vehicle Tracking'  },
  { to: '/alerts',   label: '🚨 Alerts'            },
  { to: '/watchlist',label: '📋 Watchlist'         },
  { to: '/events',   label: '🧾 Raw Events'        },
  { to: '/reports',  label: '📊 Reports'           },
]

const roleColors = { ADMIN: '#1a56db', OPERATOR: '#0e9f6e' }

function Sidebar() {
  const { user, logout } = useAuth()

  return (
    <nav style={{
      width: 220, background: '#1e293b', color: '#e2e8f0',
      display: 'flex', flexDirection: 'column', flexShrink: 0,
    }}>
      {/* Brand */}
      <div style={{ padding: '22px 20px 16px', borderBottom: '1px solid #334155' }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#f1f5f9' }}>CCTV GIS PoC</div>
        <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>Central Registry — Delhi</div>
      </div>

      {/* Nav links */}
      <div style={{ padding: '12px 0', flex: 1 }}>
        {NAV_LINKS.map(({ to, label }) => {
          // Hide watchlist from OPERATOR if we want, but spec says "Operators can view matches and alerts but cannot modify protected watchlist data".
          // So let them view it.
          return (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              style={({ isActive }) => ({
                display: 'block', padding: '10px 20px', textDecoration: 'none',
                fontSize: 14, color: isActive ? '#fff' : '#94a3b8',
                background: isActive ? '#334155' : 'transparent',
                borderLeft: isActive ? '3px solid #1a56db' : '3px solid transparent',
                fontWeight: isActive ? 600 : 400,
                transition: 'all .15s',
              })}
            >
              {label}
            </NavLink>
          )
        })}
      </div>

      {/* User info + logout */}
      {user && (
        <div style={{ padding: '14px 20px', borderTop: '1px solid #334155' }}>
          <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>Signed in as</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#f1f5f9', marginBottom: 6 }}>
            {user.username}
          </div>
          <span style={{
            fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
            background: roleColors[user.role] || '#666', color: '#fff',
          }}>
            {user.role}
          </span>
          <button
            onClick={logout}
            style={{
              display: 'block', width: '100%', marginTop: 12,
              padding: '7px 0', background: '#334155', color: '#94a3b8',
              border: '1px solid #475569', borderRadius: 6, fontSize: 13,
              cursor: 'pointer', fontWeight: 500,
            }}
          >
            🔒 Logout
          </button>
          <div style={{ marginTop: 10, fontSize: 11, color: '#64748b' }}>
            API: <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" style={{ color: '#60a5fa' }}>Swagger</a>
          </div>
        </div>
      )}
    </nav>
  )
}

function AppLayout() {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <main style={{ flex: 1, padding: '28px 32px', overflowY: 'auto', maxWidth: '100%' }}>
        <Routes>
          <Route path="/"         element={<ProtectedRoute><Dashboard /></ProtectedRoute>}       />
          <Route path="/cameras"  element={<ProtectedRoute><Cameras /></ProtectedRoute>}         />
          <Route path="/live"     element={<ProtectedRoute><Live /></ProtectedRoute>}            />
          <Route path="/feed"     element={<ProtectedRoute><Feed /></ProtectedRoute>}            />
          <Route path="/map"      element={<ProtectedRoute><MapPage /></ProtectedRoute>}         />
          <Route path="/tracking" element={<ProtectedRoute><VehicleTracking /></ProtectedRoute>} />
          <Route path="/alerts"   element={<ProtectedRoute><Alerts /></ProtectedRoute>}          />
          <Route path="/watchlist" element={<ProtectedRoute><Watchlist /></ProtectedRoute>}       />
          <Route path="/events"   element={<ProtectedRoute><Events /></ProtectedRoute>}          />
          <Route path="/reports"  element={<ProtectedRoute><Reports /></ProtectedRoute>}         />
          <Route path="*"         element={<Navigate to="/" replace />}                          />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*"     element={<AppLayout />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

