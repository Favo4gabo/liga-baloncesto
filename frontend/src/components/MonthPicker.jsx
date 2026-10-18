import { useEffect, useRef, useState } from 'react'

const monthNames = Array.from({ length: 12 }, (_, index) =>
  new Intl.DateTimeFormat('es-VE', { month: 'long' }).format(new Date(2024, index, 1)),
)

export default function MonthPicker({ value, onChange, label = 'Seleccionar mes', className = '' }) {
  const rootRef = useRef(null)
  const [open, setOpen] = useState(false)
  const [year, setYear] = useState(() => Number(value?.slice(0, 4)) || new Date().getFullYear())
  const selectedMonth = Number(value?.slice(5, 7)) - 1
  const selectedLabel = Number.isInteger(selectedMonth) && selectedMonth >= 0
    ? `${monthNames[selectedMonth]} ${value.slice(0, 4)}`
    : label

  useEffect(() => {
    if (value) setYear(Number(value.slice(0, 4)) || new Date().getFullYear())
  }, [value])

  useEffect(() => {
    if (!open) return undefined
    const closeOutside = (event) => { if (!rootRef.current?.contains(event.target)) setOpen(false) }
    const closeEscape = (event) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', closeEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', closeEscape)
    }
  }, [open])

  function chooseMonth(index) {
    onChange(`${year}-${String(index + 1).padStart(2, '0')}`)
    setOpen(false)
  }

  return <div className={`month-picker ${className}`} ref={rootRef}>
    <span className="month-picker-label">{label}</span>
    <button
      type="button"
      className="month-picker-trigger"
      aria-haspopup="dialog"
      aria-expanded={open}
      onClick={() => { setYear(Number(value?.slice(0, 4)) || new Date().getFullYear()); setOpen((current) => !current) }}
    >
      <span aria-hidden="true">▦</span><strong>{selectedLabel}</strong><span className="month-picker-chevron" aria-hidden="true">⌄</span>
    </button>
    {open && <div className="month-picker-popover" role="dialog" aria-label="Seleccionar mes">
      <header><button type="button" aria-label="Año anterior" onClick={() => setYear((current) => current - 1)}>‹</button><strong>{year}</strong><button type="button" aria-label="Año siguiente" onClick={() => setYear((current) => current + 1)}>›</button></header>
      <div className="month-picker-grid">{monthNames.map((month, index) => <button
        type="button"
        key={month}
        className={year === Number(value?.slice(0, 4)) && index === selectedMonth ? 'selected' : ''}
        onClick={() => chooseMonth(index)}
      >{month}</button>)}</div>
    </div>}
  </div>
}
