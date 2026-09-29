# Derma chart: consent from the Procedures tab

Agreed 2026-09-29. Branch `feat/consent-from-procedures`.

## Goal

1. The derma chart has no Consent tab. The Procedures tab gets a **New Consent** button.
2. New Consent: pick a consent template, pick the visit procedures it covers, then preview, fill,
   sign and create as today.
3. One consent covers many procedures, and one procedure may be covered by many consents.
4. Each procedure row shows whether it is consented.

## Constraints

- **do_health is not touched.** Everything ships in do_derma.
- **do_dental keeps working as it is.** On a site with do_dental, derma writes `Encounter Consent`
  with its `procedure_items` table, exactly as today. Dental's own API and UI are not touched.
- **Existing consents are not modified.** No backfill, no migration of data. Legacy `Consent Form`
  records (10,936 on dermaone2, none with `clinical_procedure` set) keep rendering and opening.

## Data model

New child doctype `Derma Consent Procedure` in `do_derma/doctype/derma_consent_procedure/`:

| field | type | options |
|---|---|---|
| `clinical_procedure` | Link, reqd | Clinical Procedure |
| `procedure_template` | Link | Clinical Procedure Template |
| `display_name` | Data | |

`schema.py` adds a hidden Table field to `Consent Form`, created only when `Consent Form` exists:

- `custom_derma_procedures`, Table of `Derma Consent Procedure`, inserted after `clinical_procedure`.

It lives in the schema spine, not a patch, because `install_app` skips patches on fresh installs.

On `Consent Form`, `clinical_procedure` is still set to the first selected procedure, so do_health's
back-link, reports and consent gate see what they see today.

## Backend

New module `do_derma/consent.py`. `api.py` keeps the whitelisted endpoints and delegates.

- `ConsentDoctype` — resolves the active doctype once:
  - `Encounter Consent` when installed (do_dental), procedure table `procedure_items`;
  - otherwise `Consent Form`, procedure table `custom_derma_procedures`.
  Replaces the four inline `"Encounter Consent" if _has_doctype(...) else "Consent Form"` switches.
- `get_render_context(doc, procedures)` — derma builds the context itself rather than calling
  do_health's private `_get_render_context`. Keys are the union of both apps:
  `doc`, `patient`, `patient_name`, `encounter`, `appointment`, `company`, `date`,
  `procedures` (list of `{clinical_procedure, procedure_template, display_name}`),
  `procedure_names`, and `procedure` / `procedure_name` as the display names joined with ", ".
  On the `Encounter Consent` path, dental's own `render_template` is used unchanged.
- `get_consent_coverage(procedure_names)` — returns `{procedure: [consent rows]}` for signed
  (`docstatus = 1`) consents, reading the active procedure table plus the legacy
  `Consent Form.clinical_procedure` field.

Endpoints (names and payload keys unchanged):

- `create_derma_consent`
  - Throws `ValidationError` when no procedure is selected.
  - Throws `ValidationError` when a selected procedure does not belong to this patient and
    encounter.
  - Appends one row per procedure to the active table; on `Consent Form` also sets
    `clinical_procedure` and `procedure_template` from the first row.
  - Renders with `get_render_context`, then keeps the clinician-edited `rendered_html` when sent,
    as today. Submits when signature and signer are present, as today.
- `render_derma_consent_preview` — accepts `procedure_items` and renders with
  `get_render_context`. Keeps today's named-template error on render failure.
- Chart procedure rows (the payload behind `procedures` in `DermaChart.vue`) gain
  `consents: [{name, doctype, consent_form_template, signed_on}]` from `get_consent_coverage`,
  so badges need no extra request.
- `get_derma_consents` and `get_derma_consent_html` stay; they switch to `ConsentDoctype`.

Deleting a procedure covered by a submitted consent must fail with a clear message. do_health
configures `ignore_links_on_delete` around Clinical Procedure, so Frappe's link check may not
fire: `delete_clinical_procedure_entry` checks `get_consent_coverage` and throws itself when the
procedure is covered.

## UI

### Procedures tab

- **New Consent** button (secondary style) before **New Procedure** in `ProcedurePanel.vue`'s
  header. Disabled when the chart is read-only or the visit has no procedures. Emits
  `new-consent`.
- Consent badge in the status cell, under the status pill:
  - **Consented** (with count when more than one): opens the signed consent through the existing
    `openSignedConsent`; with several, a small menu lists them first.
  - **Consent needed** (amber): only when the procedure's template has
    `custom_derma_consent_required` and no signed consent covers it. Emits `new-consent` with that
    row, which becomes the only preselected procedure.
  - Otherwise nothing.

### Consent overlay

A Vue overlay rendered by `DermaChart.vue` hosting the reworked `ConsentPanel.vue` (a
`frappe.ui.Dialog` would put the interactive preview in a separate Vue app, cut off from chart
state).

1. Setup: consent template (existing Link control) and a procedure checklist of this visit's
   procedures (name · status · region). Preselected: procedures needing consent that no signed
   consent covers, or the single row when opened from its badge.
2. Preview and sign: the existing preview, inline fields and signature pad, re-rendered on template
   or selection change.
3. **Create** validates template, at least one procedure, patient name and signature. On success
   the overlay closes, procedures reload, a toast confirms.
4. **Cancel** discards the draft, confirming first when a signature has been drawn.
5. WhatsApp buttons stay behind `enable_whatsapp_consent`, with the current "not configured"
   message.

`ConsentPanel.vue` loses the "Existing Consents" column; the badges replace it.

### Removed

- The `consent` entry in `SECTION_TABS`.
- `SECTION_ALIASES` maps `consent` and `consents` to `procedures`, so stored preferences land
  somewhere real.
- The header "Consent Required" alert becomes per procedure (any procedure needing consent with
  no coverage) and its click opens the Procedures tab.

## Known limitation

do_health's own gate (`custom_requires_consent` on Clinical Procedure Template, checked on
procedure start and submit) only reads `Consent Form.clinical_procedure`. With that flag on, only
the first procedure of a multi-procedure consent would pass. The flag is off on every template
today; derma procedures use `custom_derma_consent_required` instead. The complete fix is a small
do_health change to read `custom_derma_procedures`, deferred until needed.

## Tests

`tests/test_consent.py`:

- Create with two procedures: both rows stored, `clinical_procedure` is the first, coverage lists
  both procedures.
- Legacy `Consent Form` with only `clinical_procedure`, and one with none: coverage is correct and
  `get_derma_consent_html` returns the stored HTML unchanged.
- Rejects an empty selection and a procedure from another encounter.
- Render context carries `procedures`, `procedure_names` and the joined `procedure`.
- Chart procedure rows carry `consents`.

`tests/test_encounter_tabs.py`: `consent` alias resolves to `procedures`; no Consent tab.

Browser check on dermaone: New Consent from the header and from a row badge, two procedures,
sign, create, both rows show Consented, the signed consent opens.

## Out of scope

- Any do_health or do_dental change.
- Remote (WhatsApp) consent signing.
- Editing or re-linking procedures on an already signed consent.
