import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../context/AuthContext'

export default function Watchlist() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const { user } = useAuth()
  
  // Form state
  const [identifier, setIdentifier] = useState('')
  const [entityType, setEntityType] = useState('VEHICLE')
  const [priority, setPriority] = useState('HIGH')
  const [description, setDescription] = useState('')
  
  const fetchWatchlist = async () => {
    try {
      const res = await axios.get('/api/watchlist')
      setEntries(res.data)
    } catch (err) {
      setError('Failed to fetch watchlist.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchWatchlist()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      await axios.post('/api/watchlist', {
        identifier,
        entity_type: entityType,
        priority,
        description,
        active: true
      })
      setIdentifier('')
      setDescription('')
      fetchWatchlist()
    } catch (err) {
      alert('Failed to add entry')
    }
  }

  const handleDelete = async (id) => {
    try {
      await axios.delete(`/api/watchlist/${id}`)
      fetchWatchlist()
    } catch (err) {
      alert('Failed to delete entry')
    }
  }

  if (loading) return <div>Loading watchlist...</div>

  return (
    <div>
      <h2>Watchlist Registry</h2>
      {error && <div style={{color: 'red'}}>{error}</div>}
      
      {user?.role === 'ADMIN' && (
        <div style={{ marginBottom: 20, padding: 20, background: '#f8fafc', borderRadius: 8 }}>
          <h3>Add to Watchlist</h3>
          <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input required placeholder="Identifier (e.g. DL01AB1234)" value={identifier} onChange={e => setIdentifier(e.target.value)} />
            <select value={entityType} onChange={e => setEntityType(e.target.value)}>
              <option value="VEHICLE">VEHICLE</option>
              <option value="PERSON">PERSON</option>
            </select>
            <select value={priority} onChange={e => setPriority(e.target.value)}>
              <option value="LOW">LOW</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="HIGH">HIGH</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
            <input placeholder="Description" value={description} onChange={e => setDescription(e.target.value)} />
            <button type="submit">Add</button>
          </form>
        </div>
      )}

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#f1f5f9', textAlign: 'left' }}>
            <th style={{ padding: 10 }}>Identifier</th>
            <th style={{ padding: 10 }}>Type</th>
            <th style={{ padding: 10 }}>Priority</th>
            <th style={{ padding: 10 }}>Description</th>
            <th style={{ padding: 10 }}>Status</th>
            {user?.role === 'ADMIN' && <th style={{ padding: 10 }}>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {entries.map(entry => (
            <tr key={entry.id} style={{ borderBottom: '1px solid #e2e8f0' }}>
              <td style={{ padding: 10 }}>{entry.identifier}</td>
              <td style={{ padding: 10 }}>{entry.entity_type}</td>
              <td style={{ padding: 10 }}>{entry.priority}</td>
              <td style={{ padding: 10 }}>{entry.description}</td>
              <td style={{ padding: 10 }}>{entry.active ? 'Active' : 'Inactive'}</td>
              {user?.role === 'ADMIN' && (
                <td style={{ padding: 10 }}>
                  <button onClick={() => handleDelete(entry.id)} disabled={!entry.active}>Remove</button>
                </td>
              )}
            </tr>
          ))}
          {entries.length === 0 && (
            <tr><td colSpan="6" style={{ padding: 10, textAlign: 'center' }}>No watchlist entries found.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
