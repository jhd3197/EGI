// Pure validation for a person/report record before it is queued or synced.
// Returns { valid, errors } so callers (and tests) can surface short messages.
// English-default messages; statuses match the project-wide valid set.

export const VALID_STATUSES = ['missing', 'found', 'safe', 'deceased', 'sighted', 'care']

// Loose Venezuelan cédula: optional V/E/J/P/G prefix, optional dash, 6-9 digits.
const CEDULA_RE = /^[VEJPGve]?-?\d{6,9}$/

export function validatePerson(record = {}) {
  const errors = []

  // name: required, non-empty after trim.
  if (!record.name || String(record.name).trim() === '') {
    errors.push('name is required')
  }

  // status: must be one of the six valid statuses.
  if (!VALID_STATUSES.includes(record.status)) {
    errors.push('status is invalid')
  }

  // age: optional. When provided, must be a positive integer below 130.
  if (record.age !== null && record.age !== undefined && record.age !== '') {
    const age = Number(record.age)
    if (!Number.isInteger(age) || age <= 0 || age >= 130) {
      errors.push('age is invalid')
    }
  }

  // cedula: optional. When provided, must match the loose cédula pattern.
  if (record.cedula !== null && record.cedula !== undefined && record.cedula !== '') {
    if (!CEDULA_RE.test(String(record.cedula))) {
      errors.push('cedula is invalid')
    }
  }

  return { valid: errors.length === 0, errors }
}
