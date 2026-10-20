// Por defecto se usa una ruta relativa para que Vite reenvíe /api al backend y
// la cookie de sesión quede en el mismo origen. En producción VITE_API_URL puede
// apuntar a la URL absoluta de la API.
export const API_URL = import.meta.env.VITE_API_URL || '/api'

let csrfToken = null

export function setCsrfToken(value) {
  csrfToken = value || null
}

export function apiFetch(url, options = {}) {
  const absoluteUrl = /^https?:\/\//i.test(url) ? url : `${API_URL}${url.startsWith('/') ? url : `/${url}`}`
  const headers = new Headers(options.headers || {})
  const method = (options.method || 'GET').toUpperCase()
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken) {
    headers.set('X-CSRF-Token', csrfToken)
  }
  return fetch(absoluteUrl, { ...options, method, headers, credentials: 'include' }).catch((error) => {
    // Los errores de red del navegador cambian según motor/idioma ("NetworkError",
    // "Failed to fetch", "Load failed"); no exponerlos directamente en la interfaz.
    if (error instanceof TypeError || /networkerror|failed to fetch|load failed/i.test(error?.message || '')) {
      throw new Error(
        'No se pudo conectar con el servidor. Verifica que el backend esté iniciado y vuelve a intentarlo.'
      )
    }
    throw error
  })
}
