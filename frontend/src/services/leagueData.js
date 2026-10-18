import { apiFetch } from './api.js'

let snapshot = null
let inFlight = null

export function getCachedLeagueData() {
  return snapshot
}

export function loadLeagueData({ refresh = false } = {}) {
  if (inFlight) return inFlight
  if (snapshot && !refresh) return Promise.resolve(snapshot)

  inFlight = Promise.all([apiFetch('/arbitros/'), apiFetch('/partidos')])
    .then(async ([refereesResponse, gamesResponse]) => {
      if (!refereesResponse.ok || !gamesResponse.ok) throw new Error('No se pudieron cargar los datos del sistema.')
      const [arbitros, partidos] = await Promise.all([refereesResponse.json(), gamesResponse.json()])
      snapshot = { arbitros, partidos }
      return snapshot
    })
    .finally(() => { inFlight = null })

  return inFlight
}
