# Derma Chart Revamp — Declutter The Page And Give Assessment Two Modes

Date: 2026-08-09
Status: **Phases 1–2 implemented & verified** (2026-08-09) — Phases 3–5 are Draft.
See [Reconciliation](#reconciliation--what-changed-vs-the-plan) and [Verification](#verification).

## Goal

A practitioner opens the Derma Chart and moves left-to-right through six tabs, filling in one
kind of thing per tab, with no control on screen that duplicates another and none that does
nothing. On the first tab they choose how to document the visit — a **SOAP Note** or a
**Structured Assessment** — and the visit reopens in whichever format it was written in.

The page was built by another developer and handed over. The request, verbatim:

> "The pages look too busy. A lot of actions everywhere. […] There are not a lot of actions
> are actually needed and they are good, but need some justification regarding design and
> functionality."

> "I like the idea how it looks as a tabs and the practitioner can move between the tabs to
> fill up the needed data, and the first tab, which is assessment, I want the practitioner
> to choose between two types of assessments: SOAP or the current one, which is the fields
> inside the patient encounter, which includes examination and other fields."

> "I like how the current annotation is working, like a pop-up."

> "Let's work on all the actions are really there in the page and see if that action is
> really needed or not and how it should look and function."

Why it is hard today: the duplication is not cosmetic. Four buttons in three places call one
zero-argument handler that ignores where it was clicked from, so `New Procedure` and
`Annotate` are literally the same call. The first tab renders nothing because it depends on a
Tab Break that does not exist on this site. And the two annotation flows the request describes
— consultation-level and procedure-level — exist in the backend but only one is reachable.

## Decisions

- **Delete the right rail entirely** → every one of its controls duplicated a tab or the
  toolbar, so removing it costs no capability and reclaims the page width. Trade-off accepted:
  Smart Alerts lose their permanent home and move into the header strip as chips, which is less
  room for detail. Rejected: keeping a narrow alerts-only rail, because a rail that exists for
  one occasional widget still narrows every tab underneath it.

- **Six tabs in visit order** (Assessment · Procedures · Photos · Prescription · Consent ·
  Review) → each tab owns one job and the order matches how a visit is actually documented.
  Trade-off accepted: one more tab than today, and `Review` shrinks to read-only sign-off.
  Rejected: four phase-grouped tabs (Assessment/Treatment/Evidence/Sign-off), because each
  would hold two unrelated concerns and reintroduce the "what is this tab for" problem;
  rejected: keeping five tabs and making `Review` an accordion, because `Procedures` — the
  centre of a derma visit — would stay buried inside a tab named for something else.

- **Assessment Mode is stamped on the encounter, not chosen per view** → a note always reopens
  in the format it was written in, so a SOAP visit can never be silently re-read as an empty
  structured one. Trade-off accepted: an extra Select field on `Patient Encounter` and a
  confirm dialog to change format. Rejected: rendering both formats at once, because a
  half-filled SOAP note next to half-filled structured fields is worse documentation than
  either alone.

- **Switching mode never deletes the other format's content** → the two formats store in
  separate columns, so a switch is reversible. This is the safety mechanism that makes the
  stamp acceptable: without it, a mis-click would look like data loss.

- **The structured field list lives in a `Derma Settings` singleton, not in a Tab Break scan**
  → explicit config over implicit behavior, and the current scan is exactly why the first tab
  is blank. Trade-off accepted: a new singleton doctype and a seed step. Rejected: shipping the
  missing `custom_assessment` Tab Break as a Custom Field, because a Tab Break captures every
  field after it and would reorder the `Patient Encounter` form for every user of the site,
  including non-derma clinics; rejected: a hardcoded Python list, because a clinic cannot
  change what it documents without a code change.

- **Two explicitly labelled annotation entry points, anchored per row** → `Annotate
  Consultation` on the Assessment tab writes to the `Patient Encounter`; each procedure row on
  the Procedures tab has its own `Annotate (n)` writing to that `Clinical Procedure`. Trade-off
  accepted: two labels instead of one generic button. Rejected: one button that infers the
  anchor from the active procedure, because the anchor is invisible at click time and a
  mis-anchored annotation is not something a practitioner can see or undo.

- **The annotation studio stays a full-screen pop-up** → the request says so explicitly, and
  the React-in-Vue overlay already works. Nothing about the mounting model changes.

- **Refresh is removed entirely; a retry appears only where loading actually failed** →
  `_safe_derma_context` degrades a broken section to empty rather than erroring, so a permanent
  Refresh button is treating a reporting gap as a user chore. Trade-off accepted: backend must
  now report *which* sections degraded. Rejected: collapsing eight buttons to one in the
  header, because it is still a control the practitioner never needs on a healthy visit.

- **Non-working controls are hidden behind `Derma Settings` toggles, not deleted** → the
  clinic has not decided whether WhatsApp consent, lab cases and billing sync are wanted, and
  a toggle is a cheaper reversal than a revert. Trade-off accepted: dead code stays in the
  tree, and the spec must say so out loud so it is not mistaken for working capability.

## Current State (verified)

Everything in this section was read from the code on 2026-08-09, not remembered.

### The first tab renders nothing

`ASSESSMENT_TAB_FIELDNAME = "custom_assessment"` (`do_derma/api.py:157`) drives
`_assessment_tab_layout()` (`do_derma/api.py:1129`), which walks `Patient Encounter` meta and
collects the fields *after* it matches a Tab Break of that name (loop at `api.py:1131-1163`).
This site's `Patient Encounter` has two Tab Breaks — `encounter_details_tab` and `notes_tab` —
and neither is `custom_assessment`. The tab shows the string *"No fields found in Patient
Encounter tab custom_assessment."*

`AssessmentPanel.vue` is entirely meta-driven: it hardcodes no fields, seeds
`{ doctype: "Patient Encounter" }` (`AssessmentPanel.vue:464`), and builds every control via
`frappe.ui.form.make_control` from the server-supplied `layout` (`makeControl` `:534`, section
splitting `:218`). Fields named `custom_past_visit_*` are force-read-only (`:371`, applied
`:507`).

### There is no SOAP anywhere in running code

Grepped `soap|subjective|objective` case-insensitively across `do_derma`, `do_health`,
`healthcare`, `erpnext` and `frappe` for `.py`, `.json`, `.js`, `.vue`, `.md`, `.html`, `.csv`.
Results:

- `CONTEXT.md:28-50` — the glossary **specifies** Assessment Mode / SOAP Note / Structured
  Assessment / Practitioner Default. Committed in `a1d04ed`. A spec, not an implementation.
- `DermaChart.vue:646` — the tab is labelled `Clinical Notes` with the hint `SOAP`. Cosmetic.
- `DermaChart.vue:72` — a CSS class named `clinical-soap-stack`. Cosmetic.
- `DermaChart.vue:2158` — `assessmentSummaryField()` picks a target field with the regex
  `/assessment|summary|note|plan|objective|subjective/i` and falls back to
  `writableTextRows[0]`. This is the only SOAP-adjacent logic that runs, and it will happily
  write a generated summary into an unrelated text field. It is reached only from
  `copySummaryToAssessment` (`:2129`), which has **no call sites**.

**Zero hits** for S/O/A/P fieldnames in any DocType JSON, any Custom Field patch, any fixture,
or `api.py`. Stock `Patient Encounter` (owned by `healthcare`) offers no narrative columns to
reuse: `symptoms` and `diagnosis` are Table MultiSelects, `physical_examination` is a **Column
Break, not a text field**, `clinical_notes` is an **HTML render slot, not storage**, and
`encounter_comment` (Small Text, labelled "Review Details") is the only stock free-text field.
The examination text field practitioners actually use is do_health's
`custom_physical_examination`, added by
`do_health/do_health/patches/add_clinical_documentation_custom_fields.py`.

That same do_health patch owns the whole structured set on `Patient Encounter`:
`custom_symptom_duration`, `custom_symptoms_notes`, `custom_differential_diagnosis`,
`custom_diagnosis_note`, `custom_physical_examination`, `custom_other_examination`,
`custom_illness_progression`, `custom_pre_operative_diagnosis`,
`custom_post_operative_diagnosis`, plus the read-only `custom_past_visit_*` mirror set.

### The right rail has no unique action

`DermaQuickActionsPanel.vue` renders six buttons (`:9-14`). Wired in `DermaChart.vue:551-556`:

| Button | Actually does |
|---|---|
| `New Procedure` | `openAnnotationStudio` — zero args |
| `Annotate` | `openAnnotationStudio` — zero args, identical call |
| `New Prescription` | `setActiveSection('prescriptions')` — navigation |
| `Consent` | `setActiveSection('consent')` — navigation |
| `Upload Photos` | `uploadPhotos('Visit')` — duplicate of the toolbar button |
| `Follow-up` | `setActiveSection('clinical')` — navigates to the **wrong** tab |

`New Procedure` and `Annotate` differ only in that `canAnnotate`/`allowEvidence` gate the
latter (`DermaQuickActionsPanel.vue:12`) and not the former (`:9`). Separately, `consent`,
`followup` and `annotate` are emitted at `:12-14` but missing from `defineEmits` at `:44`.

The rail also mounts a **second** `DermaEvidencePanel` (`DermaChart.vue:560`, the first is at
`:127`) with `:active-procedure="null"`, and both bind `select-photo-set` to the same
`selectedPhotoSetName` — so the two copies are coupled. Below it sits a Visit Summary card
(`:574-598`) whose procedure buttons call `activateProcedure`, which itself calls
`setActiveSection("review")` (`:1645`) — clicking it navigates you away.

### Duplicate counts

- **`Refresh` — 8 entry points**: `AssessmentPanel:5`, `PrescriptionPanel:5`,
  `AnesthesiaPanel:5`, `ConsentPanel:5`, `ProcedurePanel:50`, `DermaEncounterHeader:32`, plus
  two `Retry` buttons at `DermaChart.vue:20` and `:26`.
- **`Upload Photo` — 6 entry points**: `DermaChart.vue:61`, `:125`, `:311`, `:553`, `:570`, and
  `DermaEvidencePanel:9`. Four of the six hard-code `'Visit'` even when a procedure is active;
  only `:125`/`:137` branch to `'Procedure'`.
- **`Complete` — 2 labels, one handler**: `Complete Encounter` (`DermaEncounterHeader:33`) and
  `Complete Session` (`ProcedurePanel:401`) both reach `completeSession` (`DermaChart.vue:38`
  and `:198`). Their disabled logic differs.
- **`Select Mark` — 2 buttons, near-identical handlers**: `selectInventoryMark` (`:1689`) and
  `selectFollowupMark` (`:1700`) differ only in how they read the mark name.
- **`Annotate` — 4 buttons, 1 handler**: `DermaChart.vue:57`, `:95`, `:551`, `:554`.

### Controls that are visible and do nothing

- **WhatsApp consent trio.** `sendConsentViaWhatsApp` (`DermaChart.vue:2521`),
  `resendConsentViaWhatsApp` (`:2525`) and `cancelRemoteConsent` (`:2529`) all call
  `unsupportedRemoteConsentMessage()` (`:2513`). `Send via WhatsApp` is rendered as the
  **primary** button on the Consent tab (`ConsentPanel.vue:12`).
- **Three unbound ProcedurePanel emits.** `edit-surfaces` (`:226`), `open-lab-case` (`:241`)
  and `create-lab-case` (`:251`) are declared at `:314-316` and rendered as clickable buttons,
  but `DermaChart.vue:184-199` binds none of them.
- **`Sync Billables`.** `sync_derma_billables` (`api.py:2444`) counts procedures and returns
  `added: 0, updated: 0` with "Billing sync is not configured".
- **Anesthesia.** `get_derma_anesthesia` (`api.py:2191`) and `set_derma_anesthesia` (`:2198`)
  are stubs returning an empty list and persisting nothing. `AnesthesiaPanel.vue` (268 lines)
  is **never imported anywhere** — the only surviving consumer of its data is the
  "Anesthesia recorded" badge (`ProcedurePanel.vue:49`, fed by `anesthesiaRecorded`
  `DermaChart.vue:776`). `saveAnesthesiaPanel` (`:2434`) has no caller.

### The workspace tab set does not exist

`activeWorkspaceTab` (`DermaChart.vue:664`) and `ensureWorkspaceTab` (`:1940`) are live, but
`setActiveWorkspaceTab` (`:1935`) has **zero call sites** and the tab-nav markup is gone —
`:182` is an empty `div.workspace-tabview` wrapper. The five workspace tabs described in
`CLAUDE.md` are reachable only programmatically.

### Annotation anchoring

Owned by **do_health**, not do_derma: `Health Annotation` and the `Health Annotation Table`
child table. The anchor is entirely the child row's `parenttype`/`parent` — `Health Annotation`
has no encounter or procedure link field of its own. `custom_annotations` is a Table custom
field created by `do_health/do_health/patches/add_clinical_documentation_custom_fields.py` on
exactly two parents: `Clinical Procedure` and `Patient Encounter`.

**The backend supports both anchors.** `save_derma_annotation` (`api.py:1999`) branches at
`:2005`: `doctype = values.get("doctype") or ("Clinical Procedure" if clinical_procedure else
"Patient Encounter")`. Downstream: `encounter_type` defaults to `"Treatment"` for procedures
(`:2036`); `_link_procedure_annotation` (`:2071`) stamps `Derma Treatment Entry.annotation` for
procedure-anchored saves only. Reads mirror it — `_load_derma_annotation_context` (`:1026`)
splits `encounter_annotations` from `procedure_annotations` keyed by procedure name
(`:1044-1047`).

**The frontend uses one anchor and cannot edit.** `DermaAnnotationStudio.save()`
(`DermaAnnotationStudio.jsx:390-411`) hardcodes `doctype: "Patient Encounter"` (`:397`) and
`docname: context.encounter` (`:398`), never sends `clinical_procedure`, never sends
`annotation_name`, and passes `marks={[]}` (`:510`). `openDermaAnnotationStudio` (`:582-600`)
accepts a `context` of `{patient, encounter, appointment}` only — **there is no
`clinical_procedure`, `doctype` or `docname` option**. Consequences:

1. Every save creates a *new* `Health Annotation`; reopening `Annotate` gives a blank canvas.
2. `_get_annotation_counts_for_procedures` (`api.py:937`) counts rows with
   `parenttype = "Clinical Procedure"`, so the per-procedure evidence badge always reads 0.
3. `DermaChart.vue:2178` *does* implement the procedure branch — it is dead code depending on
   `excalidrawRef` (`:668`), which is never bound because no `<EmbeddedExcalidraw>` exists in
   the template.

The procedure picker inside the studio selects Clinical Procedure **Templates** for stamping
(`DermaAnnotationStudio.jsx:263`, `:305-311`), not Clinical Procedure documents — it is not an
anchor picker.

### `_sync_chart_marks_for_annotation` — its fan-out branch does not fire

`CLAUDE.md` calls this the trickiest contract in the codebase. Verified behaviour
(`api.py:1889-1996`), single call site at `:2046`:

- Requires a template element tagged `derma_template`/`derma_template_image` or it returns
  immediately (`:1907-1915`).
- The tagging loop **skips any element that has `customData.kind`** (`:1922-1923`) and then
  looks for `custom.get("procedure") or custom.get("type")` (`:1924`). Every element the
  frontend creates writes `kind: "derma_mark"` and the key `procedure_template` —
  see `baseElement` (`EmbeddedExcalidraw.jsx:893-900`) and `tagAreaElement` (`:457-476`).
  **So `tagged` is always empty in practice.**
- Only the stamp-backlink block (`:1978-1996`) does real work: marks created eagerly at
  placement time by `handleMarkPlaced` → `save_chart_mark`
  (`DermaAnnotationStudio.jsx:329-372`) get their `annotation` field backfilled.
- The deletion loop (`:1972-1976`) spares marks with `clinical_procedure` set.

This is relevant to Phase 3 because adding a real procedure anchor changes what
`base_payload["clinical_procedure"]` carries (`:1943-1949`).

### Optional schema this feature must survive the absence of

- `Health Annotation Table.annotation_data` — created by do_derma's own patch
  `do_derma/patches/add_derma_annotation_data_field.py:22`, guarded by `_has_field` at
  `api.py:1834`.
- `Health Annotation.custom_derma_body_template_title` — referenced at `api.py:1834`,
  `:1842-1843`, `:1858-1859` but **no patch or fixture anywhere creates it**. The body-template
  title is therefore silently not persisted on the annotation; it survives only inside the
  scene JSON as `scene["derma_template"]` (`api.py:2015-2021`).
- Every do_health `custom_*` field in the structured list. The site may lack any of them.

### Why patches cannot fix any of this

`Custom Field` where `module = "Do Derma"` returns `[]`, yet all 12 do_derma patches are
recorded as applied in `Patch Log`. Frappe runs a patch once ever, so `bench migrate` will
never recreate them. `hooks.py:19` declares a `fixtures` entry for Custom Field but
`do_derma/fixtures/` does not exist — that declaration only ever *exports*. There is no
`after_migrate` hook. **Nothing in the app can currently create its own schema.**

### Dead code inventory

~25 handlers in `DermaChart.vue` have zero template references and zero internal callers:
`setActiveWorkspaceTab` `:1935`, `createProcedure` `:1947` (with `buildProcedurePayload`
`:1996`), `startNewProcedure` `:1758`, `startAnnotationMode` `:2329`, `saveAnnotation` `:2162`,
`loadAnnotation` `:2206`, `carryForwardLatestAnnotation` `:2236`, `copySummaryToAssessment`
`:2129`, `openEncounter` `:1608`, `toggleChartExpanded` `:2252`, `setChartOverlayMode` `:1548`,
`selectTemplate` `:1737`, `selectTemplateRegion` `:1678`, `openTemplateLibrary` `:2308`,
`newBodyTemplate` `:2312`, `openBodyTemplateDesigner` `:2320`, `setDefaultBodyTemplate` `:2263`,
`saveAnesthesiaPanel` `:2434`, `handleReadinessItem` `:1809`, `focusRequiredProcedureFields`
`:1801` (queries `.derma-procedure-fields`, markup that no longer exists).

Associated dead state: `chartMode` `:666`, `chartExpanded` `:667`, `excalidrawRef` `:668`,
`procedureSaving` `:669`, `annotationSaving` `:670`, `markSaving` `:671`, `summarySaving`
`:672`, `selectedMarkNames` `:674`, `selectedPreviousMarkNames` `:675`, `MARK_STATUSES` `:642`,
`anesthesiaTypes` `:775`, `practitioners` `:773`, `modeDisabled` `:799`, `visitSummary` `:768`,
`summaryMetaLabel` `:790`, `treatmentSetLabel` `:919`, `categoryGroups` `:978`,
`historyPanelTitle` `:1065`.

### Section persistence

`DERMA_SECTION_STORAGE_KEY = "do_derma_chart_last_section"` (`:653`). Reads are triple-source
(`loadStoredDermaSection` `:1342`): Frappe user settings → localStorage → `"clinical"`. Writes
are dual (`persistDermaSection` `:1358`): both localStorage and user settings. Two defects:

1. The try block at `:1344-1349` returns `normalizeDermaSection(undefined)` = `"clinical"`
   whenever settings exist but are empty, so the localStorage fallback at `:1350` is reached
   only if `get_user_settings` *throws*.
2. `hydrateDermaSectionPreference` (`:1372`) is invoked from `load()` (`:1439`) and overwrites
   `activeSection` asynchronously — **it can yank the practitioner off the tab they just
   picked** once the first load resolves.

Writes go to `last_section` only; reads accept `last_section` **or** legacy `last_mode`.

### Dental leftovers

The app is dermatology but carries dental structure: `Dental Anesthesia` /
`custom_dental_anesthesia` (`AnesthesiaPanel.vue:114`, `:129`, `:132`), `Dental Note Template`
(`ProcedurePanel.vue:1114`), and `rowAllowsSurfaces` matching `crown|implant|extraction|
prosthesis` (`ProcedurePanel.vue:1497`). Relabelled "Area" in the UI, still dental underneath.
Out of scope here; recorded so it is not rediscovered.

## Non-Goals

- **Refactoring `api.py`, `ProcedurePanel.vue` or `EmbeddedExcalidraw.jsx`.** They are
  sanctioned size exceptions. `DermaChart.vue` is touched only to shrink it.
- **Migrating the 5,434 existing procedure-anchored `Health Annotation` records.** They keep
  working through the existing read path.
- **Diagnosing why the do_health annotation workflow stopped in April 2026.** Flagged in the
  prior spec, still open, still not this.
- **Print formats.** Deferred by decision — see Open Questions for the risk this leaves.
- **Wiring `AnesthesiaPanel.vue` or implementing the anesthesia endpoints.** The file stays
  untouched and unimported. It is *not* covered by a feature toggle; nothing pretends it is.
- **Implementing WhatsApp consent or billing sync.** Their controls are hidden, not built.
- **Changing how the annotation studio mounts.** It stays a React `createRoot` overlay
  launched from Vue — the request asked to keep the pop-up.
- **Fixing the dead fan-out branch of `_sync_chart_marks_for_annotation`.** Phase 3 must not
  *break* it further, but reviving element-tagged fan-out is separate work.
- **The dental-to-derma structural cleanup.**
- **Any change to `permission_query_conditions` or the DocPerm matrix.**
  `_ensure_clinical_access()` remains the authorization boundary.

## Design

The core idea in three sentences. A `Derma Settings` singleton and an `after_migrate` schema
spine give the app the ability to create and configure its own fields, which is what unblocks
a working first tab. `AssessmentPanel` splits into a shell plus one component per Assessment
Mode, with the mode stamped on the encounter so a note always reopens as written. Everything
else is subtraction: one rail, four annotate buttons, eight refresh buttons and ~25 orphaned
handlers come out, and the two annotation anchors the backend already supports get one clearly
labelled entry point each.

### 1. Schema spine — `do_derma/schema.py` *(new)*, `do_derma/install.py` *(new)*

`ensure_derma_schema()` runs on every `bench migrate` via an `after_migrate` hook, bypassing
`Patch Log` entirely — that is the only way to repair a site whose patches are recorded as
applied but whose fields are absent. Two properties, both load-bearing:

- **Idempotent** — creating a field that exists is a no-op.
- **Never clobbering** — a *value* is written only when the current one is empty. Without this
  rule, "self-healing" becomes "resets clinic configuration on every migrate".

```python
DERMA_CUSTOM_FIELDS = {
	"Patient Encounter": [
		{"fieldname": "custom_derma_assessment_mode", "fieldtype": "Select",
		 "options": "\nStructured\nSOAP", "label": "Derma Assessment Mode",
		 "read_only": 1, "no_copy": 1},
		{"fieldname": "custom_derma_soap_subjective", "fieldtype": "Small Text", ...},
		{"fieldname": "custom_derma_soap_objective", ...},
		{"fieldname": "custom_derma_soap_assessment", ...},
		{"fieldname": "custom_derma_soap_plan", ...},
	],
	"Healthcare Practitioner": [
		{"fieldname": "custom_derma_default_assessment_mode", "fieldtype": "Select",
		 "options": "\nStructured\nSOAP", "label": "Default Derma Assessment Mode"},
	],
}

def ensure_derma_schema():
	for doctype, fields in DERMA_CUSTOM_FIELDS.items():
		if not _has_doctype(doctype):
			continue
		for spec in fields:
			if _has_field(doctype, spec["fieldname"]):
				continue
			_create_custom_field(doctype, {**spec, "module": "Do Derma"})
```

`Small Text` rather than `Text Editor`, matching the sibling clinical fields
(`custom_physical_examination`, `custom_symptoms_notes`) so notes stay plain text and print
predictably. `custom_derma_assessment_mode` is `read_only` on the form — it is stamped by code,
never typed.

`install.py` holds the single entry point, registered in `hooks.py`:

```python
def after_migrate():
	ensure_derma_schema()
	ensure_derma_settings_defaults()
```

The 12 existing patches are left untouched as a historical record.

### 2. `Derma Settings` singleton — `do_derma/do_derma/doctype/derma_settings/` *(new)*

```
Derma Settings (issingle: 1)
├── structured_assessment_fields  Table → Derma Structured Field  (child, new)
│     └── fieldname  Data   # a Patient Encounter fieldname
│     └── enabled    Check
├── enable_whatsapp_consent  Check  default 0
├── enable_lab_cases         Check  default 0
└── enable_billing_sync      Check  default 0
```

`ensure_derma_settings_defaults()` seeds `structured_assessment_fields` **only when empty**,
with the list `CONTEXT.md:41-44` names: `symptoms`, `custom_symptom_duration`,
`custom_symptoms_notes`, `diagnosis`, `custom_differential_diagnosis`, `custom_diagnosis_note`,
`custom_physical_examination`, `custom_other_examination`, `custom_illness_progression`. A
clinic that reorders or trims the list keeps its edit across migrates.

The three toggles default off. They govern controls that are currently visible and broken —
nothing else. Anesthesia is deliberately absent: that panel is already unreachable and gets no
toggle it would not honour.

### 3. Assessment module — `do_derma/assessment.py` *(new)*

`ASSESSMENT_TAB_FIELDNAME` and `_assessment_tab_layout()` are deleted from `api.py`.

```python
STRUCTURED = "Structured"
SOAP = "SOAP"
SOAP_FIELDS = ("custom_derma_soap_subjective", "custom_derma_soap_objective",
               "custom_derma_soap_assessment", "custom_derma_soap_plan")

def get_assessment_mode(encounter_doc):
	"""Stamped mode wins; else the practitioner default; else Structured."""
	stamped = encounter_doc.get("custom_derma_assessment_mode")
	if stamped:
		return stamped
	return _practitioner_default(encounter_doc.practitioner) or STRUCTURED

def get_structured_layout():
	"""Ordered docfields for the configured field list, silently dropping absent ones."""
	names = _configured_structured_fieldnames()
	meta = frappe.get_meta("Patient Encounter")
	return [_serialize_docfield(meta.get_field(n)) for n in names if meta.get_field(n)]
```

Stamping happens in `set_derma_assessment` on the **first save that writes any content**, not
on open — opening a chart must never mutate the encounter. Precedence, in order:

1. A mode already stamped on the encounter — always wins, even against a differing
   Practitioner Default. This is the property that makes reopening safe.
2. The practitioner's `custom_derma_default_assessment_mode`.
3. `Structured`.

Changing mode is a separate whitelisted call (`set_derma_assessment_mode`), allowed only while
`docstatus = 0`, behind a confirm dialog. **It writes no content and deletes nothing** — the
inactive format's columns are left exactly as they are, which is what makes the switch
reversible.

Because the two formats store separately, a SOAP-documented visit shows empty structured
fields and vice versa — indistinguishable from an undocumented visit, and an invitation to
re-document. The mode banner and the read-only rendering of the inactive format exist to make
an empty format read as *deliberately empty* rather than *missing*.

### 4. Assessment panel split — `chart/components/assessment/` *(new folder)*

Three files replacing the current 858-line `AssessmentPanel.vue`, each well under the 800-line
ceiling:

- `AssessmentPanel.vue` — shell. Mode banner, format toggle, `Annotate Consultation`, sticky
  save footer. Owns the dirty flag.
- `SoapNoteFields.vue` — four narrative inputs, S/O/A/P.
- `StructuredAssessmentFields.vue` — the configured structured inputs, still built through
  `frappe.ui.form.make_control` from the server layout, keeping the `custom_past_visit_*`
  read-only rule.

```
┌────────────────────────────────────────────────────────┐
│  Written as: SOAP Note                  [Change format]│
├────────────────────────────────────────────────────────┤
│  Subjective  ┌──────────────────────────────────────┐  │
│  Objective   │ …                                    │  │
│  Assessment  └──────────────────────────────────────┘  │
│  Plan                                                  │
│                                     [✎ Annotate        │
│                                        Consultation]   │
├────────────────────────────────────────────────────────┤
│  ● unsaved changes                          [ Save ]   │
└────────────────────────────────────────────────────────┘
```

### 5. Tab spine — `chart/DermaChart.vue`

```js
const SECTION_TABS = [
	{ key: "assessment",    label: __("Assessment") },
	{ key: "procedures",    label: __("Procedures") },
	{ key: "photos",        label: __("Photos") },
	{ key: "prescriptions", label: __("Prescription") },
	{ key: "consent",       label: __("Consent") },
	{ key: "review",        label: __("Review") },
]
```

`normalizeDermaSection` (`:1334`) gains aliases so a stored preference survives:
`clinical|encounter|chart|notes → assessment`, `procedure|procedures → procedures` (today
these map to `review`), `consents → consent`. **`review` must stop being the `v-else`
fallback** (`:181`) — it becomes an explicit branch, and the fallback becomes `assessment`,
so an unrecognised stored value lands on the first tab rather than the sign-off tab.

Contents move as follows:

| Tab | Gains | Loses |
|---|---|---|
| Assessment | `Annotate Consultation`, consultation annotation strip | — |
| Procedures | `ProcedurePanel`, per-row `Annotate (n)`, `New Procedure`, `Copy marks from last visit` | `Complete Session` footer |
| Photos | Before/After Compare (moved out of Review) | the duplicate Evidence panel |
| Prescription | unchanged | — |
| Consent | `Create` becomes primary | WhatsApp trio (gated) |
| Review | Timeline, Inventory Readiness, Follow-Up, read-only summary | Compare, ProcedurePanel |

Deleted outright: the right rail (`:545-599`), `DermaQuickActionsPanel.vue`, the section-bar
`Annotate`/`Upload Photo` toolbar (`:57-64`) whose jobs now belong to specific tabs, and the
`Previous Annotations` header `Annotate` (`:95`) which becomes the single
`Annotate Consultation`.

Smart Alerts move into `DermaEncounterHeader` as chips; clicking one still routes via
`handleEncounterAlert` (`:1617`), which needs its `setActiveSection("clinical")` updated to
`"assessment"` and its photo branch pointed at the new Photos tab.

### 6. Degraded-section reporting — `api.py`

`_safe_derma_context(label, fallback, getter)` currently swallows the exception and returns the
fallback. It gains a per-request accumulator so the payload can say what broke:

```python
def _safe_derma_context(label, fallback, getter, errors=None):
	try:
		return getter()
	except Exception:
		frappe.log_error(title=f"Derma chart context: {label}")
		if errors is not None:
			errors.append(label)
		return fallback
```

`get_patient_derma_chart` (`api.py:1525`) threads one `errors` list through every section and
returns it as `context_errors`. **No error text reaches the client** — only the section label,
so a broken query cannot leak a SQL fragment or a patient identifier into the browser.

The frontend renders a section's normal empty state when it loaded fine and is empty, and
`⚠ Couldn't load — [Retry]` when its label appears in `context_errors`. Retry re-runs the
existing loader for that section only. All eight `Refresh` buttons are removed; the two
full-page `Retry` buttons for a total load failure (`:20`, `:26`) stay.

### 7. Annotation anchoring — `annotation/DermaAnnotationStudio.jsx`, `ProcedurePanel.vue`

`openDermaAnnotationStudio` gains three options and stops assuming the encounter:

```js
openDermaAnnotationStudio({
	context: { patient, encounter, appointment, clinicalProcedure },  // new field
	annotationName,   // new — resume an existing Health Annotation
	marks,            // new — rehydrate existing Derma Chart Marks onto the canvas
	bodyTemplates, procedureTemplates, onSaved,
})
```

`save()` (`DermaAnnotationStudio.jsx:390-411`) stops hardcoding and sends the real anchor:

```js
doctype: context.clinicalProcedure ? "Clinical Procedure" : "Patient Encounter",
docname: context.clinicalProcedure || context.encounter,
clinical_procedure: context.clinicalProcedure || null,
annotation_name: annotationName || null,     // update in place when resuming
```

The server already handles all of this — the branch at `api.py:2005`, the update path at
`api.py:1837-1852`, and `_link_procedure_annotation` (`:2071`). Only the plumbing is missing.

The studio header states the anchor in words — *"Consultation — MARWA J. S. ALI BAR"* or
*"Procedure — Laser, Face"* — so the anchor is never invisible at save time.

Two entry points, per the decision:

- Assessment tab: `Annotate Consultation` → no `clinicalProcedure`, resumes the encounter's
  latest `Derma Annotation` if one exists.
- Procedures tab, per row: `Annotate (n)` → `clinicalProcedure: row.name`, resumes that
  procedure's latest annotation. The count comes from
  `_get_annotation_counts_for_procedures` (`api.py:937`), which starts returning non-zero
  values only once this phase lands.

**Idempotency contract to preserve** (`_sync_chart_marks_for_annotation`, `api.py:1889`): marks
are matched to Excalidraw elements by `annotation_json.element_id`; re-saving updates in place;
marks already promoted to a `Clinical Procedure` are never auto-deleted (`:1972-1976`); marks
stamped in real time by `onMarkPlaced` are only re-linked. Passing a real `clinical_procedure`
changes `base_payload` (`:1943-1949`) — the deletion guard must still spare promoted marks, and
the tests must prove it.

### 8. Orphan triage

Revived, each with a real entry point on the Procedures tab:

- **`Copy marks from last visit`** → `carry_forward_marks` (`api.py:2840`). High value for a
  repeat-visit derma clinic; the endpoint already clears procedure/finding/treatment/annotation
  links and defaults status to `Monitoring`.
- **`New Procedure`** → `createProcedure` (`:1947`) / `create_derma_chart_procedure`
  (`api.py:1614`). Today the *only* way to create a procedure is to draw a mark.

Deleted: the remaining ~20 handlers and all associated dead state listed in Current State,
including every inline-Excalidraw remnant (`chartMode`, `chartExpanded`, `excalidrawRef`,
`saveAnnotation`, `loadAnnotation`, `toggleChartExpanded`, `setChartOverlayMode`) and
`copySummaryToAssessment` with its fuzzy-regex field targeting.

`selectInventoryMark` and `selectFollowupMark` collapse into one `selectMarkFromItem(item)`.

### 9. Feature toggles

`get_patient_derma_chart` returns a `settings` block with the three booleans. `ConsentPanel`
hides the WhatsApp trio unless `enable_whatsapp_consent`; `ProcedurePanel` hides the three
lab/surface buttons unless `enable_lab_cases` and the `Sync Billables` footer unless
`enable_billing_sync`. The handlers stay in place behind the gate.

### What stays unchanged

`api.py`'s helper set and its 39 existing endpoints (beyond the assessment and annotation
changes named above), every doctype in `do_derma/do_derma/doctype/` except the new singleton,
`EmbeddedExcalidraw.jsx`, the React-overlay mounting model, both desk pages and their
`*.bundle.js` filenames — so the `frappe.require` contract is untouched — `derma_sidebar.js`,
`do_derma.openChart()`, and every existing patch in `patches.txt`.

## Security

This feature touches patient data and adds whitelisted endpoints, so both controls are stated
with the test that proves them.

- **Authorization.** `set_derma_assessment_mode` and any other new `@frappe.whitelist()`
  function calls `_ensure_clinical_access()` as its first statement, before reading a single
  argument. That role check against `CLINICAL_ACCESS_ROLES` *is* the authorization boundary
  for `api.py`, because many writes below it use `ignore_permissions=True` — DocPerms are
  inconsistent across the three apps (`Health Annotation` grants only System Manager).
  Proven by `TestClinicalAccessGate` in `do_derma/tests/test_api.py`, extended with the new
  endpoint names.

- **Write whitelisting.** `set_derma_assessment` continues to accept only fieldnames present
  in the server-side layout, and on a submitted encounter only those with `allow_on_submit`
  (`api.py:2126`). The SOAP fields join that whitelist through `assessment.py`; a client cannot
  name an arbitrary `Patient Encounter` column. `set_derma_assessment_mode` writes exactly one
  field and refuses when `docstatus != 0`.

- **No error detail crosses the boundary.** `context_errors` carries section *labels* only
  (`"procedures"`, `"annotations"`). Exception text keeps going to `frappe.log_error` on the
  server, so a failing query cannot leak SQL or patient identifiers into the browser.
  Proven by a test asserting the payload contains the label and no exception string.

- **Schema writes are server-only.** `ensure_derma_schema()` runs from `after_migrate`, never
  from a whitelisted path, so no request can create or alter a Custom Field.

## Acceptance Criteria

**Assessment**

1. On a site where `custom_assessment` does not exist, opening the Assessment tab renders the
   configured structured fields — not "No fields found".
2. A new encounter opens in the practitioner's `custom_derma_default_assessment_mode`, or
   `Structured` when unset.
3. Writing and saving a SOAP note stamps `custom_derma_assessment_mode = "SOAP"`.
4. Reopening that encounter shows SOAP **even if** the practitioner's default is Structured.
5. Switching format after content exists requires a confirm, and switching back shows the
   original content intact.
6. Opening a chart and navigating away without typing does **not** stamp a mode.
7. A submitted encounter renders the assessment read-only and saves only `allow_on_submit`
   fields.
8. A structured fieldname configured in `Derma Settings` but absent from the site is skipped
   silently — the rest of the form still renders.

**Decluttering**

9. No action appears in two places: exactly one `Complete Encounter`, one photo-upload entry
   per tab that needs it, one annotation entry per anchor.
10. Zero `Refresh` buttons on the page.
11. Nothing visible on the page is a no-op — with all three toggles off, the WhatsApp trio,
    the three lab/surface buttons and `Sync Billables` do not render.
12. Turning `enable_lab_cases` on makes those buttons reappear without a code change.
13. A returning user whose stored section is `clinical` lands on `Assessment`, not on a blank
    tab; an unrecognised stored value also lands on `Assessment`.

**Annotation**

14. `Annotate Consultation` writes a `Health Annotation` onto `Patient Encounter.custom_annotations`.
15. A procedure row's `Annotate` writes onto that `Clinical Procedure.custom_annotations`, and
    the row's count increments from 0 to 1.
16. Reopening either resumes the existing drawing with its marks on the canvas — it does not
    create a second `Health Annotation`.
17. A mark already promoted to a `Clinical Procedure` is not deleted by re-saving the
    annotation it belongs to.

**Degraded and empty paths**

18. When a chart section's query fails, that section shows `Couldn't load — Retry` and every
    other section still renders normally.
19. `Retry` on a degraded section reloads that section alone.
20. A patient with no prior visits shows the Review tab's empty states, not errors.
21. `context_errors` never contains exception text.

**No regression**

22. `bench --site dermaone.localhost migrate` is safe to run twice; the second run creates
    nothing and changes no clinic-set value.
23. Every existing endpoint keeps its current signature and response shape except
    `get_derma_assessment` / `set_derma_assessment` / `save_derma_annotation`, whose additions
    are optional arguments.
24. The full e2e suite passes against a rebuilt bundle.

## Phases

Tracer bullets — each is a vertical slice through every layer, independently shippable.

**Phase 0 — See it before building it.** This spec, plus a self-contained local HTML mockup at
`docs/mockups/derma-chart-revamp.html` showing before/after for all six tabs.
*Exit: the mockup opens locally and the layout is signed off before any code changes.*

**Phase 1 — Assessment tab end-to-end.** ✅ *Shipped 2026-08-09.* `schema.py`, `install.py`, the `after_migrate` hook,
`Derma Settings` + its child doctype, `assessment.py`, the panel split, the mode toggle,
the Practitioner Default field.
*Exit: on a site where the Clinical Notes tab previously showed nothing, a practitioner writes
a SOAP note, reloads, and it reopens in SOAP.*

**Phase 2 — Tab spine.** ✅ *Shipped 2026-08-09.* Six tabs, right rail deleted,
`DermaQuickActionsPanel` removed, Compare moved to Photos, one `Complete Encounter`,
degraded-section reporting replacing all eight `Refresh` buttons, section-preference aliases and
the `hydrate` fix.
*Exit: no duplicated action remains on any screen and the page is full width.* — met; proven by
`tab-spine.spec.ts` and the four screenshots named in Verification.

**Phase 3 — Annotation anchoring.** Studio accepts `clinicalProcedure` / `annotationName` /
`marks`; per-row `Annotate (n)` on Procedures; `Annotate Consultation` on Assessment; anchor
named in the studio header.
*Exit: an annotation drawn on a procedure appears on that `Clinical Procedure`, its row count
reads 1, and reopening resumes the drawing.*

**Phase 4 — Orphan triage.** `Copy marks from last visit` and `New Procedure` get real
buttons; the remaining ~20 orphans and their dead state are deleted.
*Exit: `DermaChart.vue` is materially smaller and every remaining handler is reachable from
the UI.*

**Phase 5 — Feature toggles.** The three `Derma Settings` booleans gate the WhatsApp, lab and
billing controls.
*Exit: nothing renders that does not work.*

## Open Questions

- **SOAP notes will print blank.** Both `Patient Encounter` print formats on this site are
  hand-written HTML (`print_format_builder: 0`) that render fields by name; the site default is
  `Encounter print (Dr Sadiq)`. New fields are invisible to them.
  *Default:* printing is deferred by decision, so **the pilot must not print SOAP-documented
  encounters** until both formats gain a block keyed off `custom_derma_assessment_mode`. This
  is the first item of follow-up work, not an optional polish.

- **Does the clinic want anesthesia recorded at all?** `AnesthesiaPanel.vue` is 268 written
  lines against stub endpoints and a `Dental Anesthesia` child table.
  *Default:* leave it unimported and unreferenced. Do not give it a toggle that would render a
  panel whose saves silently do nothing.

- **Should `Review` be able to reopen a completed encounter?** Today `completeSession` submits
  the encounter and the chart becomes read-only with no route back.
  *Default:* no reopen path in this work; a practitioner uses the desk form.

- **How many annotations per anchor?** Phase 3 resumes *the latest* annotation for an anchor.
  *Default:* one live annotation per anchor per visit; older ones remain readable in the
  history strip but are not resumed.

- **Do any of the 25 existing body templates need images copied to this bench?** All 25 have
  `File` records but the blobs 404 locally.
  *Default:* a local-environment gap, not an app gap; copy them into
  `sites/dermaone.localhost/private/files/` for manual verification. The app-level fix — a
  labelled placeholder instead of a broken-image icon — rides along in Phase 3.

## Reconciliation — what changed vs the plan

Phase 1 only. Four deviations, each forced or better:

- **`api.py` shrank instead of gaining a wrapper layer.** The plan said `api.py` would keep
  the layout code and gain thin delegates. On reading the usages, `ASSESSMENT_TAB_FIELDNAME`,
  `_assessment_tab_layout`, `_child_table_layout`, `_serialize_assessment_values`,
  `NO_VALUE_FIELD_TYPES` and `TABLE_FIELD_TYPES` turned out to be used **only** by the two
  assessment endpoints, so all six moved wholesale into `assessment.py`. `CHILD_INTERNAL_FIELDS`
  is the one genuinely shared constant; it now lives in `assessment.py` and `api.py` imports it,
  keeping one owner and no import cycle. Net: `api.py` is 90 lines shorter.

- **`Derma Settings` needed a second doctype.** The plan named one singleton; a Table field
  needs a child doctype, so `Derma Structured Field` (`fieldname` + `enabled`) was added.

- **The three feature toggles shipped in Phase 1, unused.** They belong to Phase 5, but they
  are fields on a doctype Phase 1 creates, and adding them later means a second schema change
  to the same file. They are created and default to off; nothing reads them yet.

- **`copySummaryToAssessment` and `assessmentSummaryField` were deleted early.** They are
  Phase 4 orphans, but `copySummaryToAssessment` called `saveAssessment` with the old
  single-argument shape. Rather than leave a latent break behind a changed signature, both went
  now. `visitSummary` and `summarySaving` remain unused until Phase 4 clears them.

Not deviations, but worth recording: the Assessment tab is still keyed `clinical` and still
labelled *Clinical Notes* with a *SOAP* hint. Renaming it is Phase 2, which also owns the
`data-test` rename. The right rail, the four duplicate `Annotate` buttons and the eight
`Refresh` buttons are all still on screen — every one of them is Phase 2 or later.

### Phase 2 — six deviations

- **The template no longer carries a fallback branch; `normalizeDermaSection` does.** The plan
  said `review` stops being the `v-else` and the fallback becomes `assessment`. As built, the
  review branch is an explicit `v-else-if` and there is **no `v-else` at all**
  (`DermaChart.vue:326`). `activeSection` is only ever written through `normalizeDermaSection`
  — both at the ref initializer (`:678`) and in `setActiveSection` (`:1381`) — so the
  normalizer is the single owner of the "which tab" invariant and the template does not get a
  second, silently-diverging copy of it. Acceptance criterion 13 still holds, and the e2e test
  proves it end to end rather than by inspection.

- **"Retry reloads that section alone" is only true for the three panel tabs.** Prescription,
  Consent and Assessment each have their own loader. Every other section — procedures, photos,
  timeline, inventory, follow-ups — is a slice of the *one* `get_patient_derma_chart` payload,
  so its retry is `refresh()`. Building per-section endpoints to make the criterion literally
  true would have added five whitelisted endpoints for a path that fires only when a query is
  already broken. Acceptance criterion 19 is met in effect (the section reloads) but not in
  isolation, and that is the honest reading.

- **Four rendered `Refresh` buttons came out, not eight.** The spec's count of eight included
  the two full-page `Retry` buttons (which stay by design) and `AssessmentPanel:5`, already
  removed in Phase 1. `AnesthesiaPanel.vue` keeps its Refresh because the file is explicitly
  untouched and unimported — nothing it contains reaches the page. The e2e assertion is scoped
  to the chart root, because **the `Refresh` still visible beside the page belongs to
  do_health's sidebar** (`.do-health-section__refresh`), which this app does not own.

- **`Complete Encounter` gained a `completing` prop.** Removing `Complete Session` would
  otherwise have dropped the in-flight disabled state that the ProcedurePanel button had and
  the header button did not. Consolidating to one rule — `!hasSessionContext || completing` —
  is what the Current State section said the duplicate pair got wrong.

- **`selectInventoryMark` / `selectFollowupMark` now route to Photos, not Review.** They select
  a chart mark to feed the Compare panel's "Clinical Response" control, and Compare moved to
  Photos. Leaving them pointed at Review would have reproduced the exact defect the spec
  recorded for the rail's `Follow-up` button: navigation to a tab that no longer holds the
  thing being navigated to. They are still two functions; collapsing them into
  `selectMarkFromItem` stays Phase 4.

- **`DermaEvidencePanel` lost its own `Upload` button.** With the panel mounted once, under a
  Photos header that already carries `Upload Photo`, its button was the last surviving duplicate
  of the six the spec counted. Two upload controls remain on the Photos tab and they are not
  duplicates: `Upload Photo` saves a new photo, `Upload Today` pulls today's photo into the
  Before/After comparison. The e2e test asserts that exact pair, so a third one fails.

- **One CSS fix rode along.** `.chart-annotation-history > .panel-muted` had no padding, so at
  full width its empty-state text escaped the card's bottom border. Visible in the Phase 2
  screenshots; fixed with a three-line rule.

Not deviations, worth recording: the `Annotate Consultation` button on the Assessment tab is
**a label change only** — it still calls the zero-argument `openAnnotationStudio` and still
anchors to the encounter. Real anchoring is Phase 3. The `Sync Billables` footer, the WhatsApp
trio and the three lab/surface buttons are all still rendered; gating them is Phase 5. The ~25
orphaned handlers and their dead state are still present (Phase 4) — their
`setActiveSection("review")` targets were repointed at `"procedures"` so they do not encode a
stale tab map, but they remain unreachable from the UI.

One Current State claim needs correcting: the prior spec recorded
`Custom Field where module = "Do Derma"` as returning `[]`. On this site it now returns 21 rows
(15 pre-existing on `Clinical Procedure Template`, plus the 6 this phase created). The blocker
the prior spec described was real but is no longer the current state of the site.

## Verification

### Phase 1 — run 2026-08-09, all green

| Command | Result |
|---|---|
| `bench --site dermaone.localhost migrate` | Clean. `after_migrate` created 6 custom fields. |
| `bench --site dermaone.localhost migrate` (2nd run) | Clean, still 21 `Do Derma` custom fields — idempotent. |
| `run-tests --module do_derma.tests.test_schema` | **4 passed** |
| `run-tests --module do_derma.tests.test_assessment` | **14 passed** |
| `run-tests --module do_derma.tests.test_api` | **5 passed** — no regression |
| `ruff check` (new + changed modules) | All checks passed |
| `ruff format` | Applied to `api.py`, `assessment.py`; tests already clean |
| `bench build --app do_derma` | Clean, 555 ms |
| `yarn test:e2e` | **8 passed** (5 pre-existing + 3 new) |

Manual, against real data on `dermaone.localhost` (rolled back afterwards): a draft encounter
opened `Structured` and unstamped, returned the 9 configured structured fields where the tab
previously returned none, accepted a SOAP subjective, stamped `SOAP`, and after switching to
`Structured` still held the SOAP text. Screenshots of both modes were captured from the running
desk page.

**Not yet run:** nothing for Phase 1. Phases 2–5 are unimplemented, and printing is deferred —
a SOAP-documented visit still prints blank (see Open Questions).

### Phase 2 — run 2026-08-09, all green

| Command | Result |
|---|---|
| `run-tests --module do_derma.tests.test_api` | **8 passed** (5 pre-existing + 3 new `TestChartContextErrors`) |
| `run-tests --module do_derma.tests.test_schema` | **4 passed** — no regression |
| `run-tests --module do_derma.tests.test_assessment` | **14 passed** — no regression |
| `bench --site dermaone.localhost migrate` | Clean, `after_migrate` ran |
| `bench build --app do_derma` | Clean, 529 ms |
| `yarn test:e2e` | **15 passed** (8 pre-existing + 7 new `tab-spine.spec.ts`) |
| `ruff check` / `ruff format --check` | Unchanged from the pre-Phase-2 baseline — see note |

The ruff note: this bench has no `ruff` on `PATH` and none in `env/bin`, so the run used
`pipx run ruff`, a newer release than the project pins. It reports one `RUF005` in `api.py:1298`
and would reformat `api.py` and `tests/test_api.py`. **All of it is pre-existing** — the same
output was reproduced from a clean `git stash` of this branch. Phase 2 adds no new finding.

Manual, against seeded data on `dermaone.localhost`: screenshots captured at 1500×1000 for
Assessment, Procedures, Photos and Review. All four render full width with no right rail, six
tabs in visit order, and a single `Complete Encounter` in the header. The first pass exposed the
annotation-history padding bug, which was fixed and re-shot.

**Not yet run for Phase 2:** nothing. Still outstanding across the feature — Phases 3–5, and
printing (a SOAP-documented visit prints blank; see Open Questions).

### Commands

```bash
# bench root — /Users/hameed/Developer/bench-v16
bench --site dermaone.localhost migrate
bench --site dermaone.localhost run-tests --module do_derma.tests.test_schema
bench --site dermaone.localhost run-tests --module do_derma.tests.test_assessment
bench --site dermaone.localhost run-tests --module do_derma.tests.test_api
ruff check apps/do_derma && ruff format --check apps/do_derma
bench build --app do_derma

# app root — apps/do_derma
bench --site dermaone.localhost execute do_derma.e2e_seed.setup_e2e_data
yarn test:e2e
```

Test modules and what they assert (✅ = written and passing):

| Test | Asserts |
|---|---|
| ✅ `test_creates_missing_custom_fields` | Fields appear on a site lacking them |
| ✅ `test_second_run_is_noop` | Re-running creates nothing and changes nothing |
| ✅ `test_never_overwrites_an_existing_field` | A clinic-renamed label survives migrate |
| ✅ `test_survives_a_missing_doctype` | An absent doctype does not abort the migrate |
| ✅ `test_layout_comes_from_settings_in_order` | Structured layout matches the configured list, in order |
| ✅ `test_layout_skips_absent_fields` | A missing field is dropped, not fatal |
| ✅ `test_disabled_rows_are_dropped` | An unchecked row is excluded |
| ✅ `test_mode_stamped_on_first_content_save` | `custom_derma_assessment_mode` set on first save |
| ✅ `test_empty_save_does_not_stamp` | Whitespace-only content stamps nothing |
| ✅ `test_open_does_not_stamp` | Reading the chart mutates nothing |
| ✅ `test_stamped_mode_beats_practitioner_default` | Reopen honours the stamp |
| ✅ `test_practitioner_default_applies_to_a_new_encounter` | Default drives an unstamped visit |
| ✅ `test_switch_preserves_the_other_format` | Round-trip switch loses no content |
| ✅ `test_switch_refused_on_submitted_encounter` | `docstatus != 0` is rejected |
| ✅ `test_unknown_mode_is_rejected` | An arbitrary mode string throws |
| ✅ `test_write_is_whitelisted_to_the_active_mode` | A SOAP save cannot write `status` |
| ✅ `TestAssessmentAccessGate` | `get_derma_assessment` / `set_derma_assessment_mode` gated |
| ✅ e2e `assessment-modes.spec.ts` | Fields render; SOAP survives reload; switch preserves content |
| ✅ `test_healthy_chart_reports_no_degraded_sections` | `context_errors` is empty on a healthy chart |
| ✅ `test_context_errors_carries_labels_only` | The label is returned; no exception text in the payload |
| ✅ `test_one_broken_section_leaves_the_others_intact` | One failed query degrades one section only |
| ✅ e2e `tab-spine.spec.ts` | Six tabs, no rail; zero Refresh; one Complete + one annotate entry; upload only on Photos; degraded notice + Retry; `clinical` and an unknown value both land on Assessment |
| `test_annotation_anchors_to_procedure` | Child row lands on `Clinical Procedure` — Phase 3 |
| `test_resume_updates_in_place` | Re-save with `annotation_name` creates no second record — Phase 3 |
| `test_promoted_mark_survives_resave` | The `api.py:1972` deletion guard still holds — Phase 3 |

**Not yet run** — nothing; implementation has not started.

### The `data-test` contract

33 `data-test` attributes across the Vue components are the e2e selector contract. This revamp
renames or removes many of them — `section-tab-clinical` becomes `section-tab-assessment`,
everything in the rail disappears, and the assessment panel's hooks move into the new
subfolder. `e2e/{tests,pages}` must be updated **in the same phase** that changes the markup,
and the bundle rebuilt before running specs, or they select on stale hooks and fail
misleadingly. Never wait on `networkidle`; wait on a `data-test` element as `ChartPage.open()`
does. Specs must keep setting the section explicitly via `ChartPage.setSection()`.

## Phase 2 (future, not in this spec)

- Print formats for both encounter templates, keyed off the stamped mode. **First item.**
- Wiring `AnesthesiaPanel` and implementing its two endpoints, or deleting it.
- WhatsApp consent sending; billing sync.
- Reviving the dead element-tagged fan-out branch of `_sync_chart_marks_for_annotation`.
- The dental-to-derma structural cleanup (`Dental Anesthesia`, `Dental Note Template`,
  `rowAllowsSurfaces`).
- Migrating the 5,434 procedure-anchored annotations into the derma chart's history view.
- Why the do_health annotation workflow stopped in April 2026.

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/schema.py` | *(new)* Declarative custom-field spec, `ensure_derma_schema()` |
| `do_derma/install.py` | *(new)* `after_migrate()` entry point |
| `do_derma/assessment.py` | *(new)* Mode resolution/stamping, structured layout, SOAP serialisation |
| `do_derma/do_derma/doctype/derma_settings/` | *(new)* Singleton — field list + 3 toggles |
| `do_derma/do_derma/doctype/derma_structured_field/` | *(new)* Child table of fieldnames |
| `do_derma/hooks.py` | Register `after_migrate` |
| `do_derma/api.py` | Delegate assessment to `assessment.py`; drop `ASSESSMENT_TAB_FIELDNAME`; `save_derma_annotation` accepts `annotation_name`; `_safe_derma_context` reports `context_errors`; return `settings` |
| `chart/components/assessment/AssessmentPanel.vue` | *(new)* Shell — banner, toggle, save footer |
| `chart/components/assessment/SoapNoteFields.vue` | *(new)* Four narrative inputs |
| `chart/components/assessment/StructuredAssessmentFields.vue` | *(new)* Configured structured inputs |
| `chart/components/AssessmentPanel.vue` | Deleted — replaced by the folder above |
| `chart/components/DermaQuickActionsPanel.vue` | Deleted |
| `chart/components/DegradedSectionNotice.vue` | *(new)* `⚠ Couldn't load … [Retry]` for one section |
| `chart/components/PrescriptionPanel.vue` | Drop the `Refresh` button and its emit |
| `chart/derma_chart.bundle.css` | Alert chips, section stacks, degraded notice, annotation-history padding |
| `e2e/tests/tab-spine.spec.ts` | *(new)* The decluttering contract |
| `chart/DermaChart.vue` | Six tabs; delete rail `:545-599`; delete ~25 orphans + dead state; degraded retry; section aliases; `hydrate` fix |
| `chart/components/ProcedurePanel.vue` | Per-row `Annotate (n)`; `New Procedure`; `Copy marks from last visit`; drop `Complete Session`; gate lab + billing controls |
| `chart/components/DermaEncounterHeader.vue` | Smart Alert chips; drop Refresh; wrap name + tooltip |
| `chart/components/ConsentPanel.vue` | Gate WhatsApp trio; `Create` primary; validate on submit not mount |
| `chart/components/DermaEvidencePanel.vue` | Single mount, Photos tab; drop its duplicate `Upload` |
| `chart/annotation/DermaAnnotationStudio.jsx` | Accept `clinicalProcedure` / `annotationName` / `marks`; send the real anchor; name it in the header |
| `do_derma/tests/test_schema.py` | *(new)* |
| `do_derma/tests/test_assessment.py` | *(new)* |
| `do_derma/tests/test_api.py` | Extend `TestClinicalAccessGate`; annotation anchoring tests |
| `e2e/{tests,pages}` | Update the `data-test` selector contract |
| `docs/mockups/derma-chart-revamp.html` | *(new)* Before/after mockup, Phase 0 |
