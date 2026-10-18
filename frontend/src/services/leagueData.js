const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

let snapshot = null
let inFlight = null

export function getCachedLeagueData() {
  return snapshot
}

export function loadLeagueData({ refresh = false } = {}) {
  if (inFlight) return inFlight
  if (snapshot && !refresh) return Promise.resolve(snapshot)

  inFlight = Promise.all([fetch(`${API_URL}/arbitros/`), fetch(`${API_URL}/partidos`)])
    .then(async ([refereesResponse, gamesResponse]) => {
      if (!refereesResponse.ok || !gamesResponse.ok) throw new Error('No se pudieron cargar los datos del sistema.')
      const [arbitros, partidos] = await Promise.all([refereesResponse.json(), gamesResponse.json()])
      snapshot = { arbitros, partidos }
      return snapshot
    })
    .finally(() => { inFlight = null })

  return inFlight
}
