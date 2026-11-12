import './AnalysisTabs.css'

export default function AnalysisTabs({ tabs, activeTabId, onSelectTab, onCloseTab }) {
  return (
    <div className="analysis-tabs-bar" role="tablist" aria-label="Bases de datos analizadas">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTabId
        const score = tab.scanData?.health_score
        const isSandbox = tab.kind === 'sandbox'
        const isDestroyed = tab.meta?.sandbox_status === 'destroyed'

        return (
          <div
            key={tab.id}
            role="tab"
            tabIndex={0}
            aria-selected={isActive}
            className={`analysis-tab ${isActive ? 'analysis-tab--active' : ''}`}
            onClick={() => onSelectTab(tab.id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onSelectTab(tab.id)
              }
            }}
          >
            <span className={`tab-origin-badge ${isSandbox ? 'tab-origin--sandbox' : 'tab-origin--local'}`}>
              {isSandbox ? (isDestroyed ? 'Historial' : 'Sandbox') : 'Local'}
            </span>
            <span className="analysis-tab-label" title={tab.label}>
              {tab.label}
            </span>
            {typeof score === 'number' && (
              <span className="analysis-tab-score">{score}/100</span>
            )}
            {tab.closable && (
              <button
                type="button"
                className="analysis-tab-close"
                aria-label={`Cerrar pestaña ${tab.label}`}
                title="Cerrar pestaña"
                onClick={(e) => {
                  e.stopPropagation()
                  onCloseTab(tab.id)
                }}
              >
                ×
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}

