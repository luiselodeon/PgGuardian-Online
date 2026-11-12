/*
Este documento, así como todos los documentos bajo la carpeta de components, 
pages y api, fueron hechos con ayuda de Inteligencia Artificial.
*/
import { useState, useEffect, useCallback } from 'react'
import { Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import AnalysisTabs from './components/AnalysisTabs'
import NewAnalysisModal from './components/NewAnalysisModal'
import Overview from './pages/Overview'
import HistoryPage from './pages/HistoryPage'
import BloatPage from './pages/BloatPage'
import ConfigPage from './pages/ConfigPage'
import HealthPage from './pages/HealthPage'
import IndexesPage from './pages/IndexesPage'
import QueriesPage from './pages/QueriesPage'
import { fullScan, getCurrentUserId, setCurrentUserId } from './api/pgguardian'
import './App.css'

const POLL_INTERVAL = 30000 // 30 seconds
const LOCAL_TAB_ID = 'tiendadb-local'

function createLocalTab() {
  return {
    id: LOCAL_TAB_ID,
    label: 'TiendaDB (Local)',
    kind: 'local',
    closable: false,
    scanData: null,
    lastScan: null,
    isLoading: true,
    error: null,
  }
}

export default function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const [tabs, setTabs] = useState(() => [createLocalTab()])
  const [activeTabId, setActiveTabId] = useState(LOCAL_TAB_ID)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [isNewAnalysisOpen, setIsNewAnalysisOpen] = useState(false)
  const [currentUser, setCurrentUser] = useState(() => getCurrentUserId())
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0)

  const activeTab = tabs.find((t) => t.id === activeTabId) || tabs[0]

  const updateLocalTab = useCallback((patch) => {
    setTabs((prev) =>
      prev.map((tab) => (tab.id === LOCAL_TAB_ID ? { ...tab, ...patch } : tab)),
    )
  }, [])

  const runScan = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      updateLocalTab({ isLoading: true, error: null })
    }
    try {
      const data = await fullScan()
      updateLocalTab({
        scanData: data,
        lastScan: new Date().toISOString(),
        isLoading: false,
        error: null,
      })
    } catch (err) {
      updateLocalTab({ isLoading: false, error: err.message })
      console.error('Scan failed:', err)
    }
  }, [updateLocalTab])

  // Initial scan for TiendaDB (Local)
  useEffect(() => {
    let cancelled = false
    fullScan()
      .then((data) => {
        if (!cancelled) {
          updateLocalTab({
            scanData: data,
            lastScan: new Date().toISOString(),
            isLoading: false,
            error: null,
          })
        }
      })
      .catch((err) => {
        if (!cancelled) {
          updateLocalTab({ isLoading: false, error: err.message })
          console.error('Scan failed:', err)
        }
      })
    return () => {
      cancelled = true
    }
  }, [updateLocalTab])

  // Auto-refresh polling only updates TiendaDB (Local) silently without replacing UI with skeletons
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(() => runScan({ silent: true }), POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [autoRefresh, runScan])

  const handleSelectTab = useCallback((tabId) => {
    setActiveTabId(tabId)
    if (location.pathname === '/history') {
      navigate('/')
    }
  }, [location.pathname, navigate])

  const openSandboxTab = useCallback((analysis) => {
    if (!analysis?.id || !analysis?.scan) return
    setTabs((prev) => {
      const exists = prev.some((t) => t.id === analysis.id)
      if (exists) {
        return prev.map((t) =>
          t.id === analysis.id
            ? { ...t, label: analysis.name || t.label, scanData: analysis.scan, meta: analysis }
            : t,
        )
      }
      return [
        ...prev,
        {
          id: analysis.id,
          label: analysis.name || 'Análisis Sandbox',
          kind: 'sandbox',
          closable: true,
          scanData: analysis.scan,
          lastScan: analysis.created_at,
          isLoading: false,
          error: null,
          meta: analysis,
        },
      ]
    })
    setActiveTabId(analysis.id)
  }, [])

  const closeTab = useCallback((tabId) => {
    if (tabId === LOCAL_TAB_ID) return
    setTabs((prev) => {
      const idx = prev.findIndex((t) => t.id === tabId)
      const next = prev.filter((t) => t.id !== tabId)
      setActiveTabId((curr) => {
        if (curr !== tabId) return curr
        const fallback = next[Math.max(0, idx - 1)] || next[0]
        return fallback ? fallback.id : LOCAL_TAB_ID
      })
      return next
    })
  }, [])

  const handleUserChange = (nextUser) => {
    const saved = setCurrentUserId(nextUser)
    setCurrentUser(saved)
    // Al cambiar de usuario se cierran pestañas sandbox ajenas de la sesión
    setTabs((prev) => prev.filter((t) => t.id === LOCAL_TAB_ID))
    setActiveTabId(LOCAL_TAB_ID)
  }

  const localTab = tabs.find((t) => t.id === LOCAL_TAB_ID)
  const localLoading = Boolean(localTab?.isLoading)

  return (
    <div className="app-layout">
      <Sidebar scanData={activeTab?.scanData} currentUser={currentUser} onUserChange={handleUserChange} />

      <main className="main-content">
        {/* Top bar */}
        <header className="top-bar">
          <div className="top-bar-left">
            {activeTab?.error && (
              <div className="error-toast">
                <span>{activeTab.error}</span>
                <button
                  onClick={() => updateLocalTab({ error: null })}
                  className="toast-close"
                >
                  ×
                </button>
              </div>
            )}
          </div>
          <div className="top-bar-actions">
            <label className="auto-refresh-toggle">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
              <span className="toggle-label">Auto-refresh (30s)</span>
            </label>
            <button
              type="button"
              className="new-analysis-button"
              onClick={() => setIsNewAnalysisOpen(true)}
            >
              Nuevo análisis
            </button>
            <button
              className={`scan-button ${localLoading ? 'scan-button--loading' : ''}`}
              onClick={() => {
                setActiveTabId(LOCAL_TAB_ID)
                runScan()
              }}
              disabled={localLoading}
            >
              {localLoading ? (
                <>
                  <span className="spinner"></span>
                  Escaneando…
                </>
              ) : (
                <>Ejecutar Escaneo</>
              )}
            </button>
          </div>
        </header>

        <AnalysisTabs
          tabs={tabs}
          activeTabId={activeTabId}
          onSelectTab={handleSelectTab}
          onCloseTab={closeTab}
        />

        {/* Page content */}
        <div className="page-wrapper">
          <Routes>
            <Route
              path="/"
              element={
                <Overview
                  scanData={activeTab?.scanData}
                  isLoading={Boolean(activeTab?.isLoading)}
                  lastScan={activeTab?.lastScan}
                  activeTab={activeTab}
                />
              }
            />
            <Route
              path="/history"
              element={
                <HistoryPage
                  currentUser={currentUser}
                  refreshKey={historyRefreshKey}
                  onOpenTab={openSandboxTab}
                  onDeleted={closeTab}
                />
              }
            />
            <Route path="/bloat" element={<BloatPage scanData={activeTab?.scanData} isLoading={Boolean(activeTab?.isLoading)} />} />
            <Route path="/config" element={<ConfigPage scanData={activeTab?.scanData} isLoading={Boolean(activeTab?.isLoading)} />} />
            <Route path="/health" element={<HealthPage scanData={activeTab?.scanData} isLoading={Boolean(activeTab?.isLoading)} />} />
            <Route path="/indexes" element={<IndexesPage scanData={activeTab?.scanData} isLoading={Boolean(activeTab?.isLoading)} />} />
            <Route path="/queries" element={<QueriesPage scanData={activeTab?.scanData} isLoading={Boolean(activeTab?.isLoading)} />} />
          </Routes>
        </div>
      </main>

      {isNewAnalysisOpen && (
        <NewAnalysisModal
          onClose={() => setIsNewAnalysisOpen(false)}
          onCreated={(analysis) => {
            setHistoryRefreshKey((k) => k + 1)
            openSandboxTab(analysis)
          }}
          onOpenResultTab={(analysis) => {
            openSandboxTab(analysis)
            setIsNewAnalysisOpen(false)
            navigate('/')
          }}
        />
      )}
    </div>
  )
}
