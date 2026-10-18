import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Dashboard from './views/Dashboard.jsx'
import Calendario from './views/Calendario.jsx'
import CargaExcel from './views/CargaExcel.jsx'
import Administracion from './views/Administracion.jsx'
import MetricDetail from './views/MetricDetail.jsx'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

export default function App() {
  return (
    <div className="app-shell">
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
          <div className="topbar-status"><span className="status-dot" /> Sistema operativo</div>
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
