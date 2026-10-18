import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../services/api.js'

const ROLE_LABELS = { super_admin: 'Superadmin', admin: 'Administrador', accountant: 'Contable', viewer: 'Consulta' }
const EMPTY = { nombre: '', email: '', rol: 'viewer' }

export default function Usuarios() {
  const [usuarios, setUsuarios] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [temporaryPassword, setTemporaryPassword] = useState('')

  const load = useCallback(async () => {
    const response = await apiFetch('/usuarios')
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || 'No se pudieron cargar las cuentas.')
    setUsuarios(data)
  }, [])

  useEffect(() => { load().catch((err) => setError(err.message)).finally(() => setLoading(false)) }, [load])

  async function createUser(event) {
    event.preventDefault()
    setSaving(true); setError(''); setMessage(''); setTemporaryPassword('')
    try {
      const response = await apiFetch('/usuarios', { method: 'POST', body: JSON.stringify(form) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'No se pudo crear la cuenta.')
      setTemporaryPassword(data.contrasena_temporal)
      setMessage(data.mensaje)
      setForm(EMPTY)
      await load()
    } catch (err) { setError(err.message) } finally { setSaving(false) }
  }

  async function updateUser(user, changes) {
    setError(''); setMessage('')
    try {
      const response = await apiFetch(`/usuarios/${user.id}`, { method: 'PATCH', body: JSON.stringify(changes) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'No se pudo actualizar el perfil.')
      setMessage(`Se actualizó la cuenta de ${data.nombre}.`)
      await load()
    } catch (err) { setError(err.message) }
  }

  async function resetPassword(user) {
    if (!window.confirm(`Crear una contraseña temporal nueva para ${user.nombre}? La contraseña anterior dejará de funcionar.`)) return
    setError(''); setMessage(''); setTemporaryPassword('')
    try {
      const response = await apiFetch(`/usuarios/${user.id}/reset-password`, { method: 'POST', body: JSON.stringify({}) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'No se pudo restablecer la contraseña.')
      setTemporaryPassword(data.contrasena_temporal)
      setMessage(`${data.mensaje} Entrega la clave directamente y pide al usuario cambiarla al ingresar.`)
      await load()
    } catch (err) { setError(err.message) }
  }

  return <>
    <div className="page-heading"><div><h2>Usuarios y permisos</h2><p>Administra las cuentas de la liga. Solo los superadministradores pueden abrir esta sección.</p></div></div>
    <div className="security-note"><strong>Contraseñas protegidas:</strong> el sistema almacena hashes irreversibles. No se puede consultar una contraseña existente; puedes restablecerla y entregar la clave temporal una sola vez.</div>
    {error && <div className="error-notice" role="alert">{error}</div>}
    {message && <div className="success-notice" role="status">{message}</div>}
    {temporaryPassword && <section className="temporary-password-panel"><div><strong>Contraseña temporal (se muestra una sola vez)</strong><code>{temporaryPassword}</code></div><button type="button" className="admin-secondary-button" onClick={() => navigator.clipboard?.writeText(temporaryPassword)}>Copiar</button><button type="button" className="icon-button" onClick={() => setTemporaryPassword('')} aria-label="Ocultar contraseña temporal">×</button></section>}

    <div className="users-layout">
      <section className="panel admin-form-card">
        <header className="panel-header"><h3>Crear usuario de la liga</h3></header>
        <form className="admin-form" onSubmit={createUser}>
          <label>Nombre<input required maxLength="120" value={form.nombre} onChange={(event) => setForm({ ...form, nombre: event.target.value })} /></label>
          <label>Correo electrónico<input required type="email" maxLength="190" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
          <label>Perfil<select value={form.rol} onChange={(event) => setForm({ ...form, rol: event.target.value })}><option value="admin">Administrador</option><option value="accountant">Contable</option><option value="viewer">Consulta (solo lectura)</option></select></label>
          <small>Se generará una clave temporal y se exigirá cambiarla durante el primer ingreso. Los dos perfiles super_admin se crean desde una terminal segura.</small>
          <button className="btn-primary-custom" disabled={saving}>{saving ? 'Creando…' : 'Crear cuenta'}</button>
        </form>
      </section>

      <section className="panel admin-list users-list">
        <header className="panel-header"><h3>Cuentas registradas</h3><span className="badge-soft">{usuarios.length} usuarios</span></header>
        {loading ? <p className="loading">Cargando usuarios…</p> : <div className="table-responsive"><table className="table data-table"><thead><tr><th>Usuario</th><th>Rol</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
          {usuarios.map((user) => <tr key={user.id}>
            <td><strong>{user.nombre}</strong><small className="table-subline">{user.email}</small></td>
            <td>{user.rol === 'super_admin' ? <span className="badge-soft owner-role">Superadmin propietario</span> : <select className="role-select" value={user.rol} onChange={(event) => updateUser(user, { rol: event.target.value })}><option value="admin">Administrador</option><option value="accountant">Contable</option><option value="viewer">Consulta</option></select>}</td>
            <td><span className={`availability-dot ${user.activo ? 'active' : ''}`}>{user.activo ? 'Activo' : 'Bloqueado'}</span></td>
            <td><div className="user-actions"><button type="button" className="admin-action-button" onClick={() => resetPassword(user)}>Restablecer clave</button>{user.rol !== 'super_admin' && <button type="button" className="admin-action-button" onClick={() => updateUser(user, { activo: !user.activo })}>{user.activo ? 'Bloquear' : 'Desbloquear'}</button>}</div></td>
          </tr>)}
          {!usuarios.length && <tr><td className="empty-cell" colSpan="4">Aún no hay cuentas. Crea la primera cuenta administrativa.</td></tr>}
        </tbody></table></div>}
      </section>
    </div>
  </>
}
