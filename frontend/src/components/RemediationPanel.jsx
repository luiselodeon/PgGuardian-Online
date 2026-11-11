import { useState } from 'react'
import SeverityBadge from './SeverityBadge'
import SqlRecommendation from './SqlRecommendation'
import './RemediationPanel.css'

export default function RemediationPanel({ finding, defaultOpen = false, showHeaderSummary = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  if (!finding) return null

  const sql =
    finding.sql_remediation ||
    finding.sql_recommendation ||
    finding.sql_fix ||
    finding.suggested_action
  const steps = Array.isArray(finding.remediation_steps) ? finding.remediation_steps : []
  const summary = finding.evidence || finding.description

  return (
    <div className="remediation-panel">
      {!defaultOpen && (
        <button
          type="button"
          className="remediation-toggle"
          onClick={() => setIsOpen((prev) => !prev)}
          aria-expanded={isOpen}
        >
          <span>¿Qué hacer? — Acciones sugeridas</span>
          <span className={`remediation-arrow ${isOpen ? 'remediation-arrow--open' : ''}`}>▸</span>
        </button>
      )}

      {isOpen && (
        <div className="remediation-body">
          {showHeaderSummary && (
            <div className="remediation-summary-header">
              <div className="remediation-summary-tags">
                {finding.title && <strong className="remediation-title">{finding.title}</strong>}
                {finding.category && <span className="remediation-category-tag">{finding.category}</span>}
              </div>
              {finding.severity && <SeverityBadge severity={finding.severity} />}
            </div>
          )}

          {showHeaderSummary && summary && (
            <p className="remediation-diagnosis">
              <strong>Diagnóstico:</strong> {summary}
            </p>
          )}

          {finding.recommendation && (
            <div className="remediation-advice">
              <span className="remediation-label">¿Qué hacer?</span>
              <p>{finding.recommendation}</p>
            </div>
          )}

          {steps.length > 0 && (
            <div className="remediation-steps-wrap">
              <span className="remediation-label">Acciones sugeridas</span>
              <ol className="remediation-steps">
                {steps.map((step, idx) => (
                  <li key={idx}>{step}</li>
                ))}
              </ol>
            </div>
          )}

          {sql && <SqlRecommendation sql={String(sql)} title="SQL sugerido de remediación" />}
        </div>
      )}
    </div>
  )
}
