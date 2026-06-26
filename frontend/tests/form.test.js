// Person-record form validation tests for src/lib/validatePerson.js.
import { describe, expect, it } from 'vitest'
import { validatePerson } from '../src/lib/validatePerson.js'

// TEST DATA — NOT REAL
const validRecord = {
  name: 'Juan Pérez de prueba',
  cedula: 'V-00000000',
  status: 'missing',
  age: 34,
}

describe('validatePerson', () => {
  it('accepts a fully valid record', () => {
    const { valid, errors } = validatePerson(validRecord)
    expect(valid).toBe(true)
    expect(errors).toEqual([])
  })

  it('accepts a valid record with empty optional fields', () => {
    // TEST DATA — NOT REAL: only the required fields provided.
    const { valid, errors } = validatePerson({
      name: 'Juan Pérez de prueba',
      status: 'safe',
      age: '',
      cedula: '',
    })
    expect(valid).toBe(true)
    expect(errors).toEqual([])
  })

  it('rejects a missing name', () => {
    const { valid, errors } = validatePerson({ ...validRecord, name: '   ' })
    expect(valid).toBe(false)
    expect(errors).toContain('name is required')
  })

  it('rejects an invalid status', () => {
    const { valid, errors } = validatePerson({ ...validRecord, status: 'lost' })
    expect(valid).toBe(false)
    expect(errors).toContain('status is invalid')
  })

  it('rejects a bad age', () => {
    const { valid, errors } = validatePerson({ ...validRecord, age: 200 })
    expect(valid).toBe(false)
    expect(errors).toContain('age is invalid')
  })

  it('rejects a bad cedula', () => {
    const { valid, errors } = validatePerson({ ...validRecord, cedula: 'ABC123' })
    expect(valid).toBe(false)
    expect(errors).toContain('cedula is invalid')
  })
})
