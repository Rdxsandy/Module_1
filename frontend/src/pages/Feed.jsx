/**
 * pages/Feed.jsx
 * The "AI magnifying glass": point the ANPR pipeline at one uploaded video
 * or one registered camera's live stream (picked here, or arriving via
 * ?camera=<name> from the Live Cameras grid) and watch frames/detections
 * come through in real time.
 */
import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  MdOutlineVideocam,
  MdUpload,
  MdStop,
  MdCheckCircle,
  MdErrorOutline,
  MdRadioButtonChecked,
} from 'react-icons/md'
import {
  uploadCameraFeed, analyzeCameraFeed, stopCameraFeed, getCameraFeedStatus,
  getCameraFeedActivity, getCameras,
} from '../api/client'

// No Authorization header can be attached to an <img> request, so this is
// deliberately a public MJPEG endpoint (see routers/camera_feed.py).
const STREAM_URL = '/api/camera-feed/stream'

const STATUS_LABEL = {
  detected: 'Plate detected',
  no_plate: 'No plate in frame',
  low_confidence: 'Low-confidence plate skipped',
  ai_error: 'AI service error',
  connection_error: 'Connection error',
}

export default function Feed() {
  const [status, setStatus] = useState({ running: false })
  const [activity, setActivity] = useState([])
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [cameras, setCameras] = useState([])
  const [selectedCamera, setSelectedCamera] = useState('')
  const fileInputRef = useRef(null)
  const [searchParams] = useSearchParams()

  // Only cameras with a usable stream (manual stream_url or a VMS channel)
  // can be "pointed at" — see routers/camera_feed.py's /analyze endpoint.
  const liveCameras = cameras.filter((c) => c.has_stream)

  useEffect(() => {
    getCameras().then((res) => {
      setCameras(res.data)
      const withStream = res.data.filter((c) => c.has_stream)
      // Arriving from the Live Cameras grid ("Analyze" on a specific card)
      // pre-selects that camera; otherwise default to the first live one.
      const requested = searchParams.get('camera')
      const match = requested && withStream.find((c) => c.name === requested)
      if (match) setSelectedCamera(match.name)
      else if (withStream.length > 0) setSelectedCamera(withStream[0].name)
    }).catch(() => {
      // ignore — camera picker just stays empty
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const fetchStatus = useCallback(async () => {
    try {
      const res = await getCameraFeedStatus()
      setStatus(res.data)
    } catch {
      // ignore — polling, will retry next tick
    }
  }, [])

  const fetchActivity = useCallback(async () => {
    try {
      const res = await getCameraFeedActivity()
      setActivity(res.data.items)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    fetchActivity()
    const interval = setInterval(() => {
      fetchStatus()
      fetchActivity()
    }, 2000)
    return () => clearInterval(interval)
  }, [fetchStatus, fetchActivity])

  const handleFileSelected = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return

    setUploading(true)
    setError('')
    try {
      await uploadCameraFeed(file, 'Camera-01')
      await fetchStatus()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to start video feed.')
    } finally {
      setUploading(false)
    }
  }

  const handleAnalyze = async () => {
    if (!selectedCamera) return
    setAnalyzing(true)
    setError('')
    try {
      await analyzeCameraFeed(selectedCamera)
      await fetchStatus()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to start video feed.')
    } finally {
      setAnalyzing(false)
    }
  }

  const handleStop = async () => {
    setError('')
    try {
      await stopCameraFeed()
      await fetchStatus()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to stop video feed.')
    }
  }

  const uptime = status.started_at ? formatUptime(status.started_at) : null

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.iconWrap}>
            <MdOutlineVideocam size={24} color="#1d4ed8" />
          </div>
          <div>
            <h1 style={styles.title}>Feed Monitor</h1>
            <p style={styles.subtitle}>Watch an uploaded video or a live camera stream into the AI pipeline in real time</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            style={{ display: 'none' }}
            onChange={handleFileSelected}
          />
          {status.running ? (
            <button style={{ ...styles.actionBtn, ...styles.stopBtn }} onClick={handleStop}>
              <MdStop size={18} /> Stop Feed
            </button>
          ) : (
            <>
              {liveCameras.length > 0 && (
                <>
                  <select
                    style={styles.cameraSelect}
                    value={selectedCamera}
                    onChange={(e) => setSelectedCamera(e.target.value)}
                    disabled={analyzing || uploading}
                  >
                    {liveCameras.map((c) => (
                      <option key={c.id} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                  <button
                    style={{ ...styles.actionBtn, ...styles.analyzeBtn, opacity: analyzing ? 0.7 : 1 }}
                    onClick={handleAnalyze}
                    disabled={analyzing || uploading}
                  >
                    <MdRadioButtonChecked size={18} /> {analyzing ? 'Starting…' : 'Analyze Feed'}
                  </button>
                </>
              )}
              <button
                style={{ ...styles.actionBtn, ...styles.uploadBtn, opacity: uploading ? 0.7 : 1 }}
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading || analyzing}
              >
                <MdUpload size={18} /> {uploading ? 'Uploading…' : 'Upload Video Feed'}
              </button>
            </>
          )}
        </div>
      </div>

      {error && <div style={styles.errorBox}>{error}</div>}
      {status.source_error && (
        <div style={styles.errorBox}>Video source error: {status.source_error}</div>
      )}

      <div style={styles.grid}>
        {/* Live preview */}
        <div style={styles.card}>
          <h2 style={styles.cardTitle}>
            Live Preview
            {status.running && (
              <span style={styles.liveBadge}>
                <MdRadioButtonChecked size={12} /> LIVE
              </span>
            )}
          </h2>
          <div style={styles.previewFrame}>
            {status.running || status.has_preview ? (
              <img
                key={status.started_at || 'stream'}
                src={STREAM_URL}
                alt="Live CCTV Feed"
                style={styles.previewImg}
              />
            ) : (
              <div style={styles.previewEmpty}>
                No feed running — upload a video to begin.
              </div>
            )}
          </div>
        </div>

        {/* Stats */}
        <div style={styles.card}>
          <h2 style={styles.cardTitle}>Pipeline Status</h2>
          <StatRow label="Status" value={status.running ? 'Running' : 'Stopped'} highlight={status.running} />
          <StatRow label="Camera" value={status.camera_id || '—'} />
          <StatRow label="Source" value={status.mode === 'live' ? 'Live camera' : status.mode === 'file' ? 'Uploaded file' : '—'} />
          <StatRow label="File" value={status.filename || '—'} />
          <StatRow label="Uptime" value={uptime || '—'} />
          <StatRow label="Frames processed" value={status.frames_processed ?? 0} />
          <StatRow label="Plates detected" value={status.plates_detected ?? 0} />
          <StatRow
            label="Last frame"
            value={status.last_frame_at ? new Date(status.last_frame_at).toLocaleTimeString() : '—'}
          />
        </div>
      </div>

      {/* Activity log */}
      <div style={styles.card}>
        <h2 style={styles.cardTitle}>
          Recent Frame Activity
          <span style={styles.countBadge}>{activity.length}</span>
        </h2>
        {activity.length === 0 ? (
          <div style={styles.emptyState}>
            <MdOutlineVideocam size={36} color="#cbd5e1" />
            <p style={{ margin: '8px 0 0', color: '#94a3b8' }}>
              No frames processed yet. Upload a video to start the feed.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  {['Time', 'Result', 'Plate', 'Confidence', 'Detail'].map(h => (
                    <th key={h} style={styles.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {activity.map((a, i) => (
                  <tr key={i} style={styles.tr}>
                    <td style={{ ...styles.td, color: '#64748b', fontSize: 13 }}>
                      {new Date(a.time).toLocaleTimeString()}
                    </td>
                    <td style={styles.td}>
                      <StatusBadge status={a.status} />
                    </td>
                    <td style={styles.td}>
                      {a.plate ? <span style={styles.plate}>{a.plate}</span> : '—'}
                    </td>
                    <td style={styles.td}>
                      {a.confidence != null ? `${Math.round(a.confidence * 100)}%` : '—'}
                    </td>
                    <td style={{ ...styles.td, color: '#94a3b8', fontSize: 13 }}>
                      {a.message || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function StatRow({ label, value, highlight }) {
  return (
    <div style={styles.statRow}>
      <span style={styles.statLabel}>{label}</span>
      <span style={{ ...styles.statValue, color: highlight ? '#16a34a' : '#1e293b' }}>{value}</span>
    </div>
  )
}

function StatusBadge({ status }) {
  const isOk = status === 'detected' || status === 'no_plate' || status === 'low_confidence'
  const label = STATUS_LABEL[status] || status
  return (
    <span style={{ ...styles.statusBadge, ...(isOk ? styles.statusOk : styles.statusWarn) }}>
      {isOk ? <MdCheckCircle size={13} /> : <MdErrorOutline size={13} />}
      {label}
    </span>
  )
}

function formatUptime(startedAtIso) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(startedAtIso).getTime()) / 1000))
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return h > 0 ? `${h}h ${m}m ${s}s` : m > 0 ? `${m}m ${s}s` : `${s}s`
}

const styles = {
  page: { padding: '24px', maxWidth: 1200, margin: '0 auto' },

  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 12 },
  headerLeft: { display: 'flex', alignItems: 'center', gap: 14 },
  iconWrap: { width: 44, height: 44, borderRadius: 12, background: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 22, fontWeight: 700, color: '#0f172a', margin: 0 },
  subtitle: { fontSize: 13, color: '#64748b', margin: '2px 0 0' },

  actionBtn: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '9px 18px', borderRadius: 8, border: 'none',
    fontSize: 14, fontWeight: 600, cursor: 'pointer', color: '#fff',
  },
  uploadBtn: { background: '#3b82f6' },
  analyzeBtn: { background: '#16a34a' },
  cameraSelect: {
    padding: '9px 12px', borderRadius: 8, border: '1px solid #cbd5e1',
    fontSize: 14, color: '#1e293b', background: '#fff', maxWidth: 200,
  },
  stopBtn: { background: '#ef4444' },

  errorBox: {
    background: '#fef2f2', border: '1px solid #fecaca',
    color: '#dc2626', borderRadius: 8, padding: '12px 16px',
    fontSize: 14, marginBottom: 16,
  },

  grid: { display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 20, marginBottom: 20 },

  card: {
    background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0',
    padding: '20px 24px', marginBottom: 20,
    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
  },
  cardTitle: {
    fontSize: 16, fontWeight: 600, color: '#0f172a', margin: '0 0 16px',
    display: 'flex', alignItems: 'center', gap: 8,
  },
  liveBadge: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    fontSize: 11, fontWeight: 700, color: '#dc2626',
    background: '#fef2f2', border: '1px solid #fecaca',
    borderRadius: 20, padding: '2px 8px',
  },
  countBadge: {
    fontSize: 12, fontWeight: 600, color: '#1d4ed8',
    background: '#eff6ff', border: '1px solid #bfdbfe',
    borderRadius: 20, padding: '2px 8px',
  },

  previewFrame: {
    width: '100%', aspectRatio: '16 / 9', borderRadius: 8,
    background: '#0f172a', display: 'flex', alignItems: 'center',
    justifyContent: 'center', overflow: 'hidden',
  },
  previewImg: { width: '100%', height: '100%', objectFit: 'contain' },
  previewEmpty: { color: '#94a3b8', fontSize: 14, textAlign: 'center', padding: '0 20px' },

  statRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '9px 0', borderBottom: '1px solid #f1f5f9', fontSize: 14,
  },
  statLabel: { color: '#64748b' },
  statValue: { fontWeight: 600 },

  emptyState: {
    textAlign: 'center', padding: '40px 20px',
    color: '#94a3b8', fontSize: 15,
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
  },

  table: { width: '100%', borderCollapse: 'collapse', fontSize: 14 },
  th: {
    padding: '10px 14px', background: '#f8fafc',
    color: '#475569', fontWeight: 600, fontSize: 12,
    textTransform: 'uppercase', letterSpacing: '0.04em',
    borderBottom: '2px solid #e2e8f0', textAlign: 'left',
  },
  tr: { borderBottom: '1px solid #f1f5f9' },
  td: { padding: '11px 14px', verticalAlign: 'middle', color: '#1e293b' },

  plate: { fontWeight: 600, fontFamily: 'monospace', fontSize: 13, color: '#1e293b' },

  statusBadge: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '3px 10px', borderRadius: 20,
    fontSize: 12, fontWeight: 600,
  },
  statusOk: { color: '#16a34a', background: '#f0fdf4' },
  statusWarn: { color: '#d97706', background: '#fffbeb' },
}
