export default function ProcesandoOverlay({ visible, title, detail }) {
  if (!visible) return null
  return <div className="import-progress-backdrop" role="alertdialog" aria-modal="true" aria-live="polite" aria-label={title}>
    <section className="import-progress-card">
      <span className="import-progress-spinner" aria-hidden="true" />
      <h2>{title}</h2>
      <p>{detail}</p>
      <small>Por favor, no cierres esta ventana.</small>
    </section>
  </div>
}
