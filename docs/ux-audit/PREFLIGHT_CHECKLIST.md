# EGI UX pre-flight checklist

Run this before every release (plan-29 §5/§8). It is a **process gate, not
enforced by code**: a release should not be tagged without a signed-off copy.

**How to use:** run the automated pass first, then walk the manual checks on a
real phone in the field conditions EGI is used in (bright sunlight, older
Android, one-handed, switching languages).

```bash
cd frontend
npm run ux:audit        # i18n purity + WCAG contrast + offline self-containment → docs/ux-audit/reports/
npm test                # includes tests/a11y.test.js (button-name / label rules)
npm run build && npm run check:offline
# optional, need network + tools:
npm run ux:lighthouse   # performance / a11y / best-practices / SEO
npm run ux:axe          # full axe accessibility scan
```

**Release:** ________________  **Date:** ____________  **Signed off by:** ____________

---

## 1. Automated gate

- [ ] `npm run ux:audit` passes (i18n purity green; no **critical** contrast fail).
- [ ] `npm test` passes, including the a11y suite.
- [ ] `npm run build` + `npm run check:offline` pass (no font/CDN leaks).
- [ ] Contrast warnings reviewed; no new sub-AA color used for body text.

## 2. Visual consistency

- [ ] Header logo renders uniformly — no oversized "E" in the wordmark.
- [ ] Background color is the neutral token and consistent across all screens.
- [ ] Typography scale is consistent (headings, body, captions, buttons).
- [ ] Buttons / inputs / cards / sheets share radius, border, and padding.
- [ ] Icons are the same size and style within a screen.

## 3. Layout & responsiveness

- [ ] No horizontal scroll from 320 px to 768 px wide.
- [ ] Touch targets are at least 44×44 px (ideally 48×48).
- [ ] Report form submit button is reachable with the keyboard open.
- [ ] Footer / bottom actions (tab bar) remain reachable.
- [ ] Android status bar and navigation bar do not overlap content.

## 4. Internationalization

- [ ] Spanish, English, and Portuguese labels do not overflow or clip on any screen.
- [ ] Offline banner is visible and grammatically correct in all three languages.
- [ ] Dates, numbers, and phone numbers read correctly per locale.
- [ ] No mixed-language strings (`npm run check:i18n` is green).

## 5. Accessibility

- [ ] Color contrast meets WCAG 2.1 AA for body text (4.5:1) and large text (3:1).
- [ ] Interactive elements have visible keyboard focus states.
- [ ] Icon-only buttons and form fields have screen-reader labels.
- [ ] Error messages are clear and tied to the correct field.
- [ ] Reduced-motion preference is respected for animations.

## 6. Navigation & wayfinding

- [ ] Every screen has a clear title or back action.
- [ ] Primary actions are visually dominant; destructive actions are clearly marked.
- [ ] Loading, empty, and error states have helpful copy and a next step.
- [ ] Bottom tab bar is balanced as 3 tabs + centred report button + 3 tabs.
- [ ] Notification preferences are reached through a bell icon (no sun-like glyph).
- [ ] Directions/search default to a place/name field, not coordinates.
- [ ] Home screen has one clear primary action and no more than three secondary ones above the fold.

## 7. Performance perception

- [ ] Skeleton / loading indicators appear within ~200 ms for async actions.
- [ ] Buttons show a disabled/processing state after tap (no double submit).
- [ ] Offline states explain what is cached and what will sync later.

## 8. EGI-specific checks

- [ ] Shelter/hospital directions offer location options, not raw coordinates by default.
- [ ] Mesh screen status text is readable in direct sunlight.
- [ ] "Reportar un problema" in Settings opens a pre-filled mail draft.
- [ ] No analytics/tracking added; only the minimum data is collected.
- [ ] Unverified / unreviewed records are clearly marked.

## 9. Android WebView

- [ ] No system bars overlap content (status bar / nav bar / cutouts).
- [ ] Pull-to-refresh does not conflict with WebView scroll.
- [ ] Hardware back button matches PWA navigation.
- [ ] App renders identically offline (fonts bundled, no CDN).
- [ ] Verified on both lab phones: Samsung SM-S134DL (API 33) and Moto G Play 2023 (API 31).
