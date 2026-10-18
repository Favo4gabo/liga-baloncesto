import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Dashboard from './views/Dashboard.jsx'
import Calendario from './views/Calendario.jsx'
import Administracion from './views/Administracion.jsx'
import MetricDetail from './views/MetricDetail.jsx'
import ImportarArchivos from './views/ImportarArchivos.jsx'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

function readSavedTheme() {
  try {
    return window.localStorage.getItem('arbiliga-theme') === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

export default function App() {
  const [theme, setTheme] = useState(readSavedTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.dataset.colorScheme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#101a27' : '#16325c')
    try { window.localStorage.setItem('arbiliga-theme', theme) } catch { /* El tema sigue activo aunque el navegador bloquee storage. */ }
  }, [theme])

  return (
    <div className="app-shell" data-theme={theme}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 36 36" focusable="false">
              <circle cx="18" cy="18" r="11.5" />
              <path d="M6.7 18h22.6M18 6.5v23M9.8 9.8c5.5 4.1 11 12.3 16.4 16.4M26.2 9.8C20.7 13.9 15.2 22.1 9.8 26.2" />
            </svg>
          </span>
          <span className="brand-copy"><span className="brand-name">Arbi<span>Liga</span></span><small>GESTIÓN ARBITRAL</small></span>
        </div>
        <p className="sidebar-label">OPERACIÓN</p>
        <nav className="side-nav">
          <NavLink to="/dashboard"><span>▦</span> Resumen</NavLink>
          <NavLink to="/calendario"><span>◫</span> Calendario</NavLink>
          <NavLink to="/importar"><span>↥</span> Importar archivos</NavLink>
          <NavLink to="/administracion"><span>⚙</span> Administración</NavLink>
        </nav>
        <div className="sidebar-footer">
          <div className="admin-avatar">A</div>
          <div><strong>Administrador</strong><small>Gestión de liga</small></div>
        </div>
      </aside>
      <div className="content-area">
        <header className="topbar">
          <div><span className="eyebrow">PANEL DE CONTROL</span><h1>Gestión arbitral</h1></div>
          <div className="topbar-actions">
            <button className="theme-toggle" type="button" onClick={() => setTheme((current) => current === 'dark' ? 'light' : 'dark')} aria-label={theme === 'dark' ? 'Activar modo claro' : 'Activar modo oscuro'} aria-pressed={theme === 'dark'}>
              <span aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span>{theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
            </button>
            <div className="topbar-status"><span className="status-dot" /> Sistema operativo</div>
          </div>
        </header>
        <main className="page-content">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/calendario" element={<Calendario />} />
            <Route path="/importar" element={<ImportarArchivos />} />
            <Route path="/horarios" element={<Navigate to="/importar?tipo=horario" replace />} />
            <Route path="/administracion" element={<Administracion />} />
            <Route path="/arbitros" element={<MetricDetail />} />
            <Route path="/partidos" element={<MetricDetail />} />
            <Route path="/asignaciones" element={<MetricDetail />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
