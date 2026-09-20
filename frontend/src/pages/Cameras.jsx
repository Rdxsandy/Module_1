import React, { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCameras, createCamera, bulkUploadCameras, downloadTemplateUrl } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'

const STATUS_OPTS = ['', 'ONLINE', 'OFFLINE', 'MAINTENANCE']
const TYPE_OPTS   = ['', 'ANPR', 'Fixed', 'PTZ', 'Dome']

export default function Cameras() {
  const [cameras, setCameras] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch]   = useState('')
  const [dept, setDept]       = useState('')
  const [status, setStatus]   = useState('')
  const [type, setType]       = useState('')
  
  // Single Camera Add
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name:'', department:'Traffic', camera_type:'ANPR', owner:'', latitude:'', longitude:'', status:'ONLINE',
    installation_date:'', last_maintenance_date:'', coverage_radius_meters: 50,
  })
  const [saving, setSaving] = useState(false)
  
  // Bulk Upload
  const [showBulkForm, setShowBulkForm] = useState(false)
  const [bulkFile, setBulkFile] = useState(null)
  const [bulkSaving, setBulkSaving] = useState(false)
  const [bulkResult, setBulkResult] = useState(null)
  const fileInputRef = useRef(null)
  const [modal, setModal] = useState({ open: false, title: '', message: '', variant: 'info' })

  const navigate = useNavigate()
  const { user, token } = useAuth()
  const isAdmin = user?.role === 'ADMIN'

  const load = async () => {
    setLoading(true)
    try {
      const res = await getCameras({ search, department: dept, status, camera_type: type })
      setCameras(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [search, dept, status, type])

  const handleSave = async (e) => {
    e.preventDefault()

    const trimmedName = form.name.trim()
    const duplicate = cameras.find(c => c.name.toLowerCase() === trimmedName.toLowerCase())
    if (duplicate) {
      setModal({
        open: true,
        title: 'Camera Name Already Exists',
        message: `A camera named "${trimmedName}" is already registered. Please choose a different name.`,
        variant: 'warning',
      })
      return
    }

    setSaving(true)
    try {
      await createCamera({
        ...form,
        installation_date: form.installation_date || null,
        last_maintenance_date: form.last_maintenance_date || null,
        coverage_radius_meters: Number(form.coverage_radius_meters) || 50,
      })
      setForm({
        name:'', department:'Traffic', camera_type:'ANPR', owner:'', latitude:'', longitude:'', status:'ONLINE',
        installation_date:'', last_maintenance_date:'', coverage_radius_meters: 50,
      })
      setShowForm(false)
      load()
      setModal({ open: true, title: 'Camera Saved', message: `"${trimmedName}" was added to the registry successfully.`, variant: 'success' })
    } catch (err) {
      const detail = err.response?.data?.detail
      if (err.response?.status === 409) {
        setModal({
          open: true,
          title: 'Camera Name Already Exists',
          message: detail || `A camera named "${trimmedName}" is already registered.`,
          variant: 'warning',
        })
      } else if (Array.isArray(detail)) {
        // Pydantic validation errors — each item has loc + msg
        const msgs = detail.map(d => `${d.loc?.slice(1).join('.')||'field'}: ${d.msg}`).join('\n')
        setModal({ open: true, title: 'Validation Error', message: msgs, variant: 'error' })
      } else {
        setModal({ open: true, title: 'Failed to Create Camera', message: detail || 'Please try again.', variant: 'error' })
      }
    } finally {
      setSaving(false)
    }
  }

  const handleExportCsv = () => {
    const headers = [
      'id', 'name', 'department', 'camera_type', 'owner', 'latitude', 'longitude', 'status',
      'installation_date', 'last_maintenance_date', 'coverage_radius_meters',
      'vms_type', 'vendor', 'storage_type', 'retention_days', 'description', 'created_at',
    ]
    const escape = (val) => {
      if (val === null || val === undefined) return ''
      const s = String(val)
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
    }
    const rows = cameras.map(c => headers.map(h => escape(c[h])).join(','))
    const csv = [headers.join(','), ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `cameras_export_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleBulkUpload = async (e) => {
    e.preventDefault()
    if (!bulkFile) return
    setBulkSaving(true)
    setBulkResult(null)
    try {
      const res = await bulkUploadCameras(bulkFile)
      setBulkResult(res.data)
      setBulkFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      load() // Refresh table
    } catch (err) {
      setModal({ open: true, title: 'Bulk Upload Failed', message: err.response?.data?.detail || 'Please try again.', variant: 'error' })
    } finally {
      setBulkSaving(false)
    }
  }

  return (
    <div>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
        <h1 style={h1}>📹 Camera Registry</h1>
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={handleExportCsv} disabled={cameras.length === 0} style={secondaryBtn}>
            ⬇️ Export to CSV
          </button>
          {isAdmin && (
            <>
              <button onClick={() => { setShowBulkForm(v => !v); setShowForm(false) }} style={secondaryBtn}>
                {showBulkForm ? 'Cancel Bulk Upload' : 'Bulk Upload'}
              </button>
              <button onClick={() => { setShowForm(v => !v); setShowBulkForm(false) }} style={primaryBtn}>
                {showForm ? 'Cancel' : '+ Add Camera'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Bulk Upload UI */}
      {showBulkForm && isAdmin && (
        <div style={formCard}>
          <h2 style={{ marginTop:0, marginBottom:16, fontSize:18, color:'#1e293b' }}>Bulk Upload Cameras (CSV)</h2>
          <p style={{ color:'#64748b', fontSize:14, marginBottom:20 }}>
            Upload a CSV file containing multiple cameras. Use the official template for the correct column format.
          </p>
          
          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
            <div style={{ flex: 1, padding: 16, background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
              <div style={{ fontWeight: 600, marginBottom: 8, color: '#334155' }}>Step 1: Download Template</div>
              {/* Note: The template download needs the Bearer token if we made it protected, but since it's just a file download, we can fetch it via window.location if public, or use an authenticated fetch. Since our route expects get_current_user, we can just use a fetch and Blob to trigger download */}
              <button 
                type="button" 
                onClick={async () => {
                  try {
                    const r = await fetch(downloadTemplateUrl, { headers: { Authorization: `Bearer ${token}` } })
                    const blob = await r.blob()
                    const url = window.URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = 'cameras_template.csv'
                    a.click()
                  } catch (e) { setModal({ open: true, title: 'Download Failed', message: 'Failed to download template.', variant: 'error' }) }
                }}
                style={{...secondaryBtn, fontSize: 13, padding: '6px 12px'}}
              >
                📥 Download CSV Template
              </button>
            </div>
            
            <div style={{ flex: 1, padding: 16, background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
              <div style={{ fontWeight: 600, marginBottom: 8, color: '#334155' }}>Step 2: Upload Data</div>
              <form onSubmit={handleBulkUpload} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <input 
                  type="file" 
                  accept=".csv"
                  onChange={e => setBulkFile(e.target.files[0])}
                  ref={fileInputRef}
                  style={{ fontSize: 14 }}
                />
                <button type="submit" disabled={!bulkFile || bulkSaving} style={{...primaryBtn, alignSelf: 'flex-start'}}>
                  {bulkSaving ? 'Uploading...' : 'Upload & Import'}
                </button>
              </form>
            </div>
          </div>

          {/* Bulk Upload Results */}
          {bulkResult && (
            <div style={{ marginTop: 24, padding: 16, background: bulkResult.failed > 0 ? '#fff1f2' : '#f0fdf4', border: `1px solid ${bulkResult.failed > 0 ? '#fecdd3' : '#bbf7d0'}`, borderRadius: 8 }}>
              <h3 style={{ marginTop: 0, fontSize: 16, color: bulkResult.failed > 0 ? '#be123c' : '#15803d' }}>
                Upload Complete
              </h3>
              <div style={{ display: 'flex', gap: 24, margin: '12px 0' }}>
                <div style={{ fontSize: 14 }}>Total Processed: <strong>{bulkResult.total}</strong></div>
                <div style={{ fontSize: 14, color: '#15803d' }}>Successfully Imported: <strong>{bulkResult.imported}</strong></div>
                <div style={{ fontSize: 14, color: '#be123c' }}>Failed: <strong>{bulkResult.failed}</strong></div>
              </div>
              
              {bulkResult.errors?.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#9f1239', marginBottom: 8 }}>Validation Errors:</div>
                  <div style={{ maxHeight: 150, overflowY: 'auto', background: '#fff', border: '1px solid #fecdd3', borderRadius: 4 }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ background: '#ffe4e6', textAlign: 'left' }}>
                          <th style={{ padding: '6px 12px', borderBottom: '1px solid #fecdd3', width: 60 }}>Row</th>
                          <th style={{ padding: '6px 12px', borderBottom: '1px solid #fecdd3' }}>Error Message</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bulkResult.errors.map((err, i) => (
                          <tr key={i}>
                            <td style={{ padding: '6px 12px', borderBottom: '1px solid #fecdd3' }}>{err.row}</td>
                            <td style={{ padding: '6px 12px', borderBottom: '1px solid #fecdd3' }}>{err.message}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Add Camera Form */}
      {showForm && isAdmin && (
        <form onSubmit={handleSave} style={formCard}>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginBottom:16 }}>
            <label style={lbl}>Name <input required style={inp} value={form.name} onChange={e=>setForm({...form, name:e.target.value})} /></label>
            <label style={lbl}>Department <input required style={inp} value={form.department} onChange={e=>setForm({...form, department:e.target.value})} /></label>
            <label style={lbl}>Type 
              <select required style={inp} value={form.camera_type} onChange={e=>setForm({...form, camera_type:e.target.value})}>
                <option>ANPR</option><option>Fixed</option><option>PTZ</option><option>Dome</option>
              </select>
            </label>
            <label style={lbl}>Status
              <select required style={inp} value={form.status} onChange={e=>setForm({...form, status:e.target.value})}>
                <option value="ONLINE">ONLINE</option>
                <option value="OFFLINE">OFFLINE</option>
                <option value="MAINTENANCE">MAINTENANCE</option>
              </select>
            </label>
            <label style={lbl}>Owner <input style={inp} value={form.owner} onChange={e=>setForm({...form, owner:e.target.value})} /></label>
            <label style={lbl}>Latitude <input required type="number" step="any" style={inp} value={form.latitude} onChange={e=>setForm({...form, latitude:e.target.value})} /></label>
            <label style={lbl}>Longitude <input required type="number" step="any" style={inp} value={form.longitude} onChange={e=>setForm({...form, longitude:e.target.value})} /></label>
            <label style={lbl}>Installation Date <input type="date" style={inp} value={form.installation_date} onChange={e=>setForm({...form, installation_date:e.target.value})} /></label>
            <label style={lbl}>Last Maintenance Date <input type="date" style={inp} value={form.last_maintenance_date} onChange={e=>setForm({...form, last_maintenance_date:e.target.value})} /></label>
            <label style={lbl}>Coverage Radius (m) <input type="number" min="0" step="1" style={inp} value={form.coverage_radius_meters} onChange={e=>setForm({...form, coverage_radius_meters:e.target.value})} /></label>
          </div>
          <button type="submit" disabled={saving} style={primaryBtn}>{saving ? 'Saving...' : 'Save Camera'}</button>
        </form>
      )}

      {/* Filters */}
      <div style={filterBar}>
        <input placeholder="Search name..." style={inp} value={search} onChange={e=>setSearch(e.target.value)} />
        <input placeholder="Department" style={inp} value={dept} onChange={e=>setDept(e.target.value)} />
        <select style={inp} value={type} onChange={e=>setType(e.target.value)}>
          {TYPE_OPTS.map(o => <option key={o} value={o}>{o || 'All Types'}</option>)}
        </select>
        <select style={inp} value={status} onChange={e=>setStatus(e.target.value)}>
          {STATUS_OPTS.map(o => <option key={o} value={o}>{o || 'All Statuses'}</option>)}
        </select>
      </div>

      {/* Table */}
      <div style={tableWrap}>
        <table style={table}>
          <thead>
            <tr style={trHead}>
              <th style={th}>ID</th>
              <th style={th}>Name</th>
              <th style={th}>Type</th>
              <th style={th}>Department</th>
              <th style={th}>Status</th>
              <th style={th}>Added</th>
            </tr>
          </thead>
          <tbody>
            {loading ? <tr><td colSpan="6" style={{padding:20, textAlign:'center'}}>Loading...</td></tr> : 
             cameras.length === 0 ? <tr><td colSpan="6" style={{padding:20, textAlign:'center', color:'#666'}}>No cameras found</td></tr> :
             cameras.map(c => (
              <tr key={c.id} style={trBody}>
                <td style={td}>{c.id}</td>
                <td style={td}><span style={{color:'#1a56db', cursor:'pointer'}} onClick={() => navigate(`/map?camera=${c.id}`)}>{c.name}</span></td>
                <td style={td}>{c.camera_type}</td>
                <td style={td}>{c.department}</td>
                <td style={td}>
                  <span style={{...badge, background: c.status === 'online' ? '#def7ec' : c.status === 'offline' ? '#fde8e8' : '#fef3c7', color: c.status === 'online' ? '#03543f' : c.status === 'offline' ? '#9b1c1c' : '#92400e'}}>
                    {c.status}
                  </span>
                </td>
                <td style={td}>{new Date(c.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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

// Styles
const h1 = { fontSize:24, fontWeight:700, margin:0, color:'#1e293b' }
const filterBar = { display:'flex', gap:12, marginBottom:16, background:'#fff', padding:16, borderRadius:8, boxShadow:'0 1px 2px rgba(0,0,0,0.05)' }
const inp = { padding:'8px 12px', border:'1px solid #d1d5db', borderRadius:6, outline:'none', flex:1, fontSize:14 }
const lbl = { display:'flex', flexDirection:'column', gap:4, fontSize:13, fontWeight:600, color:'#475569' }
const primaryBtn = { background:'#1a56db', color:'#fff', border:'none', padding:'8px 16px', borderRadius:6, cursor:'pointer', fontWeight:500, fontSize:14 }
const secondaryBtn = { background:'#fff', color:'#1e293b', border:'1px solid #d1d5db', padding:'8px 16px', borderRadius:6, cursor:'pointer', fontWeight:500, fontSize:14 }
const formCard = { background:'#fff', padding:20, borderRadius:8, marginBottom:20, border:'1px solid #e2e8f0' }
const tableWrap = { background:'#fff', borderRadius:8, border:'1px solid #e2e8f0', overflow:'hidden' }
const table = { width:'100%', borderCollapse:'collapse', fontSize:14 }
const trHead = { background:'#f8fafc', borderBottom:'1px solid #e2e8f0', textAlign:'left' }
const th = { padding:'12px 16px', fontWeight:600, color:'#475569' }
const trBody = { borderBottom:'1px solid #e2e8f0' }
const td = { padding:'12px 16px', color:'#1e293b' }
const badge = { padding:'2px 8px', borderRadius:12, fontSize:12, fontWeight:600, textTransform:'uppercase' }
