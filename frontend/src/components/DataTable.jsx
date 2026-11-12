import React, { useState } from 'react'
import SeverityBadge from './SeverityBadge'
import SqlRecommendation from './SqlRecommendation'
import RemediationPanel from './RemediationPanel'
import { hasRemediationInfo } from '../utils/remediation'
import './DataTable.css'

export default function DataTable({ title, data, columns, emptyMessage }) {
  const [expandedRow, setExpandedRow] = useState(null)

  if (!data || data.length === 0) {
    return (
      <div className="data-table-container fade-in">
        {title && <h3 className="table-title">{title}</h3>}
        <div className="table-empty">
          <p>{emptyMessage || 'No se encontraron hallazgos'}</p>
        </div>
      </div>
    )
  }

  const cols = columns || Object.keys(data[0]).map(key => ({
    key,
    label: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
  }))

  const toggleRow = (index) => {
    setExpandedRow(expandedRow === index ? null : index)
  }

  // Se añade el parámetro 'row' para poder leer toda la fila
  const renderCellValue = (value, key, row) => {
    // 1. Interceptar nuestra columna virtual para recomendaciones SQL
    if (key === 'sql_combined') {
      const sql = row?.sql_recommendation || row?.sql_fix || row?.suggested_action
      if (!sql) return '—'
      return <SqlRecommendation sql={String(sql)} title="SQL" />
    }

    // 2. Por si llega directo como key en columnas extra
    if (key === 'sql_recommendation' || key === 'sql_fix' || key === 'suggested_action') {
      if (!value) return '—'
      return <SqlRecommendation sql={String(value)} title="SQL" />
    }

    if (value === null || value === undefined) return '—'
    if (typeof value === 'boolean') return value ? 'Sí' : 'No'
    if (key === 'severity' || key === 'stats_severity') return <SeverityBadge severity={value} />

    if (typeof value === 'number') {
      if (key.includes('pct') || key.includes('percent') || key.includes('ratio')) {
        return `${value.toFixed(2)}%`
      }
      if (key.includes('size') && !key.includes('pretty')) {
        return value.toLocaleString()
      }
      if (key.includes('time') || key.includes('ms')) {
        return `${value.toFixed(2)} ms`
      }
      return value.toLocaleString()
    }

    return String(value)
  }

  const hiddenInExtra = new Set([
    'sql_recommendation',
    'sql_fix',
    'sql_remediation',
    'suggested_action',
    'recommendation',
    'remediation_steps',
  ])
  const allKeys = data.length > 0 ? Object.keys(data[0]) : []
  const displayedKeys = cols.map(c => c.key)
  const extraKeys = allKeys.filter(k => !displayedKeys.includes(k) && !hiddenInExtra.has(k))

  return (
    <div className="data-table-container fade-in">
      {title && <h3 className="table-title">{title}</h3>}
      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              {cols.map(col => (
                <th key={col.key}
                  style={col.width ? { width: col.width, minWidth: col.width } : {}}
                >
                  {col.label}
                </th>
              ))}
              <th className="th-expand">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => {
              const showRemediation = hasRemediationInfo(row)
              const isExpandable = showRemediation || extraKeys.length > 0
              return (
              <React.Fragment key={i}>
                <tr onClick={() => isExpandable && toggleRow(i)} className={isExpandable ? 'expandable' : ''}>
                  {cols.map(col => (
                    <td 
                      key={col.key}
                      style={col.width ? { width: col.width, minWidth: col.width } : {}}
                      className={col.key === 'query' || col.key === 'query_sample' || col.key === 'sql_fix' || col.key === 'sql_combined' ? 'mono' : ''}
                    >
                      {renderCellValue(row[col.key], col.key, row)}
                    </td>
                  ))}
                  <td className="td-expand">
                    {isExpandable && (
                      <button
                        type="button"
                        className="row-guide-btn"
                        aria-expanded={expandedRow === i}
                        onClick={(e) => {
                          e.stopPropagation()
                          toggleRow(i)
                        }}
                      >
                        {showRemediation ? '¿Qué hacer?' : 'Detalle'}{' '}
                        <span className={`expand-icon ${expandedRow === i ? 'expand-icon--open' : ''}`}>▸</span>
                      </button>
                    )}
                  </td>
                </tr>
                {expandedRow === i && isExpandable && (
                  <tr className="detail-row">
                    <td colSpan={cols.length + 1}>
                      {showRemediation && (
                        <div className="detail-remediation-wrap">
                          <RemediationPanel finding={row} defaultOpen showHeaderSummary />
                        </div>
                      )}
                      {extraKeys.length > 0 && (
                        <div className="detail-content">
                          {extraKeys.map(k => (
                            <div key={k} className="detail-item">
                              <span className="detail-label">{k.replace(/_/g, ' ')}</span>
                              <span className={`detail-value ${k.includes('sql') || k.includes('query') ? 'mono' : ''}`}>
                                {renderCellValue(row[k], k, row)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="table-footer">
        <span className="result-count">{data.length} resultado{data.length !== 1 ? 's' : ''}</span>
      </div>
    </div>
  )
}
