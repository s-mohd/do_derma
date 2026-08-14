# Assessment Mode Toggle On The Tab

Date: 2026-08-13
Status: **Implemented & verified** (2026-08-13) — see [Verification](#verification); one deviation, see [Reconciliation](#reconciliation--what-changed-vs-the-plan)

## Goal

The clinician switches between SOAP and Structured from the Assessment tab button
itself — a compact segmented toggle where the tab hint used to be — and sees a ✓
on the tab once the visit's assessment holds any saved content. The in-panel
"Documenting as … / Change format" banner is removed; it spent a full-width row
saying something a two-segment control says in place. Constraint quoted from the
request: "remove assessment type changing banner and add to assessment tab toggle
button to toggle between assessment types. The tick will show up once assessment
filled."

## Decisions

- **Toggle + tick live on the tab button, panel loses its header** → the user
  chose this over a panel-header toggle in review → trade-off accepted: the tab
  becomes a mixed click target, handled with `@click.stop` on the segments →
  a panel-header segmented control was rejected as it keeps two rows of chrome.
- **Confirm only when the mode being left has saved content** → switching away
  from an empty format is consequence-free, so a dialog there is noise → the
  always-confirm behaviour of the banner was rejected; a fully free toggle was
  rejected because leaving a written format still deserves one deliberate click.
- **Tick = any saved content in either mode, computed server-side** → the
  Structured field list is clinic-configurable, so only the server (layout
  `is_value_field` rows + `_has_content`) can own the predicate → a client-side
  live check was rejected because it would tick before anything is saved.
- **Stamping contract untouched** → printing renders the stamped mode
  (spec 2026-08-12); this feature only changes where the switch UI lives.

## Current State (verified)

- Banner: `do_derma/public/js/chart/components/assessment/AssessmentPanel.vue:3-18`
  (`data-test="assessment-mode-banner"`, `assessment-mode`, `assessment-change-mode`),
  CSS `:215-235`, confirm + emit in `requestModeChange` (`:184-196`),
  `canChangeMode` (`:140-142`). `isStamped` prop is used nowhere else.
- Tab bar: `do_derma/public/js/chart/DermaChart.vue:43-58` renders
  `<span>{{label}}</span><small>{{hint}}</small>` per tab; `SECTION_TABS`
  (`:608-615`) has no completion/count concept. **No tab decoration exists
  anywhere.** `e2e/tests/tab-spine.spec.ts:39` asserts the six labels via
  `sectionBar.locator("button > span")` — any new *direct span child* of the
  button breaks it; nested spans and non-span siblings do not.
- Mode state: Patient Encounter `custom_derma_assessment_mode` (do_derma custom
  field on a healthcare doctype), stamped on first content save
  (`do_derma/assessment.py:233-234`), switched via `stamp_mode` (`:237-248`,
  draft-only). `read_assessment` (`:154-175`) already ships both modes' layouts
  and values; there is **no `is_filled`** in the payload.
- Client mode calls: `setAssessmentMode` (`DermaChart.vue:1694-1708`) →
  `do_derma.api.set_derma_assessment_mode` (`api.py:2063`, gates via
  `_ensure_clinical_access`). Assessment data loads lazily per tab
  (`ensureSectionData`, `DermaChart.vue:1087-1093`), so the tick needs an eager
  `loadAssessment()` after `load()` or it only appears after visiting the tab.
- E2E: `e2e/tests/assessment-modes.spec.ts` drives everything through the banner
  hooks and uses the banner's "Written as" text as its post-save signal.

## Non-Goals

- No change to stamping, printing (`printing/render.py`), practitioner defaults,
  or `set_derma_assessment` write whitelisting.
- No ticks/counts on other tabs (Procedures count is spec B).
- No new endpoint; `is_filled` rides on the existing assessment payload.
- The panel's "also has content saved as {0}" note stays.

## Design

One idea: the server tells the client "documented or not"; the tab renders that
plus a two-segment switch that reuses the existing `set_derma_assessment_mode`
flow, confirming only when the departed mode holds content.

### 1. `is_filled` in the payload — `do_derma/assessment.py`

```python
# read_assessment(): values/soap_values are already serialized
"is_filled": any(_has_content(v) for v in [*values.values(), *soap_values.values()]),
# empty_assessment(): "is_filled": False
```

### 2. Tab decoration + switch logic — `do_derma/public/js/chart/DermaChart.vue`

```html
<button ...>
  <span>{{ section.label }}</span>
  <i v-if="section.key === 'assessment' && assessmentPanel.isFilled"
     class="tab-tick" data-test="assessment-tick">✓</i>
  <small v-if="section.key !== 'assessment' || !assessmentModeToggleVisible">{{ section.hint }}</small>
  <small v-else class="tab-mode-toggle" data-test="assessment-mode-toggle" @click.stop>
    <span v-for="m in assessmentPanel.availableModes" role="button"
          :data-test="`assessment-mode-${m.toLowerCase()}`"
          :data-active="assessmentPanel.mode === m ? 'true' : 'false'"
          @click.stop="requestAssessmentModeChange(m)">{{ m }}</span>
  </small>
</button>
```

`requestAssessmentModeChange(target)`: no-op when locked (`docstatus !== 0`),
saving, or already active; `frappe.confirm` only when the *leaving* mode's saved
values have content (same `hasContent` predicate as the panel); then the existing
`setAssessmentMode`. `applyAssessmentResponse` stores `is_filled`; `load()` calls
`loadAssessment()` eagerly so the tick shows on any tab. Nested interactive
elements: segments are `<span role="button">` because `<button>` cannot nest.

### 3. Panel cleanup — `AssessmentPanel.vue`

Banner header, `.mode-banner` CSS, `canChangeMode`, `requestModeChange`,
`modeLabel`, `isStamped` prop, and the `change-mode` emit are deleted.

### 4. CSS — `derma_chart.bundle.css`

`.tab-tick` (small teal check beside the label) and `.tab-mode-toggle` segments
(pill pair, active segment brand-coloured, `[data-locked]` dimmed), added beside
the existing `.derma-section-tabs` rules.

What stays unchanged: both endpoints, stamping, printing, SoapNoteFields /
StructuredAssessmentFields, chart.page.ts navigation.

## Security

No new endpoint. `is_filled` is derived from fields the caller can already read
through `get_derma_assessment`, which gates via `_ensure_clinical_access`
(`TestAssessmentAccessGate` covers it).

## Acceptance Criteria

- Assessment tab shows `[SOAP|Structured]` where its hint was, once an encounter
  exists and both modes are installed; other tabs are untouched.
- Switching away from an empty mode is instant; away from a written mode asks
  once; nothing is ever deleted (existing backend guarantee).
- Toggle is inert on submitted/cancelled encounters.
- ✓ appears after the first successful content save in either mode, survives
  reload, and shows even when the chart opens on another tab.
- Sites without SOAP fields see the plain hint, no toggle.
- `tab-spine.spec.ts` six-label assertion still passes.

## Phases

1. **Backend flag** — `is_filled` in payload + tests. Exit: `run-tests
   --module do_derma.tests.test_assessment` green with new cases.
2. **Tab toggle + tick** — DermaChart/AssessmentPanel/CSS changes, eager load.
   Exit: manual switch/confirm/tick on dermaone.localhost.
3. **E2E rewrite** — `assessment-modes.spec.ts` on the new hooks. Exit:
   `yarn test:e2e` for the suite green.

## Open Questions

- Should a fresh encounter with defaulted Select values count as "filled"?
  Default: yes if a serialized value survives `_has_content` — revisit only if a
  fresh encounter ever ticks (test asserts it does not).

## Reconciliation — what changed vs the plan

- **The toggle renders only while the Assessment tab is active.** As planned,
  the segments sat on the tab at all times — but then any navigation click that
  landed on a segment (Playwright clicks element centers; users fat-finger)
  would switch the documentation format instead of the tab. Two tab-spine specs
  failed exactly this way. An inactive tab now shows its plain hint; the toggle
  appears once the tab is active, so a format change is always a second,
  deliberate click. Everything else shipped as planned.
- `assessmentPanel.isStamped` was deleted rather than kept: after the banner
  removal nothing read it.

## Verification

- **Unit/integration**: `bench --site dermaone.localhost run-tests --module
  do_derma.tests.test_assessment` — 18 tests OK (4 new in
  `TestAssessmentIsFilled`, RED-first with `KeyError: 'is_filled'`).
  Full app: `run-tests --app do_derma` — **77 tests OK**.
- **E2E**: `npx playwright test assessment-modes tab-spine` — **11 passed**
  (3 rewritten assessment-modes, 8 tab-spine incl. the six-label assertion).
- **Lint**: `ruff check` / `ruff format --check` clean on the two changed Python
  files (`pipx run ruff`, 0.16.1 — the bench env has no ruff binary; 5
  pre-existing findings in untouched files were left alone).
- **Build**: `bench build --app do_derma` clean.
- **Manual (browser, 2026-08-14)**, demo patient `DEMO Amina Haddad`: the tab
  carries the `Structured | SOAP` segments with no banner in the panel;
  switching to an empty SOAP was instant; saving content raised the ✓ on the
  tab; switching away from the now-written SOAP raised the confirm
  ("Switch this visit to Structured Assessment? Nothing you have written is
  deleted."). The toggle is absent on inactive tabs, as designed.

Runner note: `--test <ClassName>` silently runs zero tests on this bench — use
the full module or `Class.test_method`.

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/assessment.py` | `is_filled` in `read_assessment` / `empty_assessment` |
| `do_derma/tests/test_assessment.py` | is_filled cases |
| `do_derma/public/js/chart/DermaChart.vue` | tab tick + toggle, confirm flow, eager load, `isFilled` state |
| `do_derma/public/js/chart/components/assessment/AssessmentPanel.vue` | delete banner + dead code |
| `do_derma/public/js/chart/derma_chart.bundle.css` | `.tab-tick`, `.tab-mode-toggle` |
| `e2e/tests/assessment-modes.spec.ts` | rewrite on new hooks |
