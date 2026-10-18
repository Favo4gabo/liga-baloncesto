export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

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
  return fetch(absoluteUrl, { ...options, method, headers, credentials: 'include' })
}
