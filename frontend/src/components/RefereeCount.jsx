import { useState } from 'react'
import { createPortal } from 'react-dom'

export default function RefereeCount({ assignments = [], required = 2, label = '' }) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState(null)
  const assigned = assignments.length
  const names = assignments.map((item) => `${item.arbitro?.nombre || ''} ${item.arbitro?.apellido || ''}`.trim()).filter(Boolean)
  const tooltip = names.length ? names.join(', ') : 'Todavía no hay árbitros asignados.'

  function show(event) {
    const rect = event.currentTarget.getBoundingClientRect()
    const height = Math.min(200, 50 + names.length * 20)
    const top = Math.min(rect.bottom + 7, window.innerHeight - height - 12)
    const left = Math.max(12, Math.min(rect.left, window.innerWidth - 250))
    setPosition({ top: Math.max(12, top), left })
    setOpen(true)
  }

  return <span className="assigned-referees-tooltip" onMouseLeave={() => setOpen(false)}>
    {label && <span className="assigned-referees-label">{label}</span>}
    <button
      className="calendar-referee-count"
      type="button"
      aria-label={`${assigned} de ${required} árbitros asignados. ${tooltip}`}
      aria-expanded={open}
      title={tooltip}
      onClick={(event) => { event.preventDefault(); event.stopPropagation(); show(event) }}
      onMouseEnter={show}
      onFocus={show}
      onBlur={() => setOpen(false)}
      onKeyDown={(event) => event.stopPropagation()}
    >♙ {assigned}/{required} árbitros</button>
    {open && position && createPortal(<span className="calendar-referee-popover" role="tooltip" style={position}>
      <strong>Árbitros asignados ({assigned}/{required})</strong>
      {names.length ? names.map((name, index) => <span key={`${name}-${index}`}>{name}</span>) : <span>Sin árbitros asignados</span>}
    </span>, document.body)}
  </span>
}
