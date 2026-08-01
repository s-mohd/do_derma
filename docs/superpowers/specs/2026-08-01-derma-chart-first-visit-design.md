# Derma Chart — First Real Visit End-to-End

**Date:** 2026-08-01
**Status:** Approved design, ready for planning
**Scope:** `apps/do_derma`

## Problem

`do_derma` is deployed on `dermaone.localhost` (a faithful copy of production) and has never
been used. Every derma doctype is empty:

| Doctype | Rows |
|---|---|
| Derma Chart Mark | 0 |
| Derma Finding | 0 |
| Derma Photo Set | 0 |
| Derma Treatment Entry | 0 |
| Derma Chart Template | 0 |
| Derma Procedure Category | 0 |

Against 41,878 Patients, 14,994 Patient Encounters and 15,146 Clinical Procedures.

A Playwright walkthrough of `/app/derma-chart` found no dead handlers and no performance
problem — the derma APIs return in 11–143 ms (main call 143 ms / 19 KB) and the annotation
studio opens in 491 ms. The page is not slow or broken. It is **unreachable for real work**,
for three structural reasons.

### Blocker 1 — Clinical Notes, the default tab, renders nothing

The tab shows only the string *"No fields found in Patient Encounter tab custom_assessment."*

`ASSESSMENT_TAB_FIELDNAME = "custom_assessment"` (`api.py:157`) drives
`_assessment_tab_layout()` (`api.py:1129`), which walks `Patient Encounter` meta and collects
fields *after* it matches a Tab Break of that name.

This site's Patient Encounter has two Tab Breaks — `encounter_details_tab` and `notes_tab` —
and neither is `custom_assessment`. Worse, both contain only HTML render fields
(`order_history_html`, `encounter_details`, `clinical_notes`). **All 88 real clinical fields sit
before the first Tab Break**, in Frappe's implicit first tab, which a tab-name scan structurally
cannot address.

### Blocker 2 — The schema the app depends on does not exist

`Custom Field` where `module = "Do Derma"` returns `[]`. The `custom_derma_category` column is
absent from `Clinical Procedure Template`.

Yet all 12 do_derma patches are recorded in `Patch Log` as applied. Frappe runs a patch once
ever, so `bench migrate` will never recreate these fields. `hooks.py` declares `fixtures` for
Custom Field and Property Setter, but `do_derma/fixtures/` does not exist — that declaration
only ever *exports*; on migrate there is nothing to import. There is no `after_migrate` hook.

Nothing in the app can currently create its own schema.

### Blocker 3 — No procedure is configured for derma charting

No patch creates `Derma Procedure Category` records, and none tags a
`Clinical Procedure Template`. `update_category_allowed_templates()` in
`seed_standard_derma_body_templates.py` iterates templates where `custom_derma_category` is
set — a set that is always empty. The annotation studio's procedure picker therefore has
nothing to offer even once Blocker 2 is fixed.

### Not a blocker: missing body-template images

All 25 `Derma Body Template` images 404 locally, so the canvas is blank and the picker shows
broken-image icons. All 25 have `File` records, so the images exist in production — only this
bench lacks the blobs. This is a local environment gap, addressed under Verification below.
The app-level gap is narrower: a failed image produces no message to the user.

### Context: what clinicians use instead

`Health Annotation` holds 5,434 records, and `Health Annotation Table` links them
**5,485 to Clinical Procedure versus 15 to Patient Encounter**. The incumbent workflow is
procedure-anchored; the Derma Chart is encounter-anchored.

That workflow stopped dead after March 2026 — 288 annotations in March, then zero in April,
May, June and July — while Clinical Procedures (420, 449, 464, 241) and Patient Encounters
(649, 542, 509, 173) continued at normal volume. do_derma's first commit is 2026-06-17, two
months later, so it did not cause the stoppage. Roughly 1,500 procedures have since been
recorded with no body-map documentation at all.

*Out of scope, flagged for follow-up: why the do_health annotation workflow stopped in April
2026.*

## Goal

One clinician charts one real dermatology visit start to finish. UI cleanups ride along where
they touch the same screens.

## Non-goals

- An admin UI for configuring procedure templates
- Migrating the 5,434 existing procedure-anchored annotations
- Reworking the encounter-anchored vs procedure-anchored model
- Diagnosing the April 2026 annotation stoppage
- General refactoring of `api.py`, `DermaChart.vue` or `ProcedurePanel.vue`

## Architecture

Three files exceed the 800-line ceiling in the project coding rules: `api.py` (3,481 lines,
39 endpoints), `DermaChart.vue` (2,794), `ProcedurePanel.vue` (2,550). This design does not
refactor them; it requires that **new code land in new modules** and that the one panel being
substantially rewritten be split.

| File | Responsibility | Est. lines |
|---|---|---|
| `do_derma/schema.py` | Declarative custom-field spec, `ensure_derma_schema()` | ~200 |
| `do_derma/setup/__init__.py` | New package marker | 0 |
| `do_derma/setup/defaults.py` | Seed categories, configure Laser and Facial | ~150 |
| `do_derma/do_derma/doctype/derma_settings/` | New singleton holding the structured field list | ~60 |
| `do_derma/assessment.py` | Layout resolution, mode stamping, SOAP serialisation | ~250 |
| `do_derma/install.py` | Single `after_migrate()` entry point | ~30 |
| `components/SoapNoteFields.vue` | SOAP narrative inputs | ~250 |
| `components/StructuredAssessmentFields.vue` | Curated structured inputs | ~250 |
| `components/AssessmentPanel.vue` | Shell, mode banner, format toggle (rewritten from 855) | ~250 |

`api.py` gains only thin `@frappe.whitelist()` wrappers delegating to `assessment.py`. Every
one begins with `_ensure_clinical_access()` — that role check is the authorization boundary for
this module, and `TestClinicalAccessGate` exists to enforce it.

## Schema spine

`ensure_derma_schema()` runs on every `bench migrate` via the `after_migrate` hook, bypassing
`Patch Log` entirely. This is what repairs the current site, where the patches are recorded as
done and will never run again.

Two distinct required properties:

- **Idempotent** — creating a field that already exists is a no-op.
- **Never clobbering** — a *value* is written only when the current one is empty. A clinic that
  retags `Laser` to its own category keeps that across migrates. Without this rule,
  "self-healing" becomes "resets clinic configuration on every migrate."

New custom fields on `Patient Encounter`, module `Do Derma`:

| Fieldname | Type | Purpose |
|---|---|---|
| `custom_derma_assessment_mode` | Select — `Structured`, `SOAP` | The format this visit was documented in |
| `custom_derma_soap_subjective` | Small Text | S |
| `custom_derma_soap_objective` | Small Text | O |
| `custom_derma_soap_assessment` | Small Text | A |
| `custom_derma_soap_plan` | Small Text | P |

On `Healthcare Practitioner`:

| Fieldname | Type | Purpose |
|---|---|---|
| `custom_derma_default_assessment_mode` | Select — `Structured`, `SOAP` | Default for that practitioner's *new* encounters only |

`Small Text` rather than `Text Editor`, matching sibling clinical fields
(`custom_physical_examination`, `custom_symptoms_notes`) so notes stay plain text and print
predictably.

The 12 existing patches are left untouched as historical record. New sites and drifted sites
both converge through the hook.

## Assessment modes

`ASSESSMENT_TAB_FIELDNAME` and the tab-scan in `_assessment_tab_layout()` are removed.

**Structured Assessment** renders a named field list, defaulting to:

`symptoms`, `custom_symptom_duration`, `custom_symptoms_notes`, `custom_illness_progression`,
`diagnosis`, `custom_differential_diagnosis`, `custom_diagnosis_note`,
`custom_physical_examination`, `custom_other_examination`

Configurable through a new `Derma Settings` singleton. Every field passes an existence check
before rendering, so a site missing one degrades rather than blanking the panel.

**SOAP Note** renders the four narrative fields, stored independently of the structured fields.

### Mode rules

1. A new encounter opens in the practitioner's default (`Structured` when unset), unstamped.
2. The first save of any assessment content **stamps** `custom_derma_assessment_mode`.
3. A stamped encounter always reopens in its stamped mode. The practitioner default never
   overrides a stamp.
4. A banner names the format — *"Documented as SOAP note"* — with a **View structured fields**
   toggle rendering the other format read-only.
5. Changing format is an explicit action, allowed only while `docstatus = 0`, behind a confirm
   dialog.
6. **Switching never deletes.** Content in the inactive format remains stored and reappears on
   switching back.

Rule 4 is the safety mechanism. Because the two formats store separately, a SOAP-documented
visit shows empty structured fields — indistinguishable from an undocumented visit, which
invites duplicate re-documentation. The banner and read-only toggle make an empty format read
as *deliberately empty* rather than *missing*.

## Printing

Both `Patient Encounter` print formats are hand-written HTML (`print_format_builder: 0`), and
the site default is the custom `Encounter print (Dr Sadiq)`. Hand-written templates render only
the fields they name, so new fields are invisible to them by default — a SOAP-documented visit
would print blank.

Both `Encounter print (Dr Sadiq)` and `Encounter Print` gain a conditional block keyed off the
stamped mode: SOAP renders the four narrative fields, Structured renders the curated list. A
visit prints in the format it was written.

## Configuration seed

`setup/defaults.py` creates the eight categories the code already references — Botox, Filler,
Laser, Acne, Scar, Pigmentation, Lesion, Biopsy — plus **Facial**, which has no category today
despite being 10% of procedure volume.

It then configures the two templates covering 92% of all procedures ever recorded:

| Template | Procedures | Share |
|---|---|---|
| Laser | 12,352 | 81.5% |
| Facial | 1,543 | 10.2% |

The remaining 27 templates stay untagged and simply do not appear in the picker. All writes
follow the never-clobbering rule.

### Assumptions requiring clinical sign-off

These are configuration guesses, not derived facts. They must be confirmed by a clinician
before the pilot, and are called out here so they are not mistaken for research:

- **Marker behaviour** defaults to `area` for both Laser and Facial.
- **Laser variables**: device, fluence, spot size, pulse width, passes.
- **Facial variables**: product, layers.
- **Allowed body templates** follow the existing mapping in
  `seed_standard_derma_body_templates.update_category_allowed_templates()`.

## UI cleanups

### Misleading states

- **Review empty state.** Today reads *"No procedures added yet · Procedures will appear here
  after they are recorded for this patient"* directly above a timeline of 11 visits, each with
  a procedure. The empty state is encounter-scoped; the copy is patient-scoped. Rescope to
  *"No procedures in this visit"*, with the history explicitly labelled as prior visits.
- **Consent.** The Consent Template field renders with a red required-field border on mount,
  before any interaction. Validate on submit attempt, not on mount.
- **Body-map image failure.** A failed image yields a broken-image icon in the picker and a
  blank canvas, with no explanation. Render a labelled placeholder and an explicit message in
  both places.

### Redundancy

- **Photos tab** renders `Encounter Evidence` and `Photo Compare` identically to the right
  rail — the same two panels twice on one screen. The main column owns them while the Photos
  tab is active; the rail hides them there.
- **Duplicate actions.** `@new-procedure="openAnnotationStudio"` (`DermaChart.vue:549`) makes
  *New Procedure* and *Annotate* the same handler, and *Annotate* appears three times on one
  screen. Collapse to a single annotate action in the section bar. Quick Actions keeps only
  distinct entries: New Prescription, Upload Photos, Consent, Follow-up.

### Design system

- **Prescription** embeds a raw Frappe grid with a blue Save against the app's green palette.
  Restyle to the app palette.
- **Complete Session** is removed. It and *Complete Encounter* both emit to `completeSession()`
  → `do_derma.api.complete_derma_session` — one action behind two labels and two colours.
  *Complete Encounter* keeps the header slot. `Sync Billables` is left unchanged.

### Header

Patient name truncates to *"MARWA JAMAL SALEH ALI BAR..."* with no tooltip. Wrap or add a
tooltip, and raise contrast on the allergies / visit / status / insurance chips.

## Error handling

New chart-context sections wrap in `_safe_derma_context(label, fallback, getter)` so one failing
sub-query degrades that section rather than blanking the chart. `ensure_derma_schema()` logs
per-field failures and continues, so one bad field definition cannot abort a migrate.

## Verification

The 25 body-template images are copied from production into
`sites/dermaone.localhost/private/files/`. They are anatomical diagrams and contain no patient
data. Without them the annotation flow cannot be visually verified, since marks are stored as
percentages relative to the template element and correctness is a question of anatomical
position.

Tests are Frappe `IntegrationTestCase` run through the bench runner. No pytest.

| Test | Asserts |
|---|---|
| `test_creates_missing_custom_fields` | Fields appear on a site lacking them |
| `test_second_run_is_noop` | Re-running creates nothing and changes nothing |
| `test_never_overwrites_existing_value` | A clinic-set `custom_derma_category` survives |
| `test_layout_returns_curated_fields` | Structured layout matches the configured list |
| `test_layout_skips_absent_fields` | A missing field is dropped, not fatal |
| `test_mode_stamped_on_first_save` | `custom_derma_assessment_mode` set on first content save |
| `test_stamped_mode_honoured_on_reopen` | Practitioner default does not override a stamp |
| `test_switch_preserves_other_format` | Round-trip switch loses no content |
| `TestClinicalAccessGate` | Extended to every new endpoint |

### Acceptance

A practitioner opens the Derma Chart for a Laser appointment, writes an assessment in either
mode, opens the annotation studio, selects a body template that renders, picks the Laser
procedure, places marks, saves, sees those marks in Review, and completes the encounter — with
`Derma Chart Mark` rows written and the note printing in the format it was written in.

## Sequencing

1. Schema spine — `schema.py`, `install.py`, `after_migrate`. Unblocks everything.
2. Copy template images to the local bench. Unblocks visual verification.
3. Configuration seed — `setup/defaults.py`.
4. Assessment modes — `assessment.py`, panel split, `Derma Settings`.
5. Print formats.
6. UI cleanups.

Steps 1–3 are prerequisites for a chartable visit. Steps 4–6 are independent of each other and
may proceed in any order once 1–3 land.
