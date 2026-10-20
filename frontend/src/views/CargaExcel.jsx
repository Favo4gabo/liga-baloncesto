import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '../services/api.js'
import ProcesandoOverlay from '../components/ProcesandoOverlay.jsx'

const fieldLabels = {
  estados: 'Estados', ciudades: 'Ciudades', tarifas_traslado: 'Tarifas de traslado',
  tarifas_hospedaje: 'Tarifas de hospedaje', parametros: 'Parámetros',
  estados_cercanos: 'Estados cercanos', arbitros: 'Árbitros', partidos: 'Partidos',
  distancias_ciudades: 'Distancias entre ciudades', ubicaciones_cancha: 'Sedes', aeropuertos: 'Aeropuertos',
}

export default function CargaExcel({ embedded = false, initialFile = null, hideUploader = false, autoAnalyze = false, onValidationError, onValidationComplete, onImportComplete }) {
  const ref = useRef(null)
  const autoAnalyzed = useRef(false)
  const [file, setFile] = useState(initialFile)
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function analyzeWorkbook() {
    if (!file) return setError('Selecciona un archivo Excel (.xlsx).')
    setLoading(true); setError(''); setResult(null)
    try {
      const body = new FormData()
      body.append('file', file)
      const response = await apiFetch('/upload-excel/analizar', { method: 'POST', body })
      const json = await response.json()
      if (!response.ok) {
        if (response.status === 400 && onValidationError) { onValidationError(json.error || 'El libro no tiene la estructura maestra.'); return }
        throw new Error(json.error || 'No fue posible validar el libro.')
      }
      setPreview(json)
      onValidationComplete?.(json)
    } catch (err) { setError(err.message); onValidationComplete?.(null) } finally { setLoading(false) }
  }

  async function submit(event) {
    event.preventDefault()
    if (!preview) return analyzeWorkbook()
    setLoading(true); setImporting(true); setError('')
    try {
      const body = new FormData()
      body.append('file', file)
      const response = await apiFetch('/upload-excel', { method: 'POST', body })
      const json = await response.json()
      if (!response.ok) throw new Error(json.error || 'No fue posible importar el libro.')
      setResult(json)
      onImportComplete?.(json)
    } catch (err) { setError(err.message) } finally { setLoading(false); setImporting(false) }
  }

  useEffect(() => {
    if (!autoAnalyze || !file || autoAnalyzed.current) return
    autoAnalyzed.current = true
    analyzeWorkbook()
  }, [autoAnalyze, file])

  function updateFile(selected) {
    setFile(selected || null); setPreview(null); setResult(null); setError('')
  }

  return <>
    <ProcesandoOverlay visible={loading} title={importing ? 'Guardando información del archivo…' : 'Analizando el archivo…'} detail={importing ? 'Estamos registrando los catálogos, árbitros, tarifas y partidos en una transacción segura.' : 'Estamos leyendo y validando las tablas. Este paso todavía no guarda cambios.'} />
    {!embedded && <div className="page-heading"><div><h2>Importar archivo</h2><p>Analiza, revisa el resumen y confirma antes de guardar.</p></div></div>}
    {error && <div className="error-notice mt-3" role="alert">{error}</div>}
    {!hideUploader && <div className="upload-layout">
      <section className="panel"><form onSubmit={submit} className="upload-dropzone">
        <div><div className="upload-icon">↥</div><h3>Sube el libro maestro de la liga</h3><p>Primero se valida sin modificar la base de datos. Solo se guarda cuando confirmes.</p>
          <input ref={ref} id="excel" type="file" accept=".xlsx" onChange={(event) => updateFile(event.target.files?.[0])} />
          <button type="button" className="btn-primary-custom" onClick={() => ref.current?.click()}>Seleccionar archivo</button>
          {file && <p className="file-name">✓ {file.name}</p>}
          <div className="mt-3">{!preview && <button type="submit" className="btn-primary-custom" disabled={loading || !file}>{loading ? 'Validando…' : 'Analizar libro'}</button>}</div>
        </div>
      </form></section>
      <Guide />
    </div>}
    {hideUploader && <section className="panel master-preview-actions">
      <header className="panel-header"><div><h3>Libro maestro detectado</h3><small>{file?.name} · valida las hojas requeridas antes de guardar.</small></div></header>
      <div className="master-preview-buttons"><button type="button" className="admin-secondary-button" disabled={loading} onClick={() => { setPreview(null); setResult(null); setError('') }}>Volver a analizar archivo</button><button type="button" className="btn-primary-custom" disabled={loading || !file} onClick={() => submit({ preventDefault() {} })}>{loading ? 'Procesando…' : preview ? 'Confirmar e importar' : 'Validar libro maestro'}</button></div>
    </section>}

    {preview && <section className="panel master-analysis-preview">
      <header className="panel-header"><div><h3>Revisión antes de importar</h3><small>{preview.origen === 'ia_tablas_apiladas' ? `IA de apoyo: ${preview.proveedor || 'proveedor'} · ${preview.modelo || 'modelo'}. ` : preview.origen === 'tablas_apiladas' ? 'Se detectaron automáticamente tablas organizadas por bloques en el libro. ' : 'La validación terminó correctamente. '}Aún no se guardó nada.</small></div><span className="badge-soft">Validado</span></header>
      {preview.advertencias?.map((advertencia, indice) => <div className="schedule-warning" role="status" key={`${indice}-${advertencia}`}>{advertencia}</div>)}
      <div className="master-analysis-grid">{Object.entries(preview.insertados_o_actualizados || {}).map(([key, value]) => <div key={key}><strong>{value}</strong><span>{fieldLabels[key] || key.replaceAll('_', ' ')}</span></div>)}</div>
      <p className="table-footnote">Al confirmar, estas hojas se importarán en una única transacción. Si alguna fila es inválida, no se guardará el lote.</p>
      {!hideUploader && <button type="button" className="btn-primary-custom master-confirm" disabled={loading} onClick={() => submit({ preventDefault() {} })}>{loading ? 'Guardando…' : 'Confirmar e importar'}</button>}
    </section>}
    {result && <section className="panel mt-4"><header className="panel-header"><h3>Importación completada</h3><span className="badge-soft">Éxito</span></header><div className="master-analysis-grid">{Object.entries(result.insertados_o_actualizados || {}).map(([key, value]) => <div key={key}><strong>{value}</strong><span>{fieldLabels[key] || key.replaceAll('_', ' ')}</span></div>)}</div></section>}
  </>

}

function Guide() {
  return <aside className="panel"><header className="panel-header"><h3>Hojas del libro maestro</h3></header><div className="guide-list">{['Estados y Ciudades', 'TarifasTraslado y TarifasHospedaje', 'Parametros (viatico_por_dia)', 'EstadosCercanos', 'Arbitros y Partidos'].map((text, index) => <div className="guide-item" key={text}><span className="guide-number">{index + 1}</span><span>{text}</span></div>)}</div></aside>
}
