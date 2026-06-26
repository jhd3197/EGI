// Pure, reusable helpers for the localStorage-backed offline queue.
// Mirrors the `egi.pendingRecords` contract used by useEgi in src/store.js
// (queueRecord / syncNow). Kept side-effect-free so it can be unit-tested and
// reused without pulling in the React hook.

// Read a JSON array from localStorage[key]; returns [] when missing/corrupt.
export function readPending(key) {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (e) {
    return []
  }
}

// Push a record onto the queue at `key`, persist it, and return the new length.
export function queuePending(key, record) {
  const pending = readPending(key)
  pending.push(record)
  localStorage.setItem(key, JSON.stringify(pending))
  return pending.length
}

// Drop the queue entirely (used after a successful flush to the server).
export function clearPending(key) {
  localStorage.removeItem(key)
}
