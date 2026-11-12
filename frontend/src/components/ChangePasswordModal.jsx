import { useState } from 'react'
import { changePassword } from '../api/pgguardian'
import './NewAnalysisModal.css'

export default function ChangePasswordModal({ onClose }) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSuccessMsg(null)

    if (!currentPassword) {
      setError('Ingresa tu contraseña actual.')
      return
    }
    if (newPassword.length < 12 || newPassword.length > 128 || !newPassword.trim()) {
      setError('La nueva contraseña debe tener entre 12 y 128 caracteres.')
      return
    }
    if (newPassword !== newPasswordConfirm) {
      setError('Las contraseñas nuevas no coinciden.')
      return
    }

    setIsSubmitting(true)
    try {
      const res = await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm,
      })
      setSuccessMsg(res.message)
      setCurrentPassword('')
      setNewPassword('')
      setNewPasswordConfirm('')
    } catch (err) {
      setError(err.message || 'No se pudo actualizar la contraseña.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="change-pwd-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose()
      }}
    >
      <div className="modal-card fade-in">
        <div className="modal-header">
          <div>
            <h2 id="change-pwd-title" className="modal-title">Cambiar contraseña</h2>
            <p className="modal-subtitle">
              Al actualizar tu contraseña se cerrarán tus demás sesiones activas.
            </p>
          </div>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Cerrar ventana"
          >
            ×
          </button>
        </div>

        {error && (
          <div className="modal-alert modal-alert--error" role="alert">
            {error}
          </div>
        )}
        {successMsg && (
          <div className="modal-alert modal-alert--success" role="status">
            {successMsg}
          </div>
        )}

        <form className="modal-form" onSubmit={handleSubmit} noValidate>
          <div className="field-group">
            <label htmlFor="pwd-current" className="field-label">Contraseña actual</label>
            <input
              id="pwd-current"
              type="password"
              className="field-input"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="field-group">
            <label htmlFor="pwd-new" className="field-label">Nueva contraseña (12–128 caracteres)</label>
            <input
              id="pwd-new"
              type="password"
              className="field-input"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              maxLength={128}
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="field-group">
            <label htmlFor="pwd-confirm" className="field-label">Confirmar nueva contraseña</label>
            <input
              id="pwd-confirm"
              type="password"
              className="field-input"
              value={newPasswordConfirm}
              onChange={(e) => setNewPasswordConfirm(e.target.value)}
              autoComplete="new-password"
              maxLength={128}
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={isSubmitting}>
              Cerrar
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Guardando…' : 'Actualizar contraseña'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

