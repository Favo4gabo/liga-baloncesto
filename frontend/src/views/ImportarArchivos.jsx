import { useRef, useState } from 'react'
import CargaExcel from './CargaExcel.jsx'
import EscanearHorario from './EscanearHorario.jsx'

const acceptedFiles = '.xlsx,.csv,.png,.jpg,.jpeg'

export default function ImportarArchivos() {
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [mode, setMode] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [message, setMessage] = useState('')
  const [requestId, setRequestId] = useState(0)

  function selectFile(selected) {
    setFile(selected || null)
    setMode('')
    setAnalyzing(false)
    setMessage('')
  }

  function analyze(event) {
    event.preventDefault()
    if (!file) { setMessage('Selecciona un archivo Excel, CSV, PNG o JPG.'); return }
    setMessage('')
    setAnalyzing(true)
    setRequestId((current) => current + 1)
    // Los libros .xlsx primero se validan como libro maestro sin guardar.
    // Si no tienen las hojas oficiales, se envían al lector IA de horarios.
    setMode(file.name.toLowerCase().endsWith('.xlsx') ? 'master' : 'schedule')
  }

  function fallbackToSchedule(reason) {
    setMessage(`No se reconoció el libro maestro. ${reason} Se analizará como un horario individual; este modo no crea árbitros ni tarifas. Registra árbitros y canchas en Administración y carga primero el libro maestro con sus tarifas si aún no existen.`)
    setMode('schedule')
  }

  function drop(event) {
    event.preventDefault()
    selectFile(event.dataTransfer.files?.[0])
  }

  return <>
    <div className="page-heading">
      <div><h2>Importar archivo</h2><p>El libro maestro carga catálogos, árbitros y tarifas; un archivo de horario individual propone partidos y asignaciones para revisar.</p></div>
    </div>

    {message && <div className="schedule-warning" role="status">{message}</div>}

    <section className="panel schedule-upload-panel unified-import-panel">
      <form onSubmit={analyze}>
        <div className="schedule-dropzone" role="button" tabIndex="0"
          onClick={() => inputRef.current?.click()}
          onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click() }}
          onDragOver={(event) => event.preventDefault()} onDrop={drop}>
          <span className="schedule-upload-icon" aria-hidden="true">↥</span>
          <strong>{file ? file.name : 'Arrastra aquí el archivo o selecciona uno'}</strong>
          <small>Excel (.xlsx), CSV, PNG o JPG · el análisis no guarda cambios</small>
        </div>
        <input ref={inputRef} className="schedule-file-input" type="file" accept={acceptedFiles} onChange={(event) => { selectFile(event.target.files?.[0]); event.currentTarget.value = '' }} />
        <div className="schedule-upload-actions">
          {file && <button type="button" className="admin-secondary-button" onClick={() => selectFile(null)}>Quitar archivo</button>}
          <button type="submit" className="btn-primary-custom" disabled={!file || analyzing}>{analyzing ? 'Analizando archivo…' : 'Analizar archivo'}</button>
        </div>
      </form>
    </section>

    {analyzing && <p className="schedule-muted import-analysis-status">Analizando el archivo. Esto puede tardar unos segundos…</p>}

    {mode === 'master' && <section className="import-analysis-result" key={`master-${requestId}`}>
      <CargaExcel embedded initialFile={file} hideUploader autoAnalyze
        onValidationComplete={() => setAnalyzing(false)}
        onValidationError={fallbackToSchedule} />
    </section>}
    {mode === 'schedule' && <section className="import-analysis-result" key={`schedule-${requestId}`}>
      <EscanearHorario embedded initialFile={file} hideUploader autoAnalyze
        onAnalysisComplete={() => setAnalyzing(false)}
        onAnalysisError={() => setAnalyzing(false)} />
    </section>}
  </>
}
