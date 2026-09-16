/**
 * components/Modal.jsx
 * Lightweight popup dialog — replaces native window.alert() for
 * user-facing messages (validation, duplicate warnings, errors).
 */
import React, { useEffect } from 'react'
import { MdOutlineWarningAmber, MdOutlineErrorOutline, MdOutlineInfo, MdOutlineCheckCircle, MdClose } from 'react-icons/md'

const VARIANTS = {
  warning: { color: '#ea580c', bg: '#fff7ed', border: '#fed7aa', Icon: MdOutlineWarningAmber },
  error:   { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', Icon: MdOutlineErrorOutline },
  info:    { color: '#1d4ed8', bg: '#eff6ff', border: '#bfdbfe', Icon: MdOutlineInfo },
  success: { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', Icon: MdOutlineCheckCircle },
}

export default function Modal({ open, onClose, title, message, variant = 'info', autoCloseMs }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') onClose?.() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  useEffect(() => {
    if (!open || !autoCloseMs) return
    const t = setTimeout(() => onClose?.(), autoCloseMs)
    return () => clearTimeout(t)
  }, [open, autoCloseMs, onClose])

  if (!open) return null

  const v = VARIANTS[variant] || VARIANTS.info
  const { Icon } = v

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.dialog} onClick={e => e.stopPropagation()} role="alertdialog" aria-modal="true">
        <button style={styles.closeBtn} onClick={onClose} aria-label="Close">
          <MdClose size={18} />
        </button>
        <div style={{ ...styles.iconWrap, background: v.bg, border: `1px solid ${v.border}` }}>
          <Icon size={26} color={v.color} />
        </div>
        {title && <h3 style={styles.title}>{title}</h3>}
        {message && <p style={styles.message}>{message}</p>}
        <button style={{ ...styles.okBtn, background: v.color }} onClick={onClose}>
          OK
        </button>
      </div>
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000, padding: 16,
  },
  dialog: {
    position: 'relative', background: '#fff', borderRadius: 14,
    padding: '28px 28px 22px', maxWidth: 380, width: '100%',
    boxShadow: '0 20px 40px rgba(0,0,0,0.2)',
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    textAlign: 'center',
  },
  closeBtn: {
    position: 'absolute', top: 10, right: 10,
    border: 'none', background: 'transparent', color: '#94a3b8',
    cursor: 'pointer', padding: 4, borderRadius: 6, display: 'flex',
  },
  iconWrap: {
    width: 52, height: 52, borderRadius: '50%',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    marginBottom: 14,
  },
  title: { fontSize: 17, fontWeight: 700, color: '#0f172a', margin: '0 0 6px' },
  message: { fontSize: 14, color: '#64748b', margin: '0 0 18px', lineHeight: 1.5 },
  okBtn: {
    border: 'none', color: '#fff', fontWeight: 600, fontSize: 14,
    padding: '9px 28px', borderRadius: 8, cursor: 'pointer',
  },
}
