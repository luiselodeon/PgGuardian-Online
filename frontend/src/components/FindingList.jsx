import SeverityBadge from './SeverityBadge'
import RemediationPanel from './RemediationPanel'
import './FindingList.css'

export default function FindingList({ data, emptyMessage }) {
  if (!data || data.length === 0) {
    return <p className="finding-empty">{emptyMessage || 'Sin hallazgos detectados'}</p>
  }

  return (
    <div className="finding-list">
      {data.map((item, i) => (
        <div key={i} className="finding-card">
          <div className="finding-card-header">
            <div className="finding-card-title-group">
              <span className="finding-card-title">
                {item.title || item.finding_id || 'Hallazgo'}
              </span>
              {item.category && (
                <span className="finding-card-category">{item.category}</span>
              )}
            </div>
            {item.severity && <SeverityBadge severity={item.severity} />}
          </div>

          {(item.evidence || item.description) && (
            <p className="finding-card-evidence">
              <span className="rec-evidence-icon">◈</span>{' '}
              {item.evidence || item.description}
            </p>
          )}

          {(item.query_sample || item.query) && (
            <div className="finding-card-query mono">
              <strong>Query:</strong>
              <br />
              {item.query_sample || item.query}
            </div>
          )}

          <RemediationPanel finding={item} defaultOpen={false} />
        </div>
      ))}
    </div>
  )
}

