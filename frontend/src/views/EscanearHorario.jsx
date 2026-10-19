import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '../services/api.js'

const acceptedFiles = '.xlsx,.csv,.png,.jpg,.jpeg'
const normalizeLabel = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().replace(/\s+/g, ' ').toLocaleLowerCase()

function rowIssue(row, arbitros, canchas, ciudades) {
  if (!row.fecha) return 'falta la fecha.'
  if (!row.hora) return 'falta la hora.'
  if (!Number.isInteger(Number(row.arbitro_id)) || !arbitros.some((item) => item.id === Number(row.arbitro_id))) {
    return arbitros.length ? 'selecciona un árbitro del catálogo.' : 'no hay árbitros; regístralos en Administración.'
  }
  const cancha = canchas.find((item) => item.id === Number(row.cancha_id))
  if (!cancha) return canchas.length ? 'selecciona una cancha del catálogo.' : 'no hay canchas; regístralas en Administración.'
  const ciudad = ciudades.find((item) => item.id === Number(row.ciudad_id))
  if (!ciudad) return ciudades.length ? 'selecciona una ciudad y estado.' : 'no hay ciudades; carga el catálogo geográfico.'
  if (Number(cancha.ciudad_id) !== Number(ciudad.id)) return 'la ciudad debe coincidir con la ciudad de la cancha.'
  const dias = Number(row.cantidad_dias ?? 1)
  const noches = Number(row.cantidad_noches ?? 1)
  if (!Number.isInteger(dias) || dias < 1) return 'los días de viático deben ser al menos 1.'
  if (!Number.isInteger(noches) || noches < 0) return 'las noches deben ser cero o más.'
  return ''
}

export default function EscanearHorario({
  embedded = false,
  initialFile = null,
  hideUploader = false,
  autoAnalyze = false,
  onAnalysisError,
  onAnalysisComplete,
}) {
  const inputRef = useRef(null)
  const autoAnalyzed = useRef(false)
  const [file, setFile] = useState(initialFile)
  const [filas, setFilas] = useState([])
  const [ciudades, setCiudades] = useState([])
  const [arbitros, setArbitros] = useState([])
  const [canchas, setCanchas] = useState([])
  const [advertencias, setAdvertencias] = useState([])
  const [provider, setProvider] = useState('')
  const [resultado, setResultado] = useState(null)
  const [loadingCatalogs, setLoadingCatalogs] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      apiFetch('/catalogos/ciudades'),
      apiFetch('/arbitros/'),
      apiFetch('/catalogos/canchas'),
    ]).then(async ([cityResponse, refereeResponse, venueResponse]) => {
      if (![cityResponse, refereeResponse, venueResponse].every((response) => response.ok)) throw new Error('No se pudieron cargar los catálogos.')
      const [cityList, refereeList, venueList] = await Promise.all([cityResponse.json(), refereeResponse.json(), venueResponse.json()])
      setCiudades(cityList)
      setArbitros(refereeList.filter((item) => item.activo))
      setCanchas(venueList)
    }).catch((err) => setError(err.message)).finally(() => setLoadingCatalogs(false))
  }, [])

  useEffect(() => {
    if (!autoAnalyze || !initialFile || loadingCatalogs || autoAnalyzed.current) return
    autoAnalyzed.current = true
    scan({ preventDefault() {} })
  }, [autoAnalyze, initialFile, loadingCatalogs])

  function selectFile(selected) {
    setFile(selected || null)
    setFilas([])
    setResultado(null)
    setError('')
  }

  async function scan(event) {
    event.preventDefault()
    if (!file) { setError('Selecciona un archivo Excel, CSV o imagen.'); return }
    setScanning(true)
    setError('')
    setResultado(null)
    try {
      const body = new FormData()
      body.append('file', file)
      const response = await apiFetch('/horarios/escanear', { method: 'POST', body })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'No se pudo leer el horario.')
      setFilas(data.filas || [])
      setAdvertencias(data.advertencias || [])
      setProvider(data.modelo ? `${data.origen} · ${data.modelo}` : data.origen || '')
      if (!(data.filas || []).length) throw new Error('El lector no encontró filas. Revisa el archivo e inténtalo de nuevo.')
      onAnalysisComplete?.(data)
    } catch (err) {
      setError(err.message)
      setFilas([])
      onAnalysisError?.(err.message)
    } finally {
      setScanning(false)
    }
  }

  function updateRow(index, changes) {
    setFilas((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, ...changes } : row))
    setResultado(null)
  }

  const primeraFilaIncompleta = filas.findIndex((row) => rowIssue(row, arbitros, canchas, ciudades))
  const mensajeValidacion = primeraFilaIncompleta >= 0
    ? `Fila ${primeraFilaIncompleta + 1}: ${rowIssue(filas[primeraFilaIncompleta], arbitros, canchas, ciudades)} Completa o elige un valor del catálogo antes de aprobar.`
    : ''

  function removeRow(index) {
    setFilas((current) => current.filter((_, rowIndex) => rowIndex !== index))
    setResultado(null)
  }

  async function confirmSchedule() {
    if (mensajeValidacion) { setError(mensajeValidacion); return }
    setSaving(true)
    setError('')
    setResultado(null)
    try {
      const response = await apiFetch('/horarios/confirmar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filas: filas.map((row) => ({
          fecha: row.fecha,
          hora: row.hora,
           arbitro_id: row.arbitro_id,
           cancha_id: row.cancha_id,
           ciudad_id: row.ciudad_id,
           cantidad_noches: Number(row.cantidad_noches ?? 1),
           cantidad_dias: Number(row.cantidad_dias ?? 1),
           viatico_por_dia: row.viatico_por_dia === '' || row.viatico_por_dia == null ? null : Number(row.viatico_por_dia),
        })) }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'No se pudo registrar el horario.')
      setResultado(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  function onDrop(event) {
    event.preventDefault()
    selectFile(event.dataTransfer.files?.[0])
  }

  return <>
    {!embedded && <div className="page-heading"><div><h2>Lector de horarios</h2><p>Extrae las asignaciones y revísalas antes de registrar cualquier dato.</p></div></div>}
    {error && <div className="error-notice" role="alert">{error}</div>}
    {resultado && <div className="success-notice" role="status">✓ {resultado.mensaje} Se crearon {resultado.partidos_nuevos} partidos y {resultado.asignaciones_nuevas} asignaciones.</div>}
    {!loadingCatalogs && (!arbitros.length || !canchas.length || !ciudades.length) && <div className="schedule-warning" role="status">
      Para registrar horarios necesitas ciudades, árbitros y canchas. Las ciudades de referencia se cargan al inicializar la base; crea los árbitros y las sedes desde Administración antes de aprobar el Excel.
    </div>}

    {!hideUploader && <section className="panel schedule-upload-panel">
      <form onSubmit={scan}>
        <div className="schedule-dropzone" role="button" tabIndex="0" onClick={() => inputRef.current?.click()} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click() }} onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
          <span className="schedule-upload-icon" aria-hidden="true">↥</span>
          <strong>{file ? file.name : 'Arrastra aquí tu archivo o selecciona uno'}</strong>
          <small>Excel (.xlsx), CSV, PNG o JPG · revisa y corrige los datos antes de confirmarlos</small>
        </div>
        <input ref={inputRef} className="schedule-file-input" type="file" accept={acceptedFiles} onChange={(event) => selectFile(event.target.files?.[0])} />
        <div className="schedule-upload-actions">
          {file && <button type="button" className="admin-secondary-button" onClick={() => selectFile(null)}>Quitar archivo</button>}
          <button type="submit" className="btn-primary-custom" disabled={!file || scanning || loadingCatalogs}>{scanning ? 'Analizando archivo…' : 'Analizar y previsualizar'}</button>
        </div>
      </form>
      {loadingCatalogs && <p className="schedule-muted">Cargando catálogos…</p>}
    </section>}

    {advertencias.map((warning, index) => <div className="schedule-warning" key={`${warning}-${index}`}>{warning}</div>)}
    {filas.length > 0 && <section className="panel schedule-preview-panel">
       <header className="panel-header"><div><h3>Previsualización editable</h3><small>{filas.length} fila(s) · {provider} · los datos se guardan solo al aprobar</small></div><button className="admin-action-button" type="button" onClick={() => setFilas((current) => [...current, { fecha: '', hora: '', arbitro_texto: '', cancha_texto: '', ciudad_texto: '', arbitro_id: null, cancha_id: null, ciudad_id: null, cantidad_dias: 1, cantidad_noches: 1, confianza: 0, confianza_campos: {} }])}>＋ Añadir fila</button></header>
      <p className="schedule-confidence-hint"><span aria-hidden="true">●</span> Las celdas resaltadas tienen baja confianza o necesitan revisión.</p>
       <div className="table-responsive"><table className="table data-table schedule-table"><thead><tr><th>Fecha</th><th>Hora</th><th>Árbitro</th><th>Cancha</th><th>Ciudad</th><th>Días viático</th><th>Noches</th><th>Viático/día</th><th>Presupuesto leído</th><th>Confianza</th><th aria-label="Acciones" /></tr></thead>
        <tbody>{filas.map((row, index) => {
          const low = (field) => Number(row.confianza_campos?.[field] ?? row.confianza ?? 0) < 0.62
          return <tr key={`${row.fila_origen || 'fila'}-${index}`}>
            <td className={low('fecha') ? 'schedule-low-confidence' : ''}><input aria-label={`Fecha fila ${index + 1}`} type="date" value={row.fecha || ''} onChange={(event) => updateRow(index, { fecha: event.target.value })} /></td>
            <td className={low('hora') ? 'schedule-low-confidence' : ''}><input aria-label={`Hora fila ${index + 1}`} type="time" value={row.hora || ''} onChange={(event) => updateRow(index, { hora: event.target.value })} /></td>
            <td className={low('arbitro') || !row.arbitro_id ? 'schedule-low-confidence' : ''}>
              {row.arbitro_texto && <small className="schedule-raw-value">Leído: {row.arbitro_texto}</small>}
              <input aria-label={`Árbitro fila ${index + 1}`} list={`arbitros-fila-${index}`} placeholder="Escribe o elige árbitro" value={arbitros.find((item) => item.id === Number(row.arbitro_id)) ? `${arbitros.find((item) => item.id === Number(row.arbitro_id)).nombre} ${arbitros.find((item) => item.id === Number(row.arbitro_id)).apellido}` : row.arbitro_texto || ''} onChange={(event) => {
                const value = event.target.value
                const selected = arbitros.find((item) => normalizeLabel(`${item.nombre} ${item.apellido}`) === normalizeLabel(value))
                updateRow(index, { arbitro_texto: value, arbitro_id: selected?.id || null })
              }} />
              <datalist id={`arbitros-fila-${index}`}>{arbitros.map((item) => <option key={item.id} value={`${item.nombre} ${item.apellido}`} />)}</datalist>
            </td>
            <td className={low('cancha') || !row.cancha_id ? 'schedule-low-confidence' : ''}>
              {row.cancha_texto && <small className="schedule-raw-value">Leído: {row.cancha_texto}</small>}
              <input aria-label={`Cancha fila ${index + 1}`} list={`canchas-fila-${index}`} placeholder="Escribe o elige cancha" value={canchas.find((item) => item.id === Number(row.cancha_id))?.nombre_cancha || row.cancha_texto || ''} onChange={(event) => {
                const value = event.target.value
                const selected = canchas.find((item) => normalizeLabel(item.nombre_cancha) === normalizeLabel(value))
                const city = selected && ciudades.find((item) => item.id === Number(selected.ciudad_id))
                updateRow(index, { cancha_texto: value, cancha_id: selected?.id || null, ciudad_id: city?.id || row.ciudad_id, ciudad_texto: city?.nombre || row.ciudad_texto })
              }} />
              <datalist id={`canchas-fila-${index}`}>{canchas.map((item) => <option key={item.id} value={item.nombre_cancha} />)}</datalist>
            </td>
            <td className={low('ciudad') || !row.ciudad_id ? 'schedule-low-confidence' : ''}>
               {row.ciudad_texto && <small className="schedule-raw-value">Leído: {row.ciudad_texto}</small>}
              <input aria-label={`Ciudad fila ${index + 1}`} list={`ciudades-fila-${index}`} placeholder="Escribe o elige ciudad" value={ciudades.find((item) => item.id === Number(row.ciudad_id)) ? `${ciudades.find((item) => item.id === Number(row.ciudad_id)).nombre} · ${ciudades.find((item) => item.id === Number(row.ciudad_id)).estado?.nombre || ''}` : row.ciudad_texto || ''} onChange={(event) => {
                const value = event.target.value
                const selected = ciudades.find((item) => normalizeLabel(`${item.nombre} · ${item.estado?.nombre || ''}`) === normalizeLabel(value) || normalizeLabel(item.nombre) === normalizeLabel(value))
                updateRow(index, { ciudad_texto: value, ciudad_id: selected?.id || null })
              }} />
              <datalist id={`ciudades-fila-${index}`}>{ciudades.map((item) => <option key={item.id} value={`${item.nombre} · ${item.estado?.nombre || 'Sin estado'}`} />)}</datalist>
            </td>
            <td><input aria-label={`Días de viático fila ${index + 1}`} type="number" min="1" step="1" value={row.cantidad_dias ?? 1} onChange={(event) => updateRow(index, { cantidad_dias: event.target.value === '' ? '' : Number(event.target.value) })} /></td>
            <td><input aria-label={`Noches fila ${index + 1}`} type="number" min="0" step="1" value={row.cantidad_noches ?? 1} onChange={(event) => updateRow(index, { cantidad_noches: event.target.value === '' ? '' : Number(event.target.value) })} /></td>
            <td><input aria-label={`Viático por día fila ${index + 1}`} type="number" min="0" step="0.01" placeholder="Usar tarifa" value={row.viatico_por_dia ?? ''} onChange={(event) => updateRow(index, { viatico_por_dia: event.target.value })} /></td>
            <td>{row.presupuesto == null ? '—' : `${row.presupuesto}${row.notas ? ` · ${row.notas}` : ''}`}</td>
            <td><span title={Object.entries(row.confianza_campos || {}).map(([field, score]) => `${field}: ${Math.round(Number(score) * 100)}%`).join(' · ')} className={`schedule-confidence ${Number(row.confianza || 0) < 0.62 ? 'low' : ''}`}>{Math.round(Number(row.confianza || 0) * 100)}%</span></td>
            <td><button type="button" className="schedule-remove-row" aria-label={`Quitar fila ${index + 1}`} onClick={() => removeRow(index)}>×</button></td>
          </tr>
        })}</tbody>
      </table></div>
       <footer className="schedule-confirm-footer"><small>{mensajeValidacion || 'Revisa los datos antes de guardar. El viático editado se aplica al cálculo; el presupuesto detectado es solo referencial.'} La confianza indica coincidencias automáticas; puedes escribir o elegir un valor existente en las celdas amarillas.</small><button type="button" className="btn-primary-custom" onClick={confirmSchedule} disabled={saving || filas.length === 0 || Boolean(mensajeValidacion)}>{saving ? 'Registrando…' : 'Aprobar y Registrar en Calendario'}</button></footer>
    </section>}
  </>
}
