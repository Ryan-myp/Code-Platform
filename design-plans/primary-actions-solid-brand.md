# Normalize primary actions to solid brand purple

Written against: `cc1813fcc8d2c2aa232fe3dd3866e6877ace285f`

## Evidence chain

- Surface: routed frontend pages using the shared `Button` and `Empty` components.
- Problem: the documented primary button is solid purple, but `Button.jsx` currently gives `primary` the same gradient classes as its explicit `gradient` variant. `Empty.jsx` also has a separate gradient fallback action.
- Design evidence: `frontend/docs/design-system.md` specifies `bg-purple-600` with `hover:bg-purple-700`; `frontend/src/components/ui/Button.jsx` and `frontend/src/components/ui/Empty.jsx` show the conflicting implementations.
- Owner: `frontend/src/components/ui/Button.jsx`; the empty-state fallback is owned by `frontend/src/components/ui/Empty.jsx`.
- Scope and affected surfaces: static JSX inspection found 161 default/explicit primary Button instances in 52 page modules. Empty-state fallback actions are an additional consumer when `actionLabel` and `onAction` are supplied.
- Uncertainty: this is a source-backed design-contract mismatch, not a fresh visual audit of every route. Before changing the default, check for any `primary` use that explicitly relies on gradient for a documented reason; use the existing `gradient` variant only for such intentional cases.

## Design decision

Make the shared primary action a solid brand-purple button, matching the documented design system. Keep gradient as an opt-in variant so documented gradient use (including statistics icons) and any explicitly intentional gradient CTA are not removed wholesale. Do not change unrelated elevation, motion, sizing, or page-local decoration in this change.

## Reuse

- Use the existing `Button` component and `primary` / `gradient` variants; do not add another button primitive.
- Use the existing brand/purple palette and the size/interaction behavior already defined by `Button`.
- Exemplar: `frontend/src/components/ui/Button.jsx`.

## Changes

1. `frontend/src/components/ui/Button.jsx`
   - Change: make `VARIANTS.primary` use a solid brand-600 background and brand-700 hover state, with white text. Keep `VARIANTS.gradient` available as the explicit gradient choice.
   - Preserve: loading, disabled, focus, size, icon placement, and existing click behavior.
   - Verify: primary is solid in both normal and hover states; gradient remains available only when requested.

2. `frontend/src/components/ui/Empty.jsx`
   - Change: render the fallback `actionLabel` action through the shared `Button` with `variant="primary"`, rather than duplicating gradient button classes.
   - Preserve: the current `action` override, conditional visibility, label, and `onAction` behavior.
   - Verify: custom actions remain untouched and the fallback action matches the shared primary variant.

3. Existing page consumers
   - Change: reclassify only a consumer that is confirmed to need a gradient CTA to `variant="gradient"`; do not rename primary actions solely because the previous implementation happened to be gradient.
   - Preserve: documented gradients on statistics and other non-button surfaces.
   - Verify: default and explicit primary consumers remain legible and retain their existing actions.

## Scope

- Inherit: all consumers of `Button`'s `primary` default/variant and `Empty`'s fallback action.
- Verify: the 52 page modules with primary Button instances, plus Empty states that expose fallback actions.
- Exclude: explicit `gradient` consumers, statistical icon gradients, page-specific visual changes, and unrelated button states.

## Validation

- Product: trigger a primary action, a loading primary action, a disabled primary action, and an Empty fallback action; confirm their callbacks and state handling are unchanged.
- Interface: inspect representative primary actions in a content page and an admin/workflow page at desktop and narrow mobile widths using synthetic or mocked data; verify normal, hover, focus, loading, and empty-state rendering.
- System: confirm `Button` remains the single owner for the shared primary style and that `gradient` remains opt-in.
- Repository: `cd frontend && npm test -- --run src/tests/components/SharedUI.test.jsx` → focused component tests pass; `cd frontend && npm test -- --run` → full frontend suite passes; `cd frontend && npm run build` → build succeeds; `git diff --check` → no whitespace errors.

## Stop conditions

- Stop if a primary consumer is found to carry a documented semantic meaning that depends on its gradient; preserve that case through the explicit `gradient` variant rather than broadening this change.
- Stop if replacing `Empty`'s fallback with the shared Button changes its callback, form, or keyboard behavior.
- Do not remove gradients from unrelated page surfaces as part of this plan.

## Design documentation

- The current button section already specifies the desired solid style. After acceptance, document that `gradient` is an explicit opt-in variant only if the implementation makes that distinction part of the maintained component contract; otherwise no design-system change is needed.
