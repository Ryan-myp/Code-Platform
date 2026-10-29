# Restrain shared page-header icon tiles

Written against: `cc1813fcc8d2c2aa232fe3dd3866e6877ace285f`

## Evidence chain

- Surface: page titles rendered through `frontend/src/components/ui/PageHeader.jsx` across routed page modules.
- Problem: the shared icon tile combines a gradient background, white icon, and `shadow-glow`. Static inspection found 58 page modules that pass an icon to `PageHeader`; 51 `iconColor` props are spread across 48 page modules, creating a repeated, multicolor title treatment.
- Design evidence: the user approved a global reduction in ornamentation; `frontend/docs/design-system.md` calls for clear, simple hierarchy and documents purple-50 (`#EDE9FE`) as the soft brand color. Its gradient exception is specifically for statistics-card icons, not page-title icons.
- Owner: `frontend/src/components/ui/PageHeader.jsx`; callers are the routed page modules that pass `icon` and optional `iconColor`.
- Scope and affected surfaces: the shared header icon presentation and all `PageHeader` callers in `frontend/src/pages/`; 58 page modules pass an icon, and 48 currently customize its gradient color.
- Uncertainty: the scope is source-backed, but this is not a fresh screenshot review of every route. Page-header icons appear decorative in the inspected component; if a caller uses its color to communicate a meaningful status/category, preserve that meaning through an approved semantic treatment rather than silently discarding it.

## Design decision

Keep the header icon and its placement, but remove the decorative gradient and glow. Use one solid soft-purple tile (`bg-purple-50`) with a purple icon (`text-purple-700`), matching documented brand tokens. Preserve statistics-card gradients and all page content, titles, descriptions, and actions.

## Reuse

- Use the documented `purple-50` and `purple-700` palette; do not add a new token or component.
- Keep the existing `PageHeader` composition and icon accessibility behavior.
- Exemplar: `frontend/src/components/ui/PageHeader.jsx`.

## Changes

1. `frontend/src/components/ui/PageHeader.jsx`
   - Change: replace the icon tile's gradient and `shadow-glow` with a solid purple-50 surface and purple-700 icon.
   - Change: remove the now-unused `iconColor` prop and its PropTypes declaration once all callers are updated.
   - Preserve: tile dimensions, `rounded-xl`, alignment, responsive header layout, title hierarchy, and `aria-hidden` on decorative icons.
   - Verify: headers with and without icons retain their spacing and wrapping; the title icon has no gradient or glow.

2. `frontend/src/pages/*.jsx` callers
   - Change: remove all 51 `iconColor` attributes from the 48 page modules that supply them. Keep each `icon` prop and all other header props unchanged.
   - Preserve: any color that is proven to carry semantic status/category meaning; stop and resolve that case before removing it.
   - Verify: no routed page passes a stale `iconColor` prop, and every existing icon still renders.

3. `frontend/docs/design-system.md`
   - Change: add a short page-header icon rule: solid purple-50 tile, purple-700 icon, no glow; state that the documented statistics-icon gradient remains a separate exception.
   - Preserve: existing statistics-card gradient guidance.
   - Verify: implementation and design guidance agree.

## Scope

- Inherit: all `PageHeader` icon consumers in routed pages.
- Verify: pages with different former icon colors, pages with an icon but no custom color, and headers without icons.
- Exclude: statistics-card icon gradients, non-header illustrations, status colors, page-level content, and unrelated responsive/layout changes.

## Validation

- Product: open representative routed pages with former blue, warm, and green header-icon colors; confirm title, description, action controls, and navigation are unchanged.
- Interface: inspect at desktop and narrow mobile widths; check icon/title alignment, wrapping, and header action wrapping on both icon and no-icon pages using synthetic or mocked data.
- System: `rg '\biconColor=' frontend/src` returns no call sites; confirm `PageHeader` owns the single header-icon treatment and statistics gradients remain intact.
- Repository: add/extend a focused `PageHeader` assertion in `frontend/src/tests/components/SharedUI.test.jsx`; run `cd frontend && npm test -- --run src/tests/components/SharedUI.test.jsx`, `cd frontend && npm test -- --run`, `cd frontend && npm run build`, and `git diff --check`.

## Stop conditions

- Stop if any `iconColor` caller encodes a documented semantic category rather than decoration; retain that semantic distinction through an agreed, restrained treatment.
- Stop if the shared tile change causes title/header misalignment at narrow widths; adjust the shared component rather than adding page-specific overrides.
- Do not touch statistics gradients or unrelated page ornaments in this change.

## Design documentation

- After implementation and validation, record the solid page-header icon treatment in `frontend/docs/design-system.md`, while retaining the existing statistics-gradient exception.
