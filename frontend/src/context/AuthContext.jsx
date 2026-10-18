import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { apiFetch, setCsrfToken } from '../services/api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    apiFetch('/auth/me')
      .then(async (response) => {
        const data = await response.json()
        if (!response.ok) throw new Error(data.error || 'Sesión no disponible.')
        if (!cancelled) { setCsrfToken(data.csrf_token); setUser(data.usuario) }
      })
      .catch(() => { if (!cancelled) { setCsrfToken(null); setUser(null) } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  async function login(email, password) {
    const response = await apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || 'No se pudo iniciar sesión.')
    setCsrfToken(data.csrf_token)
    setUser(data.usuario)
    return data.usuario
  }

  async function logout() {
    try { await apiFetch('/auth/logout', { method: 'POST' }) } finally {
      setCsrfToken(null)
      setUser(null)
    }
  }

  async function changePassword(currentPassword, newPassword) {
    const response = await apiFetch('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || 'No se pudo cambiar la contraseña.')
    setUser(data.usuario)
    return data
  }

  const value = useMemo(() => ({ user, loading, login, logout, changePassword }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth debe usarse dentro de AuthProvider.')
  return value
}
