# Contributing to EGI

Thank you for helping. This project exists to reunite families during disasters, so we keep the process simple and respectful.

## How to contribute

1. **Open an issue first** for big changes (new protocol, new platform, database changes).
2. **Fork the repo**, create a branch, and make your changes.
3. **Keep changes small and focused**. One feature or bug fix per pull request.
4. **Test your changes** before submitting.
5. **Write clear commit messages** in English or Spanish.
6. **Open a pull request** and describe what you changed and why.

## Areas where help is needed

- Android Bluetooth LE mesh implementation
- Offline-first PWA improvements
- Server scaling and conflict resolution
- Translations (especially Spanish)
- UI/UX for low-bandwidth and low-literacy contexts
- Security review and privacy hardening
- Documentation and deployment guides
- Real-world testing and feedback

## Code style

- Web: vanilla JS, no framework required. Keep it readable.
- Server: Node.js, `async/await`, 2-space indentation.
- Android: Kotlin, standard Android conventions.
- Comments and user-facing strings in English by default; translations welcome.

## Running tests

Server tests (when available):

```bash
cd server
npm test
```

Web app tests are manual for now. Open the site in Chrome DevTools, toggle offline mode, and verify register/search/sync.

## UX pre-flight

Any change that touches the PWA UI should pass the UX audit before review. From
`frontend/`:

```bash
npm run ux:audit   # i18n purity + WCAG contrast over design tokens + offline self-containment
npm test           # includes the automated accessibility checks (tests/a11y.test.js)
```

When you change visual styling, include before/after screenshots in the PR, and
use the design tokens in `frontend/src/styles/tokens.js` instead of new hardcoded
colors/sizes. Before tagging a release, complete
[`docs/ux-audit/PREFLIGHT_CHECKLIST.md`](docs/ux-audit/PREFLIGHT_CHECKLIST.md).
See [`docs/ux-audit/`](docs/ux-audit/) for the audit process and findings.

## Community

Be patient, be kind, and remember the people who will use this software.
