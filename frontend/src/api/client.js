/**
 * api/client.js - Axios instance with automatic Bearer token injection.
 * Reads token from localStorage on every request.
 * 401 responses auto-clear the session and redirect to /login.
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 10000,
})

// Attach Bearer token from localStorage on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cctv_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On 401: clear session and redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('cctv_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ---- Auth ----
export const loginApi    = (data)    => api.post('/auth/login', data)
export const getMeApi    = ()        => api.get('/auth/me')

// ---- Cameras ----
export const getCameras   = (params = {}) => api.get('/cameras', { params })
export const createCamera = (data)        => api.post('/cameras', data)
export const getCamera    = (id)          => api.get(`/cameras/${id}`)
export const bulkUploadCameras = (file)   => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/cameras/bulk-upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
export const downloadTemplateUrl = '/api/cameras/bulk-upload/template'
export const getCamerasGapAnalysis = () => api.get('/cameras/gap-analysis')

// ---- Events ----
export const postEvent   = (data)        => api.post('/events', data)
export const getEvents   = (params = {}) => api.get('/events', { params })

// ---- Vehicles ----
export const getVehicleHistory = (vn) =>
  api.get(`/vehicles/${encodeURIComponent(vn)}/history`)

// ---- Alerts ----
export const getAlerts        = (params = {}) => api.get('/alerts', { params })
export const acknowledgeAlert = (id)           => api.post(`/alerts/${id}/acknowledge`)
export const resolveAlert     = (id)           => api.post(`/alerts/${id}/resolve`)

// ---- Dashboard ----
export const getDashboardSummary = () => api.get('/dashboard/summary')
export const getRecentAlerts     = (params = {}) => api.get('/dashboard/recent-alerts', { params })

// ---- Simulator ----
export const startSimulator = () => api.post('/simulator/start')
export const stopSimulator  = () => api.post('/simulator/stop')
export const getSimulatorStatus = () => api.get('/simulator/status')

// ---- Camera Feed (video file -> ANPR pipeline) ----
export const uploadCameraFeed = (file, cameraId) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('camera_id', cameraId)
  return api.post('/camera-feed/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
export const stopCameraFeed = ()      => api.post('/camera-feed/stop')
export const getCameraFeedStatus = () => api.get('/camera-feed/status')
export const getCameraFeedActivity = () => api.get('/camera-feed/activity')

// ---- Watchlist ----
export const getWatchlist          = ()     => api.get('/watchlist')
export const addToWatchlist        = (data) => api.post('/watchlist', data)
export const removeFromWatchlist   = (id)   => api.delete(`/watchlist/${id}`)
export const getWatchlistLocations = ()     => api.get('/watchlist/locations')

export default api
