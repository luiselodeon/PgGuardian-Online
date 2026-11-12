/*
Cliente API centralizado para PgGuardian.
Usa cookies HttpOnly de sesión (credentials: 'include') para todas las rutas protegidas.
*/

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

function extractApiError(data, status, fallbackPrefix) {
  const detail = data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item) => (item?.msg || '').replace(/^Value error,\s*/i, '').trim())
      .filter(Boolean);
    if (messages.length > 0) return messages.join(' ');
  }
  if (detail && typeof detail === 'object') {
    const location = detail.filename && detail.line
      ? ` (${detail.filename}, línea ${detail.line})`
      : '';
    return `${detail.message || `${fallbackPrefix} (${status})`}${location}`;
  }
  return `${fallbackPrefix} (${status})`;
}

async function requestJSON(endpoint, options = {}, { fallbackPrefix = 'Error en la petición', notifyUnauthorized = true } = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${endpoint}`, {
      credentials: 'include',
      ...options,
    });
  } catch {
    throw new Error('No se pudo conectar con el servidor de PgGuardian. Verifica que el backend esté en ejecución.');
  }

  const data = await res.json().catch(() => null);
  if (res.status === 401 && notifyUnauthorized && unauthorizedHandler) {
    unauthorizedHandler();
  }
  if (!res.ok) {
    throw new Error(extractApiError(data, res.status, fallbackPrefix));
  }
  return data;
}

// Health Check (público)
export const healthCheck = () =>
  requestJSON('/health-check', {}, { fallbackPrefix: 'Error al verificar conectividad', notifyUnauthorized: false });

// Autenticación y sesiones (RF-02.1 a RF-02.6)
export async function getCurrentUser() {
  let res;
  try {
    res = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' });
  } catch {
    throw new Error('No se pudo conectar con el servidor de PgGuardian.');
  }
  if (res.status === 401) {
    return null;
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(extractApiError(data, res.status, 'Error al verificar la sesión'));
  }
  return data;
}

export const registerUser = (payload) =>
  requestJSON(
    '/auth/register',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    { fallbackPrefix: 'No se pudo completar el registro', notifyUnauthorized: false },
  );

export const loginUser = (payload) =>
  requestJSON(
    '/auth/login',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    { fallbackPrefix: 'No se pudo iniciar sesión', notifyUnauthorized: false },
  );

export const logoutUser = () =>
  requestJSON(
    '/auth/logout',
    { method: 'POST' },
    { fallbackPrefix: 'No se pudo cerrar la sesión', notifyUnauthorized: false },
  );

export const changePassword = (payload) =>
  requestJSON(
    '/auth/password',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    { fallbackPrefix: 'No se pudo actualizar la contraseña', notifyUnauthorized: false },
  );

// Full Scan (protegido)
export const fullScan = () =>
  requestJSON('/full-scan', {}, { fallbackPrefix: 'Error al ejecutar el escaneo' });

// Análisis de scripts SQL (RF-01.1 a RF-01.8, protegidos)
export async function createAnalysis(files, order, name) {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  if (order) {
    formData.append('order', JSON.stringify(order));
  }
  if (name && name.trim()) {
    formData.append('name', name.trim());
  }

  return requestJSON(
    '/analyses',
    { method: 'POST', body: formData },
    { fallbackPrefix: 'Error al validar el análisis' },
  );
}

export const listAnalyses = () =>
  requestJSON('/analyses', {}, { fallbackPrefix: 'No se pudo cargar el historial' });

export const getAnalysisDetail = (analysisId) =>
  requestJSON(`/analyses/${encodeURIComponent(analysisId)}`, {}, { fallbackPrefix: 'No se pudo cargar el análisis' });

export const deleteAnalysis = (analysisId) =>
  requestJSON(
    `/analyses/${encodeURIComponent(analysisId)}`,
    { method: 'DELETE' },
    { fallbackPrefix: 'No se pudo eliminar el análisis' },
  );

// Detectores individuales (protegidos)
export const getTableBloat = () => requestJSON('/bloat/table-bloat');
export const getDisabledAutovacuum = () => requestJSON('/bloat/disabled-autovacuum');
export const getDeadTuples = () => requestJSON('/bloat/dead-tuples');

export const getWorkMem = () => requestJSON('/config/work-mem');
export const evaluateWorkMem = () => requestJSON('/config/evaluate-work-mem');
export const getSharedBuffers = () => requestJSON('/config/shared-buffers');
export const evaluateSharedBuffers = () => requestJSON('/config/evaluate-shared-buffers');
export const evaluatePgStatMax = () => requestJSON('/config/evaluate-pg-stat-max');
export const getPgStatLimit = () => requestJSON('/config/pg-stat-limit');
export const getSlowQueryLogging = () => requestJSON('/config/slow-query-logging');

export const getPartitioningCandidates = () => requestJSON('/health/partitioning-candidates');
export const getIdleInTransaction = () => requestJSON('/health/idle-in-transaction');

export const getMissingPartialIndexes = () => requestJSON('/indexes/missing-partial');
export const getMissingIndexes = () => requestJSON('/indexes/missing');
export const getDuplicateIndexes = () => requestJSON('/indexes/duplicate');
export const getUnusedIndexes = () => requestJSON('/indexes/unused');
export const getCoveringCandidates = () => requestJSON('/indexes/covering-candidates');
export const getObsoleteStats = () => requestJSON('/indexes/obsolete-stats');
export const getLeadingWildcards = () => requestJSON('/indexes/leading-wildcards');

export const getPgStatStatus = () => requestJSON('/queries/pg-stat-status');
export const getTempSpills = () => requestJSON('/queries/temp-spills');
export const getSeqScans = () => requestJSON('/queries/seq-scans');
export const getTopTimeQueries = () => requestJSON('/queries/top-time');
export const getDatabaseTempUsage = () => requestJSON('/queries/db-temp-usage');
export const getExplainSpills = () => requestJSON('/queries/explain-spills');
