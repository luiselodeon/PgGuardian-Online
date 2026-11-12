import DataTable from '../components/DataTable'
import './PageCommon.css'

function QuerySection({ title, data, columns, emptyMessage }) {
  // Inyectamos la columna dinámicamente para que el SQL quede en la tabla
  const enhancedColumns = [...columns, { key: 'sql_combined', label: 'Recomendación SQL' }]
  return (
    <DataTable
      title={title}
      data={data || []}
      columns={enhancedColumns}
      emptyMessage={emptyMessage}
    />
  )
}

export default function QueriesPage({ scanData, isLoading }) {
  const queries = scanData?.categories?.queries

  if (isLoading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="page-title">Queries Problemáticas</h1>
        </div>
        <div className="skeleton" style={{ height: 200, borderRadius: 14 }}></div>
        <div className="skeleton" style={{ height: 200, borderRadius: 14 }}></div>
      </div>
    )
  }

  const pgStatEnabled = queries?.detectors?.check_pg_stat_statements?.data?.[0]?.pg_stat_statements_enabled || queries?.detectors?.pg_stat_statements?.data?.[0]?.enabled

  const tempSpillsData  = queries?.detectors?.temp_spills?.data || []
  const seqScansData    = queries?.detectors?.seq_scans?.data || []
  const topTimeData     = queries?.detectors?.top_time_queries?.data || []
  const dbTempData      = queries?.detectors?.db_temp_usage?.data || []
  const explainData     = queries?.detectors?.explain_spills?.data || []

  return (
    <div className="page fade-in">
      <div className="page-header">
        <h1 className="page-title">Queries Problemáticas</h1>
        <p className="page-subtitle">Detección de temp spills, seq scans, queries lentas y anti-patrones</p>
      </div>

      <div className={`status-banner ${pgStatEnabled ? 'status-banner--ok' : 'status-banner--warn'}`}>
        <span className="status-banner-icon">{pgStatEnabled ? 'OK' : 'Advertencia'}</span>
        <span>
          pg_stat_statements: <strong>{pgStatEnabled ? 'Habilitado' : 'No habilitado'}</strong>
          {!pgStatEnabled && ' — Algunos detectores no funcionarán sin esta extensión'}
        </span>
      </div>

      <div className="page-content">
        <QuerySection
          title="Temp Spills (Escritura a Disco)"
          data={tempSpillsData}
          columns={[
            { key: 'title', label: 'Hallazgo' },
            { key: 'severity', label: 'Severidad' },
            { key: 'evidence', label: 'Evidencia' },
            { key: 'query_sample', label: 'Query', width: '30%' },
          ]}
          emptyMessage="No se detectaron queries con escritura a disco"
        />

        <QuerySection
          title="Sequential Scans"
          data={seqScansData}
          columns={[
            { key: 'title', label: 'Hallazgo' },
            { key: 'calls', label: 'Ejecuciones' },
            { key: 'evidence', label: 'Evidencia' },
            { key: 'query', label: 'Query', width: '30%' },
          ]}
          emptyMessage="No se detectaron queries con Seq Scan"
        />

        <QuerySection
          title="Queries con Mayor Tiempo Acumulado"
          data={topTimeData}
          columns={[
            { key: 'title', label: 'Hallazgo' },
            { key: 'severity', label: 'Severidad' },
            { key: 'evidence', label: 'Evidencia' },
            { key: 'query_sample', label: 'Query', width: '35%' },
          ]}
          emptyMessage="No se detectaron queries con tiempo acumulado alto"
        />

        <QuerySection
          title="Uso de Archivos Temporales en BD"
          data={dbTempData}
          columns={[
            { key: 'title', label: 'Hallazgo' },
            { key: 'severity', label: 'Severidad' },
            { key: 'evidence', label: 'Evidencia', width: '50%' },
          ]}
          emptyMessage="No se detectó uso de archivos temporales a nivel base de datos"
        />

        <QuerySection
          title="Spills Detectados por EXPLAIN"
          data={explainData}
          columns={[
            { key: 'title', label: 'Hallazgo' },
            { key: 'severity', label: 'Severidad' },
            { key: 'evidence', label: 'Evidencia' },
            { key: 'query_sample', label: 'Query', width: '30%' },
          ]}
          emptyMessage="No se detectaron spills en los planes de ejecución"
        />
      </div>
    </div>
  )
}
