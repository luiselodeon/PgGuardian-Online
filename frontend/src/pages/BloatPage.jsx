import DataTable from '../components/DataTable'
import './PageCommon.css'

export default function BloatPage({ scanData, isLoading }) {
  const bloat = scanData?.categories?.bloat

  if (isLoading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="page-title">Fragmentación y Mantenimiento</h1>
        </div>
        <div className="skeleton" style={{ height: 200, borderRadius: 14 }}></div>
        <div className="skeleton" style={{ height: 200, borderRadius: 14 }}></div>
      </div>
    )
  }

  const tableBloatData = bloat?.detectors?.table_bloat?.data || []
  const autovacuumData = bloat?.detectors?.disabled_autovacuum?.data || []
  const deadTuplesData = bloat?.detectors?.dead_tuples?.data || []

  return (
    <div className="page fade-in">
      <div className="page-header">
        <h1 className="page-title">Fragmentación y Mantenimiento</h1>
        <p className="page-subtitle">Fragmentación (bloat) en tablas, autovacuum desactivado y tuplas muertas</p>
      </div>

      <div className="page-content">
        <DataTable
          title="Fragmentación en Tablas"
          data={tableBloatData}
          columns={[
            { key: 'tblname', label: 'Tabla' },
            { key: 'schemaname', label: 'Esquema' },
            { key: 'real_size', label: 'Tamaño Real' },
            { key: 'bloat_size', label: 'Tamaño Desperdiciado' },
            { key: 'bloat_pct', label: 'Fragmentación %' },
            { key: 'extra_pct', label: 'Extra %' },
            { key: 'evidence', label: 'Evidencia' },
            { key: 'sql_combined', label: 'Recomendación SQL' },
          ]}
          emptyMessage="No se detectó fragmentación significativa en las tablas"
        />

        <DataTable
          title="Autovacuum Desactivado"
          data={autovacuumData}
          columns={[
            { key: 'relname', label: 'Tabla' },
            { key: 'reloptions', label: 'Opciones' },
            { key: 'evidence', label: 'Evidencia' },
            { key: 'sql_combined', label: 'Recomendación SQL' },
          ]}
          emptyMessage="Todas las tablas tienen autovacuum habilitado"
        />

        <DataTable
          title="Tuplas Muertas"
          data={deadTuplesData}
          columns={[
            { key: 'table_name', label: 'Tabla' },
            { key: 'schemaname', label: 'Esquema' },
            { key: 'n_live_tup', label: 'Filas Vivas' },
            { key: 'n_dead_tup', label: 'Filas Muertas' },
            { key: 'dead_tuple_pct', label: 'Muertas %' },
            { key: 'evidence', label: 'Evidencia' },
            { key: 'sql_combined', label: 'Recomendación SQL' },
          ]}
          emptyMessage="No se encontraron tablas con tuplas muertas"
        />
      </div>
    </div>
  )
}
