import { useRef, useState } from 'react'
import { createAnalysis } from '../api/pgguardian'
import './NewAnalysisModal.css'

const MAX_FILES = 5
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
const MAX_TOTAL_SIZE_BYTES = 25 * 1024 * 1024

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function hasValidSqlExtension(filename) {
  const clean = (filename || '').trim()
  const lastDot = clean.lastIndexOf('.')
  return lastDot > 0 && clean.slice(lastDot).toLowerCase() === '.sql'
}

export default function NewAnalysisModal({ onClose, onCreated, onOpenResultTab }) {
  const fileInputRef = useRef(null)
  const [analysisName, setAnalysisName] = useState('')
  const [items, setItems] = useState([])
  const [error, setError] = useState(null)
  const [isDraggingFiles, setIsDraggingFiles] = useState(false)
  const [dragIndex, setDragIndex] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [result, setResult] = useState(null)

  const totalBytes = items.reduce((sum, item) => sum + item.file.size, 0)

  const addFiles = (fileList) => {
    const incoming = Array.from(fileList || [])
    if (incoming.length === 0) return

    const errors = []
    const nextItems = [...items]
    let runningBytes = totalBytes

    for (const file of incoming) {
      const alreadyAdded = nextItems.some(
        (entry) =>
          entry.file.name === file.name &&
          entry.file.size === file.size &&
          entry.file.lastModified === file.lastModified,
      )
      if (alreadyAdded) {
        errors.push(`El archivo "${file.name}" ya está en la lista.`)
        continue
      }

      if (!hasValidSqlExtension(file.name)) {
        errors.push(`"${file.name}": solo se permiten archivos con extensión .sql.`)
        continue
      }

      if (file.size > MAX_FILE_SIZE_BYTES) {
        errors.push(`"${file.name}": excede el límite máximo de 10 MB por archivo.`)
        continue
      }

      if (nextItems.length >= MAX_FILES) {
        errors.push(`Solo puedes cargar un máximo de ${MAX_FILES} archivos .sql por análisis.`)
        break
      }

      if (runningBytes + file.size > MAX_TOTAL_SIZE_BYTES) {
        errors.push(`"${file.name}": el peso total combinado supera el límite de 25 MB.`)
        continue
      }

      runningBytes += file.size
      nextItems.push({
        id: `${file.name}-${file.size}-${file.lastModified}-${nextItems.length}-${Date.now()}`,
        file,
      })
    }

    setItems(nextItems)
    setError(errors.length > 0 ? errors.join(' ') : null)
  }

  const handleFileChange = (e) => {
    addFiles(e.target.files)
    e.target.value = ''
  }

  const handleDropZoneDrop = (e) => {
    e.preventDefault()
    setIsDraggingFiles(false)
    if (isSubmitting || result) return
    addFiles(e.dataTransfer.files)
  }

  const moveItem = (index, delta) => {
    const target = index + delta
    if (target < 0 || target >= items.length) return
    const next = [...items]
    const [moved] = next.splice(index, 1)
    next.splice(target, 0, moved)
    setItems(next)
  }

  const handleRowDrop = (targetIndex) => {
    if (dragIndex === null || dragIndex === targetIndex) {
      setDragIndex(null)
      return
    }
    const next = [...items]
    const [moved] = next.splice(dragIndex, 1)
    next.splice(targetIndex, 0, moved)
    setItems(next)
    setDragIndex(null)
  }

  const removeItem = (index) => {
    setItems((prev) => prev.filter((_, idx) => idx !== index))
    setError(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (items.length === 0) {
      setError('Debes seleccionar al menos 1 archivo .sql antes de enviar.')
      return
    }

    setIsSubmitting(true)
    setError(null)
    try {
      const orderedFiles = items.map((entry) => entry.file)
      const orderIndices = orderedFiles.map((_, idx) => idx)
      const data = await createAnalysis(orderedFiles, orderIndices, analysisName)
      setResult(data)
      if (onCreated) onCreated(data)
    } catch (err) {
      setError(err.message || 'No se pudieron validar los scripts SQL.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleReset = () => {
    setAnalysisName('')
    setItems([])
    setError(null)
    setResult(null)
  }

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-analysis-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose()
      }}
    >
      <div className="modal-card fade-in">
        <div className="modal-header">
          <div>
            <h2 id="new-analysis-title" className="modal-title">Nuevo análisis SQL</h2>
            <p className="modal-subtitle">
              Carga hasta 5 scripts <code className="mono">.sql</code> (UTF-8) y define su orden de ejecución.
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
            <span>{error}</span>
          </div>
        )}

        {result ? (
          <div className="analysis-result">
            <div className="modal-alert modal-alert--success">
              <div>
                <strong>{result.message}</strong>
                <div className="result-meta">
                  Nombre: <strong>{result.name}</strong> · Estado: <strong>{result.status}</strong> ·{' '}
                  {result.file_count} archivo(s) · {formatBytes(result.total_size_bytes)}
                  {result.sandbox_db_name && (
                    <>
                      {' '}· Sandbox: <code className="mono">{result.sandbox_db_name}</code> ({result.sandbox_status}) ·{' '}
                      {result.executed_statements} sentencias ({result.execution_time_ms} ms)
                    </>
                  )}
                  {result.scan && (
                    <>
                      {' '}· Health Score: <strong>{result.scan.health_score}/100</strong> ·{' '}
                      {result.scan.total_findings} hallazgo(s) ·{' '}
                      {result.scan.evaluated_detectors} detectores activos / {result.scan.not_applicable_detectors} N/A
                    </>
                  )}
                </div>
              </div>
            </div>

            <div className="result-table-wrap">
              <table className="result-table">
                <thead>
                  <tr>
                    <th>Orden</th>
                    <th>Archivo</th>
                    <th>Tamaño</th>
                    <th>Codificación</th>
                    <th>Líneas</th>
                  </tr>
                </thead>
                <tbody>
                  {result.files.map((f) => (
                    <tr key={`${f.order}-${f.filename}`}>
                      <td><span className="order-badge">#{f.order}</span></td>
                      <td className="mono">{f.filename}</td>
                      <td>{formatBytes(f.size_bytes)}</td>
                      <td>{f.encoding.toUpperCase()}</td>
                      <td>{f.line_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="modal-footer">
              <button type="button" className="btn-secondary" onClick={handleReset}>
                Cargar otros archivos
              </button>
              {onOpenResultTab && (
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => onOpenResultTab(result)}
                >
                  Ver pestaña en Dashboard
                </button>
              )}
              <button type="button" className="btn-secondary" onClick={onClose}>
                Cerrar
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="modal-form">
            <label className="field-group">
              <span className="field-label">Nombre del análisis (opcional)</span>
              <input
                type="text"
                className="field-input"
                maxLength={200}
                value={analysisName}
                onChange={(e) => setAnalysisName(e.target.value)}
                placeholder="Ej. Esquema tienda v1 (por defecto usa el primer .sql)"
                disabled={isSubmitting}
              />
            </label>

            <div
              className={`dropzone ${isDraggingFiles ? 'dropzone--active' : ''}`}
              onDragOver={(e) => {
                e.preventDefault()
                setIsDraggingFiles(true)
              }}
              onDragLeave={() => setIsDraggingFiles(false)}
              onDrop={handleDropZoneDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".sql"
                multiple
                onChange={handleFileChange}
                className="dropzone-input"
                aria-label="Seleccionar archivos SQL"
              />
              <p className="dropzone-text">
                Arrastra tus scripts aquí o{' '}
                <button
                  type="button"
                  className="dropzone-trigger"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isSubmitting || items.length >= MAX_FILES}
                >
                  selecciona archivos .sql
                </button>
              </p>
              <p className="dropzone-hint">
                Codificación UTF-8 · Máx. 5 archivos · Hasta 10 MB por archivo · Máx. 25 MB acumulados
              </p>
            </div>

            <div className="queue-header">
              <span className="queue-title">Orden de ejecución</span>
              <span className="queue-stats">
                {items.length} / {MAX_FILES} archivos · {formatBytes(totalBytes)} / 25 MB
              </span>
            </div>

            {items.length === 0 ? (
              <div className="queue-empty">
                Aún no has agregado archivos <code className="mono">.sql</code>.
              </div>
            ) : (
              <ul className="file-queue">
                {items.map((item, idx) => (
                  <li
                    key={item.id}
                    className={`file-row ${dragIndex === idx ? 'file-row--dragging' : ''}`}
                    draggable={!isSubmitting}
                    onDragStart={() => setDragIndex(idx)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={() => handleRowDrop(idx)}
                    onDragEnd={() => setDragIndex(null)}
                  >
                    <span className="order-badge">#{idx + 1}</span>
                    <div className="file-info">
                      <span className="file-name mono">{item.file.name}</span>
                      <span className="file-size">{formatBytes(item.file.size)}</span>
                    </div>
                    <div className="file-controls">
                      <button
                        type="button"
                        className="icon-btn"
                        onClick={() => moveItem(idx, -1)}
                        disabled={idx === 0 || isSubmitting}
                        aria-label={`Subir ${item.file.name}`}
                        title="Subir en el orden"
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        className="icon-btn"
                        onClick={() => moveItem(idx, 1)}
                        disabled={idx === items.length - 1 || isSubmitting}
                        aria-label={`Bajar ${item.file.name}`}
                        title="Bajar en el orden"
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        className="icon-btn icon-btn--danger"
                        onClick={() => removeItem(idx)}
                        disabled={isSubmitting}
                        aria-label={`Quitar ${item.file.name}`}
                        title="Quitar archivo"
                      >
                        ×
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <div className="modal-footer">
              <button
                type="button"
                className="btn-secondary"
                onClick={onClose}
                disabled={isSubmitting}
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="btn-primary"
                disabled={items.length === 0 || isSubmitting}
              >
                {isSubmitting ? 'Validando…' : 'Validar y crear análisis'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

