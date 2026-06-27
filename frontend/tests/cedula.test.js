// Tests for normalizeCedula — the soft-match helper used by the dedicated
// cédula search (must mirror the server's normalization).
import { describe, expect, it } from 'vitest'
import { normalizeCedula } from '../src/lib/person.js'

describe('normalizeCedula', () => {
  it('strips dots, spaces and the V/E prefix to a bare number', () => {
    // TEST DATA — NOT REAL
    expect(normalizeCedula('V-26.345.789')).toBe('26345789')
    expect(normalizeCedula('26345789')).toBe('26345789')
    expect(normalizeCedula('v26345789')).toBe('26345789')
    expect(normalizeCedula('E-12.345.678')).toBe('12345678')
    expect(normalizeCedula('  26 345 789 ')).toBe('26345789')
  })

  it('matches differently-formatted inputs to the same normalized value', () => {
    expect(normalizeCedula('V-26.345.789')).toBe(normalizeCedula('26345789'))
  })

  it('handles empty / nullish input safely', () => {
    expect(normalizeCedula('')).toBe('')
    expect(normalizeCedula(null)).toBe('')
    expect(normalizeCedula(undefined)).toBe('')
  })

  it('only strips a single leading nationality letter', () => {
    // A leading V is dropped; digits after stay intact.
    expect(normalizeCedula('V12345')).toBe('12345')
  })
})
