import DataTable from '../components/DataTable'
import FindingList from '../components/FindingList'
import './PageCommon.css'

export default function ConfigPage({ scanData, isLoading }) {
  const config = scanData?.categories?.config

  if (isLoading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="page-title">Configuración</h1>
        </div>
        <div className="skeleton" style={{ height: 200, borderRadius: 14 }}></div>
        <div className="skeleton" style={{ height: 200, borderRadius: 14 }}></div>
      </div>
    )
  }

  return (
    <div className="page fade-in">
      <div className="page-header">
        <h1 className="page-title">Configuración</h1>
        <p className="page-subtitle">Parámetros críticos del servidor PostgreSQL y sus evaluaciones</p>
      </div>

      <div className="page-content">
        {/* work_mem — valor actual */}
        <DataTable
          title="Valor Actual de work_mem"
          data={config?.detectors?.work_mem?.data || []}
          columns={[
            { key: 'name', label: 'Parámetro' },
            { key: 'setting', label: 'Valor' },
            { key: 'unit', label: 'Unidad' },
          ]}
          emptyMessage="No se pudo obtener el valor de work_mem"
        />

        {/* work_mem — evaluación */}
        <section className="detector-section">
          <h3 className="detector-section-title">Evaluación de work_mem</h3>
          <FindingList
            data={config?.detectors?.work_mem_evaluation?.data}
            emptyMessage="work_mem tiene un valor aceptable"
          />
        </section>

        {/* shared_buffers — valor actual */}
        <DataTable
          title="Valor Actual de shared_buffers"
          data={config?.detectors?.shared_buffers?.data || []}
          columns={[
            { key: 'name', label: 'Parámetro' },
            { key: 'setting', label: 'Valor' },
            { key: 'unit', label: 'Unidad' },
          ]}
          emptyMessage="No se pudo obtener el valor de shared_buffers"
        />

        {/* shared_buffers — evaluación */}
        <section className="detector-section">
          <h3 className="detector-section-title">Evaluación de shared_buffers</h3>
          <FindingList
            data={config?.detectors?.shared_buffers_evaluation?.data}
            emptyMessage="shared_buffers tiene un valor aceptable"
          />
        </section>

        {/* pg_stat_statements.max — evaluación */}
        <section className="detector-section">
          <h3 className="detector-section-title">Evaluación de pg_stat_statements.max</h3>
          <FindingList
            data={config?.detectors?.pg_stat_max_evaluation?.data}
            emptyMessage="pg_stat_statements.max tiene un valor aceptable"
          />
        </section>

        {/* pg_stat_statements límite de tracking */}
        <section className="detector-section">
          <h3 className="detector-section-title">Límite de Rastreo de Consultas</h3>
          <FindingList
            data={config?.detectors?.pg_stat_limit?.data}
            emptyMessage="El rastreo de consultas es suficiente (sin desalojo detectado)"
          />
        </section>

        {/* Logging de consultas lentas */}
        <section className="detector-section">
          <h3 className="detector-section-title">Registro de Consultas Lentas</h3>
          <FindingList
            data={config?.detectors?.slow_query_logging?.data}
            emptyMessage="El registro de consultas lentas está habilitado"
          />
        </section>
      </div>
    </div>
  )
}
