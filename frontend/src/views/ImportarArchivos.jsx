import CargaExcel from './CargaExcel.jsx'
import EscanearHorario from './EscanearHorario.jsx'
import { useSearchParams } from 'react-router-dom'

export default function ImportarArchivos() {
  const [params, setParams] = useSearchParams()
  const tipo = params.get('tipo') === 'horario' ? 'horario' : 'libro'

  function seleccionar(valor) { setParams({ tipo: valor }, { replace: true }) }

  return <>
    <div className="page-heading">
      <div>
        <h2>Importar archivos</h2>
        <p>Elige un libro maestro o analiza un calendario para revisar sus filas antes de guardarlas.</p>
      </div>
    </div>
    <div className="importer-mode-tabs" role="tablist" aria-label="Tipo de archivo a importar">
      <button type="button" role="tab" aria-selected={tipo === 'libro'} className={tipo === 'libro' ? 'active' : ''} onClick={() => seleccionar('libro')}>
        <span aria-hidden="true">▦</span><strong>Libro maestro</strong><small>Catálogos, tarifas, árbitros y partidos</small>
      </button>
      <button type="button" role="tab" aria-selected={tipo === 'horario'} className={tipo === 'horario' ? 'active' : ''} onClick={() => seleccionar('horario')}>
        <span aria-hidden="true">◷</span><strong>Leer horario</strong><small>Excel, CSV o imagen con revisión humana</small>
      </button>
    </div>
    <div role="tabpanel" aria-label={tipo === 'libro' ? 'Importar libro maestro' : 'Leer y confirmar horario'}>
      {tipo === 'libro' ? <CargaExcel embedded /> : <EscanearHorario embedded />}
    </div>
  </>
}
