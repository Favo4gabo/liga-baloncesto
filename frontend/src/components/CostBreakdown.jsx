const amount = (value) => Number(value || 0).toLocaleString('es-VE', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export default function CostBreakdown({ costs, detail, title = 'Desglose de costos', preview = false }) {
  if (!costs) return null

  const medium = detail?.medio_externo || costs.medio_externo
  const nights = detail?.cantidad_noches ?? costs.cantidad_noches
  const days = detail?.cantidad_dias_viaticos ?? costs.cantidad_dias_viaticos
  const lodgingRate = detail?.costo_hospedaje_por_noche ?? costs.costo_hospedaje_por_noche
  const dailyAllowance = detail?.viatico_por_dia ?? costs.viatico_por_dia

  return (
    <section className={`cost-breakdown ${preview ? 'cost-breakdown-preview' : ''}`} aria-label={title}>
      <header className="cost-breakdown-heading">
        <strong>{title}</strong>
        {medium && <span>{medium === 'avion' ? '✈ Avión' : '🚕 Taxi'} externo</span>}
      </header>
      <div className="cost-row">
        <span>Transporte externo <small>ida y vuelta{medium ? ` · ${medium}` : ''}</small></span>
        <strong>{amount(costs.costo_traslado_externo)}</strong>
      </div>
      <div className="cost-row">
        <span>Transporte interno <small>hotel ↔ cancha · ida y vuelta</small></span>
        <strong>{amount(costs.costo_traslado_interno)}</strong>
      </div>
      <div className="cost-row">
        <span>Estadía <small>{nights != null ? `${nights} noche(s) × ${amount(lodgingRate)} por noche` : 'hospedaje'}</small></span>
        <strong>{amount(costs.costo_estadia)}</strong>
      </div>
      <div className="cost-row">
        <span>Viáticos <small>{days != null && dailyAllowance != null ? `${days} día(s) × ${amount(dailyAllowance)} por día` : 'tarifa diaria según configuración'}</small></span>
        <strong>{amount(costs.costo_viaticos)}</strong>
      </div>
      {Number(costs.gastos_extra_aprobados || 0) > 0 && <div className="cost-row">
        <span>Gastos extra aprobados</span>
        <strong>{amount(costs.gastos_extra_aprobados)}</strong>
      </div>}
      {(costs.gastos_extra_pendientes || []).map((expense) => <div className="cost-row" key={expense.id}>
        <span>Gasto pendiente de revisión <small>#{expense.id} · {expense.concepto}</small></span>
        <strong>{amount(expense.monto)} · pendiente</strong>
      </div>)}
      <div className="cost-total"><span>Total logístico</span><strong>{amount(costs.costo_total)}</strong></div>
      <p className="cost-note">Importes calculados con las tarifas configuradas por el administrador; no se aplica conversión de moneda.</p>
    </section>
  )
}
