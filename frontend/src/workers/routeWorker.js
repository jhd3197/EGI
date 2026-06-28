// Offline road-routing Web Worker (plan-21, Phase 2). Runs A* off the main
// thread so a large pack never janks the UI. It is a thin shell around the pure
// core in src/lib/routeGraph.js (shared with the vitest unit test), invoked as a
// module worker: new Worker(new URL('./routeWorker.js', import.meta.url), { type: 'module' }).
//
// Message in:  { graph, from: {lat,lon}, to: {lat,lon}, hazards?: [...] }
// Message out: { ok:true, polyline:[[lat,lon],...], meters, nodes }
//          or  { ok:false, reason }
//
// When `hazards` is supplied (plan-21, Phase 4) we build a blockedEdge predicate
// from the pure hazard helpers and hand it to A* so the route avoids active
// hazard zones. The helpers are dependency-free, so they import cleanly here.
import { aStar } from '../lib/routeGraph.js'
import { makeBlockedEdge } from '../lib/hazards.js'

self.onmessage = (e) => {
  const { graph, from, to, hazards } = e.data || {}
  try {
    const result = aStar(graph, from, to, { blockedEdge: makeBlockedEdge(hazards) })
    self.postMessage(result)
  } catch (err) {
    self.postMessage({ ok: false, reason: 'worker_error: ' + (err && err.message) })
  }
}
