/**
 * pages/Dashboard.jsx — Screen 1
 * Shows stats cards, recent alerts, and quick navigation links.
 */
import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { FaHome, FaStop, FaPlay, FaMapMarkedAlt, FaVideo, FaCar, FaExclamationTriangle, FaUpload } from 'react-icons/fa'
import {
  getDashboardSummary, getRecentAlerts,
  startSimulator, stopSimulator, getSimulatorStatus,
  uploadCameraFeed, stopCameraFeed, getCameraFeedStatus,
} from '../api/client'
import StatsCards from '../components/StatsCards'
import AlertList from '../components/AlertList'
import Modal from '../components/Modal'

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [simulatorRunning, setSimulatorRunning] = useState(false)
  const [feedRunning, setFeedRunning] = useState(false)
  const [feedFilename, setFeedFilename] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [modal, setModal] = useState({ open: false, title: '', message: '', variant: 'info' })
  const fileInputRef = useRef(null)

  const load = async () => {
    try {
      const [sumRes, alertRes, simRes, feedRes] = await Promise.all([
        getDashboardSummary(),
        getRecentAlerts({ limit: 5 }),
        getSimulatorStatus().catch(() => ({ data: { running: false } })),
        getCameraFeedStatus().catch(() => ({ data: { running: false, filename: null } })),
      ])
      setSummary(sumRes.data)
      setAlerts(alertRes.data)
      setSimulatorRunning(simRes.data.running)
      setFeedRunning(feedRes.data.running)
      setFeedFilename(feedRes.data.filename)
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
        setSimulatorRunning(false);
        setModal({ open: true, title: 'Simulator Stopped', message: 'The traffic simulator was stopped successfully.', variant: 'success' });
      } else {
        await startSimulator();
        setSimulatorRunning(true);
        setModal({ open: true, title: 'Simulator Started', message: 'The traffic simulator is now running.', variant: 'success' });
      }
    } catch (e) {
      console.error(e);
      const detail = e.response?.data?.detail;
      setModal({ open: true, title: 'Failed to Toggle Simulator', message: detail || 'Please try again.', variant: 'error' });
    }
  };

  const handleVideoButtonClick = () => {
    if (feedRunning) {
      stopVideoFeed();
    } else {
      fileInputRef.current?.click();
    }
  };

  const handleFileSelected = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file later
    if (!file) return;

    setUploading(true);
    try {
      await uploadCameraFeed(file, 'Camera-01');
      setFeedRunning(true);
      setFeedFilename(file.name);
      setModal({ open: true, title: 'Video Feed Started', message: `Streaming "${file.name}" to the ANPR pipeline.`, variant: 'success' });
    } catch (e) {
      console.error(e);
      const detail = e.response?.data?.detail;
      setModal({ open: true, title: 'Failed to Start Video Feed', message: detail || 'Please try again.', variant: 'error' });
    } finally {
      setUploading(false);
    }
  };

  const stopVideoFeed = async () => {
    try {
      await stopCameraFeed();
      setFeedRunning(false);
      setFeedFilename(null);
      setModal({ open: true, title: 'Video Feed Stopped', message: 'The uploaded video feed was stopped.', variant: 'success' });
    } catch (e) {
      console.error(e);
      const detail = e.response?.data?.detail;
      setModal({ open: true, title: 'Failed to Stop Video Feed', message: detail || 'Please try again.', variant: 'error' });
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 style={h1}><FaHome style={{ marginRight: 8, verticalAlign: 'middle' }} />Dashboard</h1>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            style={{ display: 'none' }}
            onChange={handleFileSelected}
          />
          <button
            onClick={handleVideoButtonClick}
            disabled={uploading}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: 'none',
              background: feedRunning ? '#ef4444' : '#3b82f6',
              color: 'white',
              fontWeight: 'bold',
              cursor: uploading ? 'not-allowed' : 'pointer',
              opacity: uploading ? 0.7 : 1,
            }}
            title={feedFilename ? `Currently streaming: ${feedFilename}` : undefined}
          >
            {uploading
              ? 'Uploading…'
              : feedRunning
                ? <><FaStop style={{ marginRight: 6, verticalAlign: 'middle' }} />Stop Video Feed</>
                : <><FaUpload style={{ marginRight: 6, verticalAlign: 'middle' }} />Upload Video Feed</>}
          </button>
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
            {simulatorRunning
              ? <><FaStop style={{ marginRight: 6, verticalAlign: 'middle' }} />Stop Simulator</>
              : <><FaPlay style={{ marginRight: 6, verticalAlign: 'middle' }} />Start Simulator</>}
          </button>
        </div>
      </div>
      {loading ? <p>Loading…</p> : (
        <>
          <StatsCards summary={summary} />

          {/* Quick actions */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
            <QuickLink to="/map"      icon={<FaMapMarkedAlt />}         label="View GIS Map" />
            <QuickLink to="/cameras"  icon={<FaVideo />}                label="Camera Registry" />
            <QuickLink to="/tracking" icon={<FaCar />}                  label="Track Vehicle" />
            <QuickLink to="/alerts"   icon={<FaExclamationTriangle />}  label="All Alerts" />
          </div>

          {/* Recent alerts */}
          <div style={card}>
            <h2 style={h2}>Recent Alerts</h2>
            <AlertList alerts={alerts} onRefresh={load} compact />
          </div>
        </>
      )}

      <Modal
        open={modal.open}
        title={modal.title}
        message={modal.message}
        variant={modal.variant}
        autoCloseMs={modal.variant === 'success' ? 2000 : undefined}
        onClose={() => setModal(m => ({ ...m, open: false }))}
      />
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
      <span style={{ fontSize: 22, display: 'flex', alignItems: 'center' }}>{icon}</span> {label}
    </Link>
  )
}

const h1 = { fontSize: 24, fontWeight: 700, marginBottom: 20 }
const h2 = { fontSize: 17, fontWeight: 600, marginBottom: 14, color: '#1e293b' }
const card = { background: 'var(--card-bg)', borderRadius: 10, padding: 20, boxShadow: '0 1px 4px rgba(0,0,0,.08)' }
