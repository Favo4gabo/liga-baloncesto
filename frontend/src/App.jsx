import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Dashboard from './views/Dashboard.jsx'
import Calendario from './views/Calendario.jsx'
import CargaExcel from './views/CargaExcel.jsx'
import Administracion from './views/Administracion.jsx'
import MetricDetail from './views/MetricDetail.jsx'

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
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#101a27' : '#16325c')
    try { window.localStorage.setItem('arbiliga-theme', theme) } catch { /* El tema sigue activo aunque el navegador bloquee storage. */ }
  }, [theme])

  return (
    <div className="app-shell" data-theme={theme}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">AL</span>
          <span>Arbi<span>Liga</span></span>
        </div>
        <p className="sidebar-label">OPERACIÓN</p>
        <nav className="side-nav">
          <NavLink to="/dashboard"><span>▦</span> Resumen</NavLink>
          <NavLink to="/calendario"><span>◫</span> Calendario</NavLink>
           <NavLink to="/carga"><span>↥</span> Importar Excel</NavLink>
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
            <Route path="/carga" element={<CargaExcel />} />
            <Route path="/administracion" element={<Administracion />} />
            <Route path="/arbitros" element={<MetricDetail />} />
            <Route path="/partidos" element={<MetricDetail />} />
            <Route path="/partidos/programados" element={<MetricDetail />} />
            <Route path="/asignaciones" element={<MetricDetail />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
