import { lazy, Suspense, useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Dashboard from './views/Dashboard.jsx'
import Calendario from './views/Calendario.jsx'
import Administracion from './views/Administracion.jsx'
import MetricDetail from './views/MetricDetail.jsx'
import ImportarArchivos from './views/ImportarArchivos.jsx'
import { AuthProvider, useAuth } from './context/AuthContext.jsx'
import { API_URL } from './services/api.js'

export { API_URL }

const Finanzas = lazy(() => import('./views/Finanzas.jsx'))
const Usuarios = lazy(() => import('./views/Usuarios.jsx'))

const ROLE_NAMES = { super_admin: 'Superadministrador', admin: 'Administrador', accountant: 'Contable', viewer: 'Consulta' }
const MANAGEMENT_ROLES = ['super_admin', 'admin']
const FINANCE_ROLES = ['super_admin', 'admin', 'accountant', 'viewer']

function readSavedTheme() {
  try { return window.localStorage.getItem('arbiliga-theme') === 'dark' ? 'dark' : 'light' } catch { return 'light' }
}

function LoginScreen() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setSending(true)
    setError('')
    try { await login(email, password) } catch (err) { setError(err.message) } finally { setSending(false) }
  }

  return <main className="auth-screen">
    <form className="auth-card panel" onSubmit={submit}>
      <div className="auth-brand"><img className="auth-brand-logo" src="/images/logo/logo.png?v=2" alt="" /><strong>Arbi<span>Liga</span></strong></div>
      <h1>Iniciar sesión</h1><p>Ingresa con la cuenta de tu liga.</p>
      {error && <div className="error-notice" role="alert">{error}</div>}
      <label>Correo electrónico<input autoComplete="username" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      <label>Contraseña<input autoComplete="current-password" type="password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      <button className="btn-primary-custom" disabled={sending}>{sending ? 'Validando…' : 'Entrar'}</button>
    </form>
  </main>
}

function ChangePasswordScreen() {
  const { changePassword, logout } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError('')
    if (next !== confirmation) return setError('La confirmación no coincide.')
    setSaving(true)
    try { await changePassword(current, next) } catch (err) { setError(err.message) } finally { setSaving(false) }
  }

  return <main className="auth-screen"><form className="auth-card panel" onSubmit={submit}>
    <div className="eyebrow">SEGURIDAD DE LA CUENTA</div><h1>Actualiza tu contraseña</h1>
    <p>Esta cuenta tiene una contraseña temporal. Cámbiala para continuar.</p>
    {error && <div className="error-notice" role="alert">{error}</div>}
    <label>Contraseña actual (si aplica)<input type="password" autoComplete="current-password" value={current} onChange={(event) => setCurrent(event.target.value)} /></label>
    <label>Nueva contraseña<input type="password" autoComplete="new-password" minLength="6" required value={next} onChange={(event) => setNext(event.target.value)} /></label>
    <small>Usa al menos 6 caracteres. Recomendamos una contraseña más larga para proteger mejor la cuenta.</small>
    <label>Repite la nueva contraseña<input type="password" autoComplete="new-password" required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label>
    <button className="btn-primary-custom" disabled={saving}>{saving ? 'Guardando…' : 'Cambiar contraseña'}</button>
    <button className="auth-logout-link" type="button" onClick={() => logout()}>Cerrar sesión</button>
  </form></main>
}

function RoleGate({ roles, children }) {
  const { user } = useAuth()
  return roles.includes(user.rol) ? children : <section className="panel access-denied"><h2>Acceso no disponible</h2><p>Tu perfil no tiene permiso para esta sección.</p></section>
}

function AppShell({ theme, setTheme, user }) {
  const { logout } = useAuth()
  const links = [
    { to: '/dashboard', icon: '▦', label: 'Resumen', roles: ['super_admin', 'admin', 'accountant', 'viewer'] },
    { to: '/calendario', icon: '◫', label: 'Calendario', roles: ['super_admin', 'admin', 'accountant', 'viewer'] },
    { to: '/finanzas', icon: '$', label: 'Finanzas e informes', roles: FINANCE_ROLES },
    { to: '/importar', icon: '↥', label: 'Importar archivos', roles: MANAGEMENT_ROLES },
    { to: '/administracion', icon: '⚙', label: 'Administración', roles: MANAGEMENT_ROLES },
    { to: '/usuarios', icon: '♙', label: 'Usuarios y permisos', roles: ['super_admin'] },
  ].filter((item) => item.roles.includes(user.rol))

  return <div className="app-shell" data-theme={theme}>
    <aside className="sidebar">
      <div className="brand"><img className="brand-logo" src="/images/logo/logo.png?v=2" alt="" /><span className="brand-copy"><span className="brand-name">Arbi<span>Liga</span></span><small>GESTIÓN ARBITRAL</small></span></div>
      <p className="sidebar-label">OPERACIÓN</p>
      <nav className="side-nav">{links.map((item) => <NavLink key={item.to} to={item.to}><span>{item.icon}</span>{item.label}</NavLink>)}</nav>
      <div className="sidebar-footer"><div className="admin-avatar">{user.nombre?.[0] || 'U'}</div><div><strong>{user.nombre}</strong><small>{ROLE_NAMES[user.rol] || user.rol}</small></div></div>
    </aside>
    <div className="content-area">
      <header className="topbar"><div><span className="eyebrow">PANEL DE CONTROL</span><h1>Gestión arbitral</h1></div>
        <div className="topbar-actions">
          <button className="theme-toggle" type="button" onClick={() => setTheme((current) => current === 'dark' ? 'light' : 'dark')} aria-label={theme === 'dark' ? 'Activar modo claro' : 'Activar modo oscuro'} aria-pressed={theme === 'dark'}><span aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span>{theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}</button>
          <button className="session-user-button" type="button" title={user.email} onClick={logout}>Salir · {user.nombre}</button>
        </div>
      </header>
      <main className="page-content"><Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/calendario" element={<Calendario />} />
        <Route path="/arbitros" element={<MetricDetail />} />
        <Route path="/partidos" element={<MetricDetail />} />
        <Route path="/asignaciones" element={<MetricDetail />} />
        <Route path="/finanzas" element={<RoleGate roles={FINANCE_ROLES}><Suspense fallback={<div className="loading">Cargando finanzas…</div>}><Finanzas /></Suspense></RoleGate>} />
        <Route path="/usuarios" element={<RoleGate roles={['super_admin']}><Suspense fallback={<div className="loading">Cargando usuarios…</div>}><Usuarios /></Suspense></RoleGate>} />
        <Route path="/importar" element={<RoleGate roles={MANAGEMENT_ROLES}><ImportarArchivos /></RoleGate>} />
        <Route path="/carga" element={<Navigate to="/importar?tipo=libro" replace />} />
        <Route path="/horarios" element={<Navigate to="/importar?tipo=horario" replace />} />
        <Route path="/administracion" element={<RoleGate roles={MANAGEMENT_ROLES}><Administracion /></RoleGate>} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes></main>
    </div>
  </div>
}

function AppContent() {
  const { user, loading } = useAuth()
  const [theme, setTheme] = useState(() => {
    try { return window.localStorage.getItem('arbiliga-theme') === 'dark' ? 'dark' : 'light' } catch { return 'light' }
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.dataset.colorScheme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#101a27' : '#16325c')
    try { window.localStorage.setItem('arbiliga-theme', theme) } catch { /* Sigue funcionando en la sesión actual. */ }
  }, [theme])

  if (loading) return <main className="auth-screen"><div className="loading">Verificando sesión…</div></main>
  if (!user) return <LoginScreen />
  if (user.debe_cambiar_password) return <ChangePasswordScreen />
  return <AppShell theme={theme} setTheme={setTheme} user={user} />
}

export default function App() {
  return <AuthProvider><AppContent /></AuthProvider>
}
