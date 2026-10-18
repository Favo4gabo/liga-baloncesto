import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '../services/api.js'

const acceptedFiles = '.xlsx,.csv,.png,.jpg,.jpeg'

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

  function removeRow(index) {
    setFilas((current) => current.filter((_, rowIndex) => rowIndex !== index))
    setResultado(null)
  }

  async function confirmSchedule() {
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
            <td className={low('arbitro') ? 'schedule-low-confidence' : ''}>
              {row.arbitro_texto && <small className="schedule-raw-value">Leído: {row.arbitro_texto}</small>}
              <select aria-label={`Árbitro fila ${index + 1}`} value={row.arbitro_id || ''} onChange={(event) => { const selected = arbitros.find((item) => item.id === Number(event.target.value)); updateRow(index, { arbitro_id: selected?.id || null, arbitro_texto: selected ? `${selected.nombre} ${selected.apellido}` : row.arbitro_texto }) }}>
                <option value="">Seleccionar árbitro</option>{arbitros.map((item) => <option key={item.id} value={item.id}>{item.nombre} {item.apellido}</option>)}
              </select>
            </td>
            <td className={low('cancha') ? 'schedule-low-confidence' : ''}>
              {row.cancha_texto && <small className="schedule-raw-value">Leído: {row.cancha_texto}</small>}
              <select aria-label={`Cancha fila ${index + 1}`} value={row.cancha_id || ''} onChange={(event) => { const selected = canchas.find((item) => item.id === Number(event.target.value)); updateRow(index, { cancha_id: selected?.id || null, cancha_texto: selected?.nombre_cancha || row.cancha_texto, ciudad_id: selected?.ciudad_id || row.ciudad_id }) }}>
                <option value="">Seleccionar cancha</option>{canchas.map((item) => <option key={item.id} value={item.id}>{item.nombre_cancha}</option>)}
              </select>
            </td>
            <td className={low('ciudad') ? 'schedule-low-confidence' : ''}>
              {row.ciudad_texto && <small className="schedule-raw-value">Leído: {row.ciudad_texto}</small>}
             <select aria-label={`Ciudad fila ${index + 1}`} value={row.ciudad_id || ''} onChange={(event) => updateRow(index, { ciudad_id: event.target.value ? Number(event.target.value) : null })}>
                <option value="">Seleccionar ciudad</option>{ciudades.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
              </select>
            </td>
            <td><input aria-label={`Días de viático fila ${index + 1}`} type="number" min="1" step="1" value={row.cantidad_dias ?? 1} onChange={(event) => updateRow(index, { cantidad_dias: event.target.value === '' ? '' : Number(event.target.value) })} /></td>
            <td><input aria-label={`Noches fila ${index + 1}`} type="number" min="0" step="1" value={row.cantidad_noches ?? 1} onChange={(event) => updateRow(index, { cantidad_noches: event.target.value === '' ? '' : Number(event.target.value) })} /></td>
            <td><input aria-label={`Viático por día fila ${index + 1}`} type="number" min="0" step="0.01" placeholder="Usar tarifa" value={row.viatico_por_dia ?? ''} onChange={(event) => updateRow(index, { viatico_por_dia: event.target.value })} /></td>
            <td>{row.presupuesto == null ? '—' : `${row.presupuesto}${row.notas ? ` · ${row.notas}` : ''}`}</td>
            <td><span className={`schedule-confidence ${Number(row.confianza || 0) < 0.62 ? 'low' : ''}`}>{Math.round(Number(row.confianza || 0) * 100)}%</span></td>
            <td><button type="button" className="schedule-remove-row" aria-label={`Quitar fila ${index + 1}`} onClick={() => removeRow(index)}>×</button></td>
          </tr>
        })}</tbody>
      </table></div>
       <footer className="schedule-confirm-footer"><small>Confirma los datos antes de guardar. El viático editado se aplica al cálculo; el presupuesto detectado es solo referencial. Si alguna fila es inválida, el lote completo se cancela.</small><button type="button" className="btn-primary-custom" onClick={confirmSchedule} disabled={saving || filas.length === 0}>{saving ? 'Registrando…' : 'Aprobar y Registrar en Calendario'}</button></footer>
    </section>}
  </>
}
