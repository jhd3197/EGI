// Tiny helper to turn a CSS declaration string into a React style object.
// Lets us keep the original prototype's inline styles verbatim instead of
// hand-translating hundreds of declarations to camelCase objects.
//
//   <div style={css('padding:16px;background:#fff;')} />
//
// Merge dynamic values with object spread:
//   <div style={{ ...css('padding:16px;'), background: conn.bg }} />
const cache = new Map()

export function css(str) {
  if (!str) return {}
  if (cache.has(str)) return cache.get(str)
  const out = {}
  for (const decl of str.split(';')) {
    const i = decl.indexOf(':')
    if (i < 0) continue
    const rawKey = decl.slice(0, i).trim()
    const value = decl.slice(i + 1).trim()
    if (!rawKey) continue
    // custom properties (--foo) stay as-is; otherwise kebab -> camelCase
    const key = rawKey.startsWith('--')
      ? rawKey
      : rawKey.replace(/-([a-z])/g, (_, c) => c.toUpperCase())
    out[key] = value
  }
  cache.set(str, out)
  return out
}
