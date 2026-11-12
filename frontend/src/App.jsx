/*
Este documento, así como todos los documentos bajo la carpeta de components, 
pages y api, fueron hechos con ayuda de Inteligencia Artificial.
*/
import { useState, useEffect, useCallback } from 'react'
import { Navigate, Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import AnalysisTabs from './components/AnalysisTabs'
import NewAnalysisModal from './components/NewAnalysisModal'
import ChangePasswordModal from './components/ChangePasswordModal'
import ProtectedRoute from './components/ProtectedRoute'
import AuthLandingPage from './pages/AuthLandingPage'
import Overview from './pages/Overview'
import HistoryPage from './pages/HistoryPage'
import BloatPage from './pages/BloatPage'
import ConfigPage from './pages/ConfigPage'
import HealthPage from './pages/HealthPage'
import IndexesPage from './pages/IndexesPage'
import QueriesPage from './pages/QueriesPage'
import {
  fullScan,
  getCurrentUser,
  logoutUser,
  setUnauthorizedHandler,
} from './api/pgguardian'
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
  const [user, setUser] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [authCheckError, setAuthCheckError] = useState(null)
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const [tabs, setTabs] = useState(() => [createLocalTab()])
  const [activeTabId, setActiveTabId] = useState(LOCAL_TAB_ID)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [isNewAnalysisOpen, setIsNewAnalysisOpen] = useState(false)
  const [isChangePwdOpen, setIsChangePwdOpen] = useState(false)
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0)

  const activeTab = tabs.find((t) => t.id === activeTabId) || tabs[0]

  const resetSessionState = useCallback(() => {
    setUser(null)
    setTabs([createLocalTab()])
    setActiveTabId(LOCAL_TAB_ID)
    setIsNewAnalysisOpen(false)
    setIsChangePwdOpen(false)
  }, [])

  // Registrar callback global ante respuestas 401 de la API
  useEffect(() => {
    setUnauthorizedHandler(() => {
      resetSessionState()
      navigate('/', { replace: true })
    })
    return () => setUnauthorizedHandler(null)
  }, [navigate, resetSessionState])

  // Verificar cookie de sesión activa al cargar la aplicación
  useEffect(() => {
    let cancelled = false
    getCurrentUser()
      .then((currentUser) => {
        if (!cancelled) {
          setUser(currentUser)
          setAuthCheckError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setUser(null)
          setAuthCheckError(err.message)
        }
      })
      .finally(() => {
        if (!cancelled) setAuthChecked(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

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

  // Escaneo inicial de TiendaDB (Local) únicamente cuando existe sesión autenticada
  useEffect(() => {
    if (!user) return
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
  }, [user, updateLocalTab])

  // Auto-refresh solo cuando hay sesión activa
  useEffect(() => {
    if (!user || !autoRefresh) return
    const interval = setInterval(() => runScan({ silent: true }), POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [user, autoRefresh, runScan])

  const handleAuthenticated = useCallback((authenticatedUser) => {
    setAuthCheckError(null)
    setAuthChecked(true)
    setUser(authenticatedUser)
    setTabs([createLocalTab()])
    setActiveTabId(LOCAL_TAB_ID)
    navigate('/dashboard', { replace: true })
  }, [navigate])

  const handleLogout = useCallback(async () => {
    setIsLoggingOut(true)
    try {
      await logoutUser()
    } catch {
      // Limpiar estado cliente aunque la sesión ya hubiera expirado
    } finally {
      setIsLoggingOut(false)
      resetSessionState()
      navigate('/', { replace: true })
    }
  }, [navigate, resetSessionState])

  const handleSelectTab = useCallback((tabId) => {
    setActiveTabId(tabId)
    if (location.pathname === '/history') {
      navigate('/dashboard')
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

  const localTab = tabs.find((t) => t.id === LOCAL_TAB_ID)
  const localLoading = Boolean(localTab?.isLoading)

  const renderPublicRoute = (initialTab) => {
    if (!authChecked) {
      return (
        <div className="auth-checking-screen" role="status" aria-live="polite">
          <span className="spinner" aria-hidden="true"></span>
          <span>Verificando sesión…</span>
        </div>
      )
    }
    if (user) {
      return <Navigate to="/dashboard" replace />
    }
    return (
      <AuthLandingPage
        initialTab={initialTab}
        initialError={authCheckError}
        onAuthenticated={handleAuthenticated}
      />
    )
  }

  return (
    <Routes>
      <Route path="/" element={renderPublicRoute('login')} />
      <Route path="/register" element={renderPublicRoute('register')} />
      <Route
        path="/*"
        element={
          <ProtectedRoute user={user} authChecked={authChecked}>
            <div className="app-layout">
              <Sidebar
                scanData={activeTab?.scanData}
                currentUser={user}
                onOpenChangePassword={() => setIsChangePwdOpen(true)}
                onLogout={handleLogout}
                isLoggingOut={isLoggingOut}
              />

              <main className="main-content">
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
                      <span className="toggle-label">Actualización automática (30 s)</span>
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

                <div className="page-wrapper">
                  <Routes>
                    <Route
                      path="dashboard"
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
                      path="history"
                      element={
                        <HistoryPage
                          currentUser={user}
                          refreshKey={historyRefreshKey}
                          onOpenTab={openSandboxTab}
                          onDeleted={closeTab}
                        />
                      }
                    />
                    <Route path="bloat" element={<BloatPage scanData={activeTab?.scanData} isLoading={Boolean(activeTab?.isLoading)} />} />
                    <Route path="config" element={<ConfigPage scanData={activeTab?.scanData} isLoading={Boolean(activeTab?.isLoading)} />} />
                    <Route path="health" element={<HealthPage scanData={activeTab?.scanData} isLoading={Boolean(activeTab?.isLoading)} />} />
                    <Route path="indexes" element={<IndexesPage scanData={activeTab?.scanData} isLoading={Boolean(activeTab?.isLoading)} />} />
                    <Route path="queries" element={<QueriesPage scanData={activeTab?.scanData} isLoading={Boolean(activeTab?.isLoading)} />} />
                    <Route path="*" element={<Navigate to="/dashboard" replace />} />
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
                    navigate('/dashboard')
                  }}
                />
              )}

              {isChangePwdOpen && (
                <ChangePasswordModal onClose={() => setIsChangePwdOpen(false)} />
              )}
            </div>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}
