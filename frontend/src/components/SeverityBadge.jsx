import './SeverityBadge.css'

export default function SeverityBadge({ severity }) {
  const s = (severity || 'ok').toUpperCase()

  const map = {
    HIGH: { label: 'Alta', className: 'severity--high' },
    CRITICAL: { label: 'Crítico', className: 'severity--high' },
    MEDIUM: { label: 'Media', className: 'severity--medium' },
    LOW: { label: 'Baja', className: 'severity--low' },
    OK: { label: 'OK', className: 'severity--ok' },
    WARNING: { label: 'Advertencia', className: 'severity--medium' },
    NO_APLICA: { label: 'No aplica', className: 'severity--na' },
  }

  const info = map[s] || map['OK']

  return (
    <span className={`severity-badge ${info.className}`}>
      {info.label}
    </span>
  )
}
