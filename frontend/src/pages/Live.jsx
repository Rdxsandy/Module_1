/**
 * pages/Live.jsx
 * Grid dashboard of all registered cameras — a name, status, and a still
 * JPEG refreshed periodically (NOT full live video for every camera: that's
 * exactly what would exhaust a modest box's CPU/RAM running 30 AI feeds at
 * once). Click a camera with a stream configured to jump to Feed Monitor
 * and point the AI pipeline at it specifically.
 */
import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { MdVideocam, MdVideocamOff, MdRefresh, MdOutlineDashboard } from 'react-icons/md'
import { getCameras, getCameraSnapshot } from '../api/client'

const REFRESH_MS = 10000

const STATUS_COLORS = {
  ONLINE: '#16a34a',
  OFFLINE: '#94a3b8',
  MAINTENANCE: '#d97706',
}

export default function Live() {
  const [cameras, setCameras] = useState([])
  const [loading, setLoading] = useState(true)
  const [snapshots, setSnapshots] = useState({}) // camera.id -> { url, reachable, updatedAt }
  const navigate = useNavigate()
  const urlsRef = useRef({}) // camera.id -> current blob url (for revoke-on-replace/unmount)

  const loadCameras = useCallback(async () => {
    try {
      const res = await getCameras()
      setCameras(res.data)
    } catch {
      // ignore — grid just keeps showing whatever it last had
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshSnapshots = useCallback(async (cameraList) => {
    const withStream = cameraList.filter((c) => c.has_stream)
    await Promise.allSettled(
      withStream.map(async (c) => {
        try {
          const res = await getCameraSnapshot(c.id)
          const newUrl = URL.createObjectURL(res.data)
          const oldUrl = urlsRef.current[c.id]
          urlsRef.current[c.id] = newUrl
          setSnapshots((prev) => ({ ...prev, [c.id]: { url: newUrl, reachable: true, updatedAt: Date.now() } }))
          if (oldUrl) URL.revokeObjectURL(oldUrl)
        } catch {
          setSnapshots((prev) => ({
            ...prev,
            [c.id]: { url: prev[c.id]?.url ?? null, reachable: false, updatedAt: Date.now() },
          }))
        }
      })
    )
  }, [])

  useEffect(() => { loadCameras() }, [loadCameras])

  useEffect(() => {
    if (cameras.length === 0) return undefined
    refreshSnapshots(cameras)
    const interval = setInterval(() => refreshSnapshots(cameras), REFRESH_MS)
    return () => clearInterval(interval)
  }, [cameras, refreshSnapshots])

  // Revoke every remaining blob URL when the page unmounts.
  useEffect(() => () => {
    Object.values(urlsRef.current).forEach((url) => url && URL.revokeObjectURL(url))
  }, [])

  const handleOpenFeed = (camera) => {
    if (!camera.has_stream) return
    navigate(`/feed?camera=${encodeURIComponent(camera.name)}`)
  }

  const withStreamCount = cameras.filter((c) => c.has_stream).length

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.iconWrap}>
            <MdOutlineDashboard size={24} color="#1d4ed8" />
          </div>
          <div>
            <h1 style={styles.title}>Live Cameras</h1>
            <p style={styles.subtitle}>
              {cameras.length} registered · {withStreamCount} with a live stream configured
            </p>
          </div>
        </div>
        <button style={styles.refreshBtn} onClick={() => refreshSnapshots(cameras)}>
          <MdRefresh size={16} /> Refresh now
        </button>
      </div>

      {loading ? (
        <div style={styles.emptyState}>Loading cameras…</div>
      ) : cameras.length === 0 ? (
        <div style={styles.emptyState}>
          <MdVideocamOff size={36} color="#cbd5e1" />
          <p style={{ margin: '8px 0 0', color: '#94a3b8' }}>
            No cameras registered yet — add one from the Cameras page.
          </p>
        </div>
      ) : (
        <div style={styles.grid}>
          {cameras.map((c) => {
            const snap = snapshots[c.id]
            const hasStream = !!c.has_stream
            return (
              <div
                key={c.id}
                style={{ ...styles.card, cursor: hasStream ? 'pointer' : 'default' }}
                onClick={() => handleOpenFeed(c)}
                title={hasStream ? `Analyze ${c.name}` : 'No stream URL configured'}
              >
                <div style={styles.thumbWrap}>
                  {hasStream ? (
                    snap?.url ? (
                      <img src={snap.url} alt={c.name} style={styles.thumbImg} />
                    ) : (
                      <div style={styles.thumbPlaceholder}>
                        <MdVideocam size={28} color="#64748b" />
                        <span>Connecting…</span>
                      </div>
                    )
                  ) : (
                    <div style={styles.thumbPlaceholder}>
                      <MdVideocamOff size={28} color="#94a3b8" />
                      <span>No stream configured</span>
                    </div>
                  )}
                  {hasStream && snap && !snap.reachable && (
                    <div style={styles.unreachableBadge}>Unreachable</div>
                  )}
                </div>
                <div style={styles.cardFooter}>
                  <span style={styles.cardName}>{c.name}</span>
                  <span style={{ ...styles.statusDot, background: STATUS_COLORS[c.status] || '#94a3b8' }} />
                </div>
                <div style={styles.cardMeta}>{c.department} · {c.camera_type}</div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

const styles = {
  page: { padding: '24px', maxWidth: 1400, margin: '0 auto' },

  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 12 },
  headerLeft: { display: 'flex', alignItems: 'center', gap: 14 },
  iconWrap: { width: 44, height: 44, borderRadius: 12, background: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 22, fontWeight: 700, color: '#0f172a', margin: 0 },
  subtitle: { fontSize: 13, color: '#64748b', margin: '2px 0 0' },

  refreshBtn: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '9px 16px', borderRadius: 8, border: '1px solid #cbd5e1',
    background: '#fff', color: '#334155', fontSize: 14, fontWeight: 600, cursor: 'pointer',
  },

  grid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))', gap: 16,
  },
  card: {
    background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0',
    overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
  },
  thumbWrap: {
    position: 'relative', width: '100%', aspectRatio: '16 / 9',
    background: '#0f172a', display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  thumbImg: { width: '100%', height: '100%', objectFit: 'cover' },
  thumbPlaceholder: {
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
    color: '#64748b', fontSize: 12,
  },
  unreachableBadge: {
    position: 'absolute', top: 8, right: 8,
    background: 'rgba(220,38,38,0.9)', color: '#fff',
    fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
  },
  cardFooter: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 12px 2px', fontSize: 14, fontWeight: 600, color: '#0f172a',
  },
  statusDot: { width: 9, height: 9, borderRadius: '50%', flexShrink: 0 },
  cardMeta: { padding: '0 12px 12px', fontSize: 12, color: '#94a3b8' },

  emptyState: {
    textAlign: 'center', padding: '60px 20px',
    color: '#94a3b8', fontSize: 15,
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
  },
}
