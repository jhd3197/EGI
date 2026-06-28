// Offline road-routing Web Worker (plan-21, Phase 2). Runs A* off the main
// thread so a large pack never janks the UI. It is a thin shell around the pure
// core in src/lib/routeGraph.js (shared with the vitest unit test), invoked as a
// module worker: new Worker(new URL('./routeWorker.js', import.meta.url), { type: 'module' }).
//
// Message in:  { graph, from: {lat,lon}, to: {lat,lon} }
// Message out: { ok:true, polyline:[[lat,lon],...], meters, nodes }
//          or  { ok:false, reason }
import { aStar } from '../lib/routeGraph.js'

self.onmessage = (e) => {
  const { graph, from, to } = e.data || {}
  try {
    const result = aStar(graph, from, to)
    self.postMessage(result)
  } catch (err) {
    self.postMessage({ ok: false, reason: 'worker_error: ' + (err && err.message) })
  }
}
