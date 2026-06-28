#!/usr/bin/env node
// Guard: the built PWA must be fully self-contained so it renders offline inside
// the Android WebView (no network, no EGI server). This fails the build/CI if a
// new external font or CDN dependency sneaks into frontend/dist.
//
// What it checks, over dist/**/*.{html,css,js}:
//   1. No references to known font CDNs (fonts.googleapis.com, fonts.gstatic.com,
//      use.typekit.net, fonts.bunny.net, cdn.jsdelivr.net/.../fonts, …).
//   2. index.html has no <link rel="stylesheet"> pointing at an absolute http(s)
//      URL (an external stylesheet blocks offline first paint).
//   3. No @import url(http…) and no @font-face src pointing at an http(s) URL.
//
// Plain attribution strings in bundled libraries (e.g. "https://reactjs.org")
// are NOT network requests and are ignored — we only flag fetchable asset URLs.

import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs'
import { join, extname } from 'node:path'
import { fileURLToPath } from 'node:url'

const distDir = join(fileURLToPath(new URL('.', import.meta.url)), '..', 'dist')

if (!existsSync(distDir)) {
  console.error('[check-offline-assets] dist/ not found — run `npm run build` first.')
  process.exit(2)
}

const FONT_CDN = /(fonts\.googleapis\.com|fonts\.gstatic\.com|use\.typekit\.net|fonts\.bunny\.net|fontawesome\.com|cdn\.jsdelivr\.net\/[^"')]*fonts?)/i
const EXTERNAL_STYLESHEET = /<link\b[^>]*rel=["']?stylesheet["']?[^>]*href=["']https?:\/\//i
const EXTERNAL_STYLESHEET_HREFFIRST = /<link\b[^>]*href=["']https?:\/\/[^>]*rel=["']?stylesheet["']?/i
const CSS_IMPORT_URL = /@import\s+(url\()?["']?https?:\/\//i
const FONTFACE_SRC_URL = /@font-face[^}]*src\s*:[^}]*url\(\s*["']?https?:\/\//i

const failures = []

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) walk(full)
    else if (['.html', '.css', '.js'].includes(extname(full))) checkFile(full)
  }
}

function checkFile(file) {
  const text = readFileSync(file, 'utf8')
  const rel = file.slice(distDir.length + 1)
  if (FONT_CDN.test(text)) failures.push(`${rel}: references an external font CDN`)
  if (file.endsWith('.html')) {
    if (EXTERNAL_STYLESHEET.test(text) || EXTERNAL_STYLESHEET_HREFFIRST.test(text)) {
      failures.push(`${rel}: external <link rel="stylesheet"> would block offline rendering`)
    }
  }
  if (file.endsWith('.css')) {
    if (CSS_IMPORT_URL.test(text)) failures.push(`${rel}: @import of an http(s) URL`)
    if (FONTFACE_SRC_URL.test(text)) failures.push(`${rel}: @font-face src points at an http(s) URL`)
  }
}

walk(distDir)

if (failures.length) {
  console.error('[check-offline-assets] FAIL — external asset dependencies found in dist/:')
  for (const f of failures) console.error('  - ' + f)
  console.error('\nFonts/CSS must be self-hosted (see frontend/src/main.jsx @fontsource imports).')
  process.exit(1)
}

console.log('[check-offline-assets] OK — dist/ is self-contained (no external fonts/CDN).')
