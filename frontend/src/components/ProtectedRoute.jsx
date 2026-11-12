import { Navigate } from 'react-router-dom'

export default function ProtectedRoute({ user, authChecked, children }) {
  if (!authChecked) {
    return (
      <div className="auth-checking-screen" role="status" aria-live="polite">
        <span className="spinner" aria-hidden="true"></span>
        <span>Verificando sesión…</span>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/" replace />
  }

  return children
}

