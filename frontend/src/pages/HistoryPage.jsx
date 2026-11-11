import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  deleteAnalysis,
  getAnalysisDetail,
  listAnalyses,
} from '../api/pgguardian'
import SeverityBadge from '../components/SeverityBadge'
import RemediationPanel from '../components/RemediationPanel'
import { hasRemediationInfo } from '../utils/remediation'
import './PageCommon.css'
import './HistoryPage.css'

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function formatDate(iso) {
  return new Date(iso).toLocaleString('es-MX')
}

export default function HistoryPage({ currentUser, refreshKey, onOpenTab, onDeleted }) {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedDetail, setSelectedDetail] = useState(null)
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    listAnalyses()
      .then((res) => {
        if (!cancelled) {
          setItems(res.items || [])
          setSelectedDetail(null)
          setError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [currentUser, refreshKey, reloadTick])

  const handleRefresh = () => {
    setIsLoading(true)
    setReloadTick((t) => t + 1)
  }

  const handleInspect = async (analysisId) => {
    setIsLoadingDetail(true)
    setError(null)
    try {
      const detail = await getAnalysisDetail(analysisId)
      setSelectedDetail(detail)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoadingDetail(false)
    }
  }

  const handleOpenInTab = async (analysisId) => {
    setIsLoadingDetail(true)
    setError(null)
    try {
      const detail =
        selectedDetail?.id === analysisId
          ? selectedDetail
          : await getAnalysisDetail(analysisId)
      if (onOpenTab) {
        onOpenTab(detail)
        navigate('/')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoadingDetail(false)
    }
  }

  const handleDelete = async (analysisId, name) => {
    setDeletingId(analysisId)
    setError(null)
    try {
      await deleteAnalysis(analysisId)
      setItems((prev) => prev.filter((item) => item.id !== analysisId))
      if (selectedDetail?.id === analysisId) {
        setSelectedDetail(null)
      }
      if (onDeleted) onDeleted(analysisId)
    } catch (err) {
      setError(`Error al eliminar "${name}": ${err.message}`)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="page fade-in">
      <div className="history-header">
        <div className="page-header">
          <h1 className="page-title">Historial de Análisis</h1>
          <p className="page-subtitle">
            Reportes de scripts SQL pertenecientes a <code className="mono">{currentUser}</code>
          </p>
        </div>
        <button type="button" className="history-refresh-btn" onClick={handleRefresh} disabled={isLoading}>
          {isLoading ? 'Cargando…' : 'Actualizar historial'}
        </button>
      </div>

      {error && (
        <div className="history-error" role="alert">
          <span>{error}</span>
        </div>
      )}

      {isLoading ? (
        <div className="skeleton" style={{ height: 200, borderRadius: 14 }}></div>
      ) : items.length === 0 ? (
        <div className="history-empty">
          <p>
            No hay análisis registrados para <code className="mono">{currentUser}</code>.
          </p>
          <p className="history-empty-hint">
            Usa el botón <strong>«Nuevo análisis»</strong> en la barra superior para cargar scripts <code className="mono">.sql</code>.
          </p>
        </div>
      ) : (
        <div className="history-table-card">
          <table className="history-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Fecha</th>
                <th>Health Score</th>
                <th>Hallazgos</th>
                <th>Archivos</th>
                <th>Sandbox (24 h)</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const isDestroyed = item.sandbox_status === 'destroyed'
                return (
                  <tr key={item.id}>
                    <td>
                      <div className="history-name">{item.name}</div>
                      <div className="history-id mono">{item.id}</div>
                    </td>
                    <td>{formatDate(item.created_at)}</td>
                    <td>
                      <span className="score-pill">{item.health_score}/100</span>
                    </td>
                    <td>{item.total_findings}</td>
                    <td>
                      {item.file_count} ({formatBytes(item.total_size_bytes)})
                    </td>
                    <td>
                      <span className={`sandbox-pill ${isDestroyed ? 'sandbox-pill--destroyed' : 'sandbox-pill--active'}`}>
                        {isDestroyed ? 'Purgado (24 h)' : 'Activo'}
                      </span>
                    </td>
                    <td>
                      <div className="history-actions">
                        <button
                          type="button"
                          className="history-btn"
                          onClick={() => handleOpenInTab(item.id)}
                          disabled={isLoadingDetail}
                        >
                          Abrir pestaña
                        </button>
                        <button
                          type="button"
                          className="history-btn"
                          onClick={() => handleInspect(item.id)}
                          disabled={isLoadingDetail}
                        >
                          Ver detalle
                        </button>
                        <button
                          type="button"
                          className="history-btn history-btn--danger"
                          onClick={() => handleDelete(item.id, item.name)}
                          disabled={deletingId === item.id}
                        >
                          {deletingId === item.id ? 'Eliminando…' : 'Eliminar'}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {selectedDetail && (
        <div className="history-detail-card fade-in">
          <div className="detail-card-header">
            <div>
              <h2 className="detail-card-title">{selectedDetail.name}</h2>
              <p className="detail-card-meta">
                Creado: {formatDate(selectedDetail.created_at)} · Score:{' '}
                <strong>{selectedDetail.health_score ?? selectedDetail.scan?.health_score}/100</strong> ·{' '}
                Sandbox: <code className="mono">{selectedDetail.sandbox_db_name}</code> (
                {selectedDetail.sandbox_status === 'destroyed'
                  ? 'Base temporal purgada tras 24 h — reporte conservado'
                  : `Expira: ${formatDate(selectedDetail.sandbox_expires_at)}`}
                )
              </p>
            </div>
            <button type="button" className="history-btn" onClick={() => setSelectedDetail(null)}>
              Cerrar detalle
            </button>
          </div>

          <div className="detail-categories">
            {Object.entries(selectedDetail.scan?.categories || {}).map(([catKey, cat]) => (
              <div key={catKey} className="detail-category-box">
                <h3 className="detail-category-title">{cat.label}</h3>
                <ul className="detail-detector-list">
                  {Object.entries(cat.detectors || {}).map(([detKey, det]) => {
                    const isNa = det.status === 'no_aplica'
                    const firstActionable = !isNa && Array.isArray(det.data)
                      ? det.data.find((row) => hasRemediationInfo(row))
                      : null
                    return (
                      <li key={detKey} className="detail-detector-item">
                        <div className="detail-detector-row">
                          <span>{det.label}</span>
                          {isNa ? (
                            <SeverityBadge severity="NO_APLICA" />
                          ) : (
                            <span className="detail-count-badge">{det.count} hallazgo(s)</span>
                          )}
                        </div>
                        {firstActionable && <RemediationPanel finding={firstActionable} />}
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

