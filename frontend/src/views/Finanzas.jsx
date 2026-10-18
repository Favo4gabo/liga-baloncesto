import { useCallback, useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { apiFetch } from '../services/api.js'
import { useAuth } from '../context/AuthContext.jsx'

const todayMonth = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}` }
const todayDate = () => new Date().toISOString().slice(0, 10)
const format = (value, currency = 'USD') => value == null ? '—' : Number(value).toLocaleString('es-VE', { style: 'currency', currency, minimumFractionDigits: 2, maximumFractionDigits: 2 })
const PALETTE = ['#3184a4', '#42ad9b', '#dfa84b', '#8470bd']
const CAN_EDIT_ACTUALS = ['super_admin', 'admin', 'accountant']
const CAN_EXPORT = CAN_EDIT_ACTUALS
const CATEGORIES = [
  ['transporte_externo', 'Transporte externo'],
  ['transporte_interno', 'Transporte interno'],
  ['hospedaje', 'Hospedaje'],
  ['viaticos', 'Viáticos'],
]
const CATEGORY_LABELS = Object.fromEntries([...CATEGORIES, ['gastos_extra', 'Gastos extra aprobados']])

const emptyExpense = (assignmentId) => ({
  asignacion_id: assignmentId,
  categoria: 'transporte_externo',
  fecha_gasto: todayDate(),
  monto: '',
  moneda: 'USD',
  descripcion: '',
  referencia_documento: '',
})

export default function Finanzas() {
  const { user } = useAuth()
  const [mes, setMes] = useState(todayMonth)
  const [monedaGrafico, setMonedaGrafico] = useState('USD')
  const [agrupar, setAgrupar] = useState('arbitro')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [rateDate, setRateDate] = useState(todayDate)
  const [rateValue, setRateValue] = useState('')
  const [expandedAssignment, setExpandedAssignment] = useState(null)
  const [expenseForm, setExpenseForm] = useState(null)
  const [savingExpense, setSavingExpense] = useState(false)
  const canDownload = CAN_EXPORT.includes(user.rol)
  const canEditActuals = CAN_EDIT_ACTUALS.includes(user.rol)
  const canManageRate = ['super_admin', 'admin'].includes(user.rol)

  const load = useCallback(async (period = mes, firstLoad = false) => {
    if (firstLoad) setLoading(true)
    setError('')
    try {
      const response = await apiFetch(`/finanzas/resumen?mes=${encodeURIComponent(period)}`)
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo consultar el resumen financiero.')
      setData(result)
    } catch (err) { setError(err.message) } finally { if (firstLoad) setLoading(false) }
  }, [mes])

  useEffect(() => { load(mes, true) }, [mes, load])

  const categories = useMemo(() => Object.entries(data?.resumen?.categorias || {}).map(([key, item]) => ({
    key,
    name: item.nombre,
    budget_usd: Number(item.usd || 0),
    actual_usd: Number(item.real_usd || 0),
    budget_ves: Number(item.ves || 0),
    actual_ves: item.real_ves == null ? null : Number(item.real_ves),
  })), [data])
  const totalRealRegistered = Number(data?.resumen?.registros_gasto_real || 0) > 0
  const pieDataKey = totalRealRegistered ? `actual_${monedaGrafico.toLowerCase()}` : `budget_${monedaGrafico.toLowerCase()}`
  const actualCurrencyMissing = categories.some((category) => category[`actual_${monedaGrafico.toLowerCase()}`] == null)

  async function refreshBcv() {
    setSyncing(true); setError(''); setMessage('')
    try {
      const response = await apiFetch('/finanzas/tasas-bcv/sincronizar', { method: 'POST', body: JSON.stringify({}) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo consultar la tasa BCV.')
      setMessage(`Tasa del ${result.fecha} actualizada: 1 USD = ${Number(result.ves_por_usd).toLocaleString('es-VE')} VES.`)
      await load(mes)
    } catch (err) { setError(err.message) } finally { setSyncing(false) }
  }

  async function saveHistoricalRate(event) {
    event.preventDefault(); setError(''); setMessage('')
    try {
      const response = await apiFetch('/finanzas/tasas', { method: 'POST', body: JSON.stringify({ fecha: rateDate, ves_por_usd: Number(rateValue) }) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo guardar la tasa.')
      setMessage(`Tasa BCV guardada para ${result.fecha}: ${Number(result.ves_por_usd).toLocaleString('es-VE')} VES/USD.`)
      setRateValue('')
      await load(mes)
    } catch (err) { setError(err.message) }
  }

  async function download(formatType) {
    setError('')
    try {
      const params = new URLSearchParams({ agrupar })
      if (agrupar === 'temporada') params.set('temporada', mes.slice(0, 4))
      else params.set('mes', mes)
      const response = await apiFetch(`/finanzas/exportar.${formatType}?${params}`)
      if (!response.ok) {
        const result = await response.json()
        throw new Error(result.error || 'No se pudo generar el informe.')
      }
      const blob = await response.blob()
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `informe_financiero_arbiliga.${formatType}`
      link.click()
      URL.revokeObjectURL(link.href)
    } catch (err) { setError(err.message) }
  }

  async function saveActualExpense(event) {
    event.preventDefault()
    if (!expenseForm) return
    setSavingExpense(true); setError(''); setMessage('')
    try {
      const response = await apiFetch('/finanzas/gastos-reales', { method: 'POST', body: JSON.stringify(expenseForm) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo registrar el gasto real.')
      setExpenseForm(null)
      setMessage(`Gasto real registrado: ${format(result.monto_usd, 'USD')} de presupuesto ejecutado.`)
      await load(mes)
    } catch (err) { setError(err.message) } finally { setSavingExpense(false) }
  }

  async function voidExpense(gasto) {
    const motivo = window.prompt('Motivo para anular este gasto (mínimo 5 caracteres):')
    if (!motivo) return
    setError(''); setMessage('')
    try {
      const response = await apiFetch(`/finanzas/gastos-reales/${gasto.id}/anular`, { method: 'POST', body: JSON.stringify({ motivo }) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo anular el gasto.')
      setMessage('Gasto anulado; se conserva en el historial de auditoría.')
      await load(mes)
    } catch (err) { setError(err.message) }
  }

  const resumen = data?.resumen
  const items = data?.items || []

  return <>
    <div className="page-heading finance-heading"><div><h2>Finanzas e informes</h2><p>Compara el presupuesto logístico con gastos reales, por mes del partido. Tarifas presupuestadas en USD.</p></div><label className="month-filter">Mes de los partidos<input type="month" value={mes} onChange={(event) => setMes(event.target.value)} /></label></div>
    {error && <div className="error-notice" role="alert">{error}</div>}
    {message && <div className="success-notice" role="status">{message}</div>}
    {loading && !data ? <div className="loading">Cargando resumen financiero…</div> : <>
      <section className="finance-metrics">
        <article className="finance-metric-card"><span>Presupuesto del mes</span><strong>{format(resumen?.usd, 'USD')}</strong><small>{resumen?.asignaciones || 0} asignaciones · mes del partido</small></article>
        <article className="finance-metric-card"><span>Gasto real registrado</span><strong>{format(resumen?.real_usd, 'USD')}</strong><small>{resumen?.registros_gasto_real || 0} comprobantes/partidas</small></article>
        <article className="finance-metric-card"><span>Variación real − presupuesto</span><strong>{resumen?.variacion_usd == null ? 'Sin datos reales' : format(resumen.variacion_usd, 'USD')}</strong><small>Positivo = sobrepresupuesto; negativo = bajo presupuesto</small></article>
        <article className="finance-metric-card"><span>Presupuesto equivalente en VES</span><strong>{format(resumen?.ves, 'VES')}</strong><small>{resumen?.sin_tasa ? `${resumen.sin_tasa} asignaciones sin tasa BCV` : 'Tasa efectiva guardada por fecha'}</small></article>
      </section>

      {data?.advertencia_tasas && <div className="rate-warning">{data.advertencia_tasas} Registra la tasa BCV efectiva para completar las conversiones.</div>}

      <section className="finance-charts-grid">
        <article className="panel finance-chart-panel"><header className="panel-header"><div><h3>{totalRealRegistered ? 'Distribución del gasto real' : 'Distribución del presupuesto'}</h3><small>Por categoría logística · elige moneda</small></div><select className="finance-currency-select" value={monedaGrafico} onChange={(event) => setMonedaGrafico(event.target.value)}><option value="USD">USD</option><option value="VES">VES</option></select></header>
          <div className="chart-canvas">{categories.length && categories.some((item) => Number(item[pieDataKey] || 0) > 0) ? <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={categories} dataKey={pieDataKey} nameKey="name" innerRadius="54%" outerRadius="78%" paddingAngle={3}>{categories.map((entry, index) => <Cell key={entry.key} fill={PALETTE[index % PALETTE.length]} />)}</Pie><Tooltip formatter={(value) => format(value, monedaGrafico)} /></PieChart></ResponsiveContainer> : <p className="empty-cell">No hay importes disponibles para esta gráfica.</p>}</div>
          <div className="chart-legend">{categories.map((item, index) => <span key={item.key}><i style={{ background: PALETTE[index % PALETTE.length] }} />{item.name} · {format(item[pieDataKey], monedaGrafico)}</span>)}</div>
        </article>
        <article className="panel finance-chart-panel"><header className="panel-header"><div><h3>Presupuesto frente a gasto real</h3><small>Comparación por rubro · {monedaGrafico}</small></div></header>
          <div className="chart-canvas"><ResponsiveContainer width="100%" height="100%"><BarChart data={categories} margin={{ top: 12, right: 14, left: 4, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} /><YAxis tick={{ fontSize: 10 }} /><Tooltip formatter={(value) => format(value, monedaGrafico)} /><Legend /><Bar dataKey={`budget_${monedaGrafico.toLowerCase()}`} name="Presupuesto" fill="#3184a4" radius={[5, 5, 0, 0]} /><Bar dataKey={`actual_${monedaGrafico.toLowerCase()}`} name="Gasto real" fill="#dfa84b" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div>
          {monedaGrafico === 'VES' && actualCurrencyMissing && <small className="chart-footnote">Faltan tasas BCV para convertir algunos gastos reales.</small>}
        </article>
      </section>

      <section className="panel finance-pending-panel"><header className="panel-header"><div><h3>Presupuesto y gastos reales por asignación</h3><small>El presupuesto se calcula al asignar; contabilidad registra los importes realmente incurridos.</small></div><span className="badge-soft">{items.length} asignaciones</span></header>
        <div className="table-responsive"><table className="table data-table"><thead><tr><th>Partido / fecha</th><th>Árbitro</th><th>Sede</th><th>Presupuesto USD</th><th>Real USD</th><th>Variación USD</th><th>Gastos reales</th></tr></thead><tbody>
          {items.map((item) => <>
            <tr key={`movement-${item.asignacion_id}`}><td>{new Intl.DateTimeFormat('es-VE', { dateStyle: 'medium' }).format(new Date(item.fecha_partido))}<small className="table-subline">{item.estadio}</small></td><td>{item.arbitro}</td><td>{item.ciudad}, {item.estado}</td><td>{format(item.total_usd, 'USD')}</td><td>{format(item.total_real_usd, 'USD')}</td><td>{item.variacion_usd == null ? '—' : format(item.variacion_usd, 'USD')}</td><td><button type="button" className="admin-action-button" onClick={() => setExpandedAssignment(expandedAssignment === item.asignacion_id ? null : item.asignacion_id)}>{item.cantidad_gastos_reales} detalle(s)</button>{canEditActuals && <button type="button" className="admin-action-button" onClick={() => { setExpenseForm(emptyExpense(item.asignacion_id)); setExpandedAssignment(item.asignacion_id) }}>＋ Registrar real</button>}</td></tr>
            {expandedAssignment === item.asignacion_id && <tr key={`details-${item.asignacion_id}`}><td colSpan="7"><div className="actual-detail-list">
                  {item.gastos_reales.map((gasto) => <div className={`actual-expense-item ${gasto.anulado ? 'voided' : ''}`} key={`${gasto.tipo}-${gasto.id}`}><div><strong>{CATEGORY_LABELS[gasto.categoria] || gasto.categoria}</strong><small>{gasto.fecha_gasto} · {format(gasto.monto_original, gasto.moneda)} · equivalente {format(gasto.monto_usd, 'USD')}{gasto.moneda === 'VES' && gasto.tasa_bcv ? ` · BCV ${Number(gasto.tasa_bcv).toLocaleString('es-VE')}` : ''}</small>{gasto.descripcion && <small>{gasto.descripcion}</small>}{gasto.referencia_documento && <small>Referencia: {gasto.referencia_documento}</small>}{gasto.anulado && <small>Anulado: {gasto.motivo_anulacion}</small>}</div>{canEditActuals && gasto.tipo === 'gasto_real' && !gasto.anulado && <button className="admin-action-button danger" type="button" onClick={() => voidExpense(gasto)}>Anular</button>}</div>)}
                  {(item.gastos_extra_pendientes || []).map((gasto) => <div className="actual-expense-item awaiting-review" key={`extra-${gasto.id}`}><div><strong>Gasto extra pendiente de revisión · {gasto.concepto}</strong><small>{gasto.reportado_en?.slice(0, 10)} · {format(gasto.monto, gasto.moneda)}</small>{gasto.descripcion && <small>{gasto.descripcion}</small>}</div><span className="badge-soft">Pendiente Telegram</span></div>)}
              {!item.gastos_reales.length && <p className="empty-cell">No hay gastos reales registrados para esta asignación.</p>}
              {expenseForm?.asignacion_id === item.asignacion_id && <form className="finance-rate-form actual-expense-form" onSubmit={saveActualExpense}>
                <label>Categoría<select value={expenseForm.categoria} onChange={(event) => setExpenseForm({ ...expenseForm, categoria: event.target.value })}>{CATEGORIES.map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
                <label>Fecha del gasto<input type="date" max={todayDate()} required value={expenseForm.fecha_gasto} onChange={(event) => setExpenseForm({ ...expenseForm, fecha_gasto: event.target.value })} /></label>
                <label>Importe<input type="number" min="0.01" step="0.01" required value={expenseForm.monto} onChange={(event) => setExpenseForm({ ...expenseForm, monto: event.target.value })} /></label>
                <label>Moneda<select value={expenseForm.moneda} onChange={(event) => setExpenseForm({ ...expenseForm, moneda: event.target.value })}><option value="USD">USD</option><option value="VES">VES</option></select></label>
                <label>Descripción<input maxLength="300" value={expenseForm.descripcion} onChange={(event) => setExpenseForm({ ...expenseForm, descripcion: event.target.value })} placeholder="Taxi, boleto, hotel…" /></label>
                <label>Referencia<input maxLength="120" value={expenseForm.referencia_documento} onChange={(event) => setExpenseForm({ ...expenseForm, referencia_documento: event.target.value })} placeholder="Factura o comprobante" /></label>
                <button className="btn-primary-custom" disabled={savingExpense}>{savingExpense ? 'Guardando…' : 'Guardar gasto real'}</button>
                <button type="button" className="admin-secondary-button" onClick={() => setExpenseForm(null)}>Cancelar</button>
              </form>}
            </div></td></tr>}
          </>)}
          {!items.length && <tr><td colSpan="7" className="empty-cell">No hay asignaciones para este mes.</td></tr>}
        </tbody></table></div>
      </section>

      {canDownload && <section className="panel finance-export-panel"><header className="panel-header"><div><h3>Exportar informe</h3><small>Presupuesto y gastos reales agrupados por árbitro, partido, ciudad o temporada.</small></div></header><div className="finance-export-controls"><label>Agrupar por<select value={agrupar} onChange={(event) => setAgrupar(event.target.value)}><option value="arbitro">Árbitro</option><option value="partido">Partido</option><option value="ciudad">Ciudad</option><option value="temporada">Temporada</option></select></label><button className="admin-secondary-button" onClick={() => download('xlsx')}>Descargar Excel</button><button className="btn-primary-custom" onClick={() => download('pdf')}>Descargar PDF</button></div></section>}

      {canManageRate && <details className="panel finance-rate-settings"><summary>Administrar tasas BCV · {data?.tasa_hoy ? `${format(data.tasa_hoy.ves_por_usd, 'VES')} por USD (${data.tasa_hoy.fecha})` : 'tasa de hoy no registrada'}</summary><div className="finance-rate-content"><p>Se consulta el portal público del BCV. Para fechas históricas sin tasa guardada, registra la cotización oficial verificada. No se usa una tasa estimada.</p><button type="button" className="admin-secondary-button" disabled={syncing} onClick={refreshBcv}>{syncing ? 'Consultando BCV…' : 'Consultar tasa oficial de hoy'}</button><form className="finance-rate-form" onSubmit={saveHistoricalRate}><label>Fecha de tasa<input type="date" max={todayDate()} value={rateDate} onChange={(event) => setRateDate(event.target.value)} /></label><label>VES por USD<input type="number" min="0.000001" step="0.000001" required value={rateValue} onChange={(event) => setRateValue(event.target.value)} /></label><button className="admin-secondary-button">Guardar tasa verificada</button></form></div></details>}
    </>}
  </>
}
