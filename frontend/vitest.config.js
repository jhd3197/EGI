import { defineConfig } from 'vitest/config'

export default defineConfig({
  // Use the automatic JSX runtime so component tests can render .jsx files
  // without each module importing React (the app relies on Vite's react plugin
  // for this at build/dev time; tests need the same transform).
  esbuild: { jsx: 'automatic' },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests/**/*.test.js'],
  },
})
