/*
Este es el Cliente API para PgGuardian.

Aquí se va a centralizar todas las llamadas al backend de FastAPI.
Se usa un Base URL configurable, manejo de errores y función fullScan 
que ejecuta todos los detectores en una sola petición.

Este documento fue hecho con ayuda de Inteligencia Artificial. 
*/

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const USER_STORAGE_KEY = 'pgguardian_user_id';
const DEFAULT_USER_ID = 'usuario_a';

export function getCurrentUserId() {
  try {
    return localStorage.getItem(USER_STORAGE_KEY) || DEFAULT_USER_ID;
  } catch {
    return DEFAULT_USER_ID;
  }
}

export function setCurrentUserId(userId) {
  const clean = (userId || DEFAULT_USER_ID).trim() || DEFAULT_USER_ID;
  try {
    localStorage.setItem(USER_STORAGE_KEY, clean);
  } catch {
    // Ignorar si localStorage no está disponible
  }
  return clean;
}

function authHeaders() {
  return { 'X-User-Id': getCurrentUserId() };
}

function extractApiError(data, status, fallbackPrefix) {
  const detail = data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') {
    const location = detail.filename && detail.line
      ? ` (${detail.filename}, línea ${detail.line})`
      : '';
    return `${detail.message || `${fallbackPrefix} (${status})`}${location}`;
  }
  return `${fallbackPrefix} (${status})`;
}

async function fetchJSON(endpoint) {
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

async function fetchAnalysesJSON(endpoint, options = {}, fallbackPrefix = 'Error en análisis') {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(extractApiError(data, res.status, fallbackPrefix));
  }
  return data;
}

// En esta parte van a estar todas las funciones que estén en el API del Backend

// Health Check
export const healthCheck = () => fetchJSON('/health-check');

// Full Scan
export const fullScan = () => fetchJSON('/full-scan');

// Análisis de scripts SQL (RF-01.1 a RF-01.8)
export async function createAnalysis(files, order, name) {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  if (order) {
    formData.append('order', JSON.stringify(order));
  }
  if (name && name.trim()) {
    formData.append('name', name.trim());
  }

  return fetchAnalysesJSON(
    '/analyses',
    { method: 'POST', body: formData },
    'Error al validar el análisis',
  );
}

export const listAnalyses = () =>
  fetchAnalysesJSON('/analyses', {}, 'No se pudo cargar el historial');

export const getAnalysisDetail = (analysisId) =>
  fetchAnalysesJSON(`/analyses/${encodeURIComponent(analysisId)}`, {}, 'No se pudo cargar el análisis');

export const deleteAnalysis = (analysisId) =>
  fetchAnalysesJSON(
    `/analyses/${encodeURIComponent(analysisId)}`,
    { method: 'DELETE' },
    'No se pudo eliminar el análisis',
  );

// Bloat
export const getTableBloat = () => fetchJSON('/bloat/table-bloat');
export const getDisabledAutovacuum = () => fetchJSON('/bloat/disabled-autovacuum');
export const getDeadTuples = () => fetchJSON('/bloat/dead-tuples');

// Config
export const getWorkMem = () => fetchJSON('/config/work-mem');
export const evaluateWorkMem = () => fetchJSON('/config/evaluate-work-mem');
export const getSharedBuffers = () => fetchJSON('/config/shared-buffers');
export const evaluateSharedBuffers = () => fetchJSON('/config/evaluate-shared-buffers');
export const evaluatePgStatMax = () => fetchJSON('/config/evaluate-pg-stat-max');
export const getPgStatLimit = () => fetchJSON('/config/pg-stat-limit');
export const getSlowQueryLogging = () => fetchJSON('/config/slow-query-logging');

// Health
export const getPartitioningCandidates = () => fetchJSON('/health/partitioning-candidates');
export const getIdleInTransaction = () => fetchJSON('/health/idle-in-transaction');

// Indexes
export const getMissingPartialIndexes = () => fetchJSON('/indexes/missing-partial');
export const getMissingIndexes = () => fetchJSON('/indexes/missing');
export const getDuplicateIndexes = () => fetchJSON('/indexes/duplicate');
export const getUnusedIndexes = () => fetchJSON('/indexes/unused');
export const getCoveringCandidates = () => fetchJSON('/indexes/covering-candidates');
export const getObsoleteStats = () => fetchJSON('/indexes/obsolete-stats');
export const getLeadingWildcards = () => fetchJSON('/indexes/leading-wildcards');

// Queries
export const getPgStatStatus = () => fetchJSON('/queries/pg-stat-status');
export const getTempSpills = () => fetchJSON('/queries/temp-spills');
export const getSeqScans = () => fetchJSON('/queries/seq-scans');
export const getTopTimeQueries = () => fetchJSON('/queries/top-time');
export const getDatabaseTempUsage = () => fetchJSON('/queries/db-temp-usage');
export const getExplainSpills = () => fetchJSON('/queries/explain-spills');