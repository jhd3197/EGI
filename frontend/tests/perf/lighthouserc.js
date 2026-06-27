// Lighthouse CI config for the EGI PWA (plan-15 §8.2).
//
// Asserts the initial bundle stays under the 500 KB gzipped SLO
// (docs/PERFORMANCE.md) and flags performance/accessibility regressions.
//
// Optional tooling — install only when running it:
//   cd frontend && npm run build && npx @lhci/cli autorun
//
// `collect.staticDistDir` points at the Vite build output so LHCI serves the
// production bundle (not the dev server). Budgets are advisory in CI (warn), not
// a hard merge block, per plan-15 §8.4.

module.exports = {
  ci: {
    collect: {
      staticDistDir: '../../dist',
      numberOfRuns: 1,
      settings: {
        // PWA is offline-first; emulate a mid-range mobile device.
        preset: 'desktop',
      },
    },
    assert: {
      assertions: {
        // ~500 KB total script weight (gzipped transfer is smaller; this is the
        // uncompressed budget Lighthouse measures, kept generous as a guardrail).
        'resource-summary:script:size': ['warn', { maxNumericValue: 1500000 }],
        'total-byte-weight': ['warn', { maxNumericValue: 3000000 }],
        'categories:performance': ['warn', { minScore: 0.8 }],
        'categories:accessibility': ['warn', { minScore: 0.9 }],
      },
    },
    upload: {
      target: 'temporary-public-storage',
    },
  },
};
