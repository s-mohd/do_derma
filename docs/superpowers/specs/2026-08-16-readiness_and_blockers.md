# Readiness With One Owner, Enforced By The Server

Date: 2026-08-16
Status: **Draft**

## Goal

When a session cannot safely be completed, the server says so — and says the same thing the chart
says. Today the gate exists **only in the browser**: `completeSession()` checks blockers and
returns, and the endpoint it would have called submits the encounter after checking a role and
nothing else. Any direct `frappe.call` completes a blocked session. Meanwhile three separate
engines compute readiness with rules that disagree about the same clinical fact, and a fourth
aggregator in the browser quietly drops any blocker that has a ToDo attached.

## Decisions

- **One `do_derma/readiness/` package with a single `get_session_readiness()`** → one owner for
  state that currently drifts across three engines and a client aggregator. Trade-off: a package
  move touching ~250 lines. Rejected: an aggregator inside `api.py` (grows a file already at its
  sanctioned 3.5k limit) and closing only the bypass hole (leaves the engines disagreeing).
- **Enforcement is configurable in Derma Settings: warn or block** → clinics differ, and a hard
  gate with no escape hatch gets worked around by never completing sessions. A blocked completion
  proceeds only with a recorded override reason.
- **The override is one reason for the whole session, available to any clinical role**
  (companion screen 5, Q2) → same authorization boundary as every other endpoint here, and the
  comment records exactly which blockers were live. Rejected: a reason per blocker (friction at
  the end of a clinic day) and administrator-only (a practitioner working alone cannot close
  their own encounter, so it stays in draft forever).
- **The reason is recorded on the encounter** as `custom_derma_completion_override_reason`, plus
  an automatic Comment naming the user and the overridden blockers → travels with the encounter,
  visible on the form, printable. Rejected: a dedicated audit doctype (more machinery than this
  needs today) and a bare Comment (unqueryable).
- **The product-tracking flag is the only trigger for lot-number blocking** (companion screen 5,
  Q1) → behaviour stops depending on whether a clinic named a category "Botox". A migration sets
  `custom_derma_product_tracking_required` on every template the hard-coded category set was
  silently covering, so nothing loosens. Rejected: the union of both rules (keeps a hard-coded
  category list alive as a second owner) and category-only (fails for clinic-named categories).
- **Whether an open ToDo downgrades a follow-up blocker is a Derma Settings switch**
  (companion screen 5, Q3), **defaulting to on** → that is today's real behaviour, so no site's
  completions get stricter on upgrade. Rejected: hard-coding either answer.

## Current State (verified)

Verified against `d782a8a`, working tree clean. Every doctype here is **healthcare**
(`Patient Encounter`, `Clinical Procedure`, `Clinical Procedure Template`) or **do_derma**
(`Derma Chart Mark`, `Derma Settings`); `Bin` and `ToDo` are **frappe/erpnext**.

### Three engines

**Inventory** — `_build_inventory_readiness` (`api.py:1357-1461`), exposed by
`get_inventory_readiness` (`api.py:1345-1354`, gated at `:1349`). Tracking is forced when the
category is in the hard-coded set `{"Botox", "Filler"}` (`:1379-1382`), *in addition* to the
template's `custom_derma_product_tracking_required` flag. Rows group on
`product_item|lot_no|expiry_date|dose_unit` (`:1405`). Six blocking rules (`:1429-1456`): missing
product, missing/zero dose, missing lot, missing expiry, expired (`_is_expired`, `:1490-1496`),
and `available_qty < dose` where availability is `sum(actual_qty)` from `tabBin`
(`_stock_available_qty`, `:1480-1487`). One non-blocking warning: item present, no Bin row.
Status trichotomy at `:1457`, severity at `:1458`.

**Follow-up** — `get_followup_intelligence` (`api.py:3371-3482`, gated at `:3374`). Four
hard-coded rules: status follow-up on `{"Monitoring","Worse","Biopsied","Excised"}` with due-day
map `{"Worse":7,"Biopsied":3,"Excised":14,"Monitoring":30}` (`:3414-3429`, blocking for
`{"Worse","Biopsied"}` at `:3427`); missing before/after photo (`:3431-3443`, blocking);
missing product or lot when the template flag is set (`:3445-3459`, blocking); next-session
interval on `{"Botox","Filler","Laser"}` with map `{90,180,28}` (`:3461-3474`, non-blocking).

**Procedure gate** — `_validate_marks_ready_for_procedure` (`api.py:2911-2937`), a hard
`frappe.throw` called from `create_procedure_from_mark` (`api.py:2823`) — a **different
transition** from session completion. It checks required template variables via
`_mark_variable_value` (`api.py:2940-2955`), product/lot when the flag is set, and photo evidence.
It checks neither expiry, dose, nor stock.

**They disagree.** Inventory blocks on a missing lot when the *category is named* Botox or Filler;
follow-up blocks on a missing lot only when the *template flag* is set. Same fact, two triggers.

### The gate is client-side only

`complete_derma_session` (`api.py:2686-2734`) calls `_ensure_clinical_access()` at `:2694`,
resolves context, submits draft Clinical Procedures via `_complete_derma_procedures_for_session`
(`:2658-2682`), calls the `sync_derma_billables` stub (`:2628-2655`), attempts invoicing inside a
bare `except Exception` that only logs (`:2718-2719`), and submits the encounter at `:2721-2725`.
**It calls none of the three engines.**

The only gate is `DermaChart.vue:2131-2135`:

```js
const blockers = sessionBlockers()
if (blockers.length) { showBlockers(blockers); return }
```

`sessionBlockers()` (`:2082-2090`) concatenates `inventoryBlockers` (`:786`) and
`followupBlockers` (`:785`) — and `followupBlockers` filters `item.blocking && !item.todo`. **That
`!item.todo` rule has no server counterpart**: creating a ToDo silently clears the blocker, in the
UI only. `showBlockers` (`:2092-2102`) shows only the first six.

`encounterAlertItems` (`:818-863`) is a separate advisory engine (allergy, consent, photo, plus the
first two of each blocker list). Nothing gates on it.

### Derma Settings today

`derma_settings.json` is `issingle: 1` with six fields: a Structured Assessment section with the
`structured_assessment_fields` child table, and three feature-toggle checks
(`enable_whatsapp_consent`, `enable_lab_cases`, `enable_billing_sync`). `do_derma/settings.py` is
its single owner — `get_settings_doc()` (`:18-26`) returns `None` if the doctype is absent or
unreadable, and `get_feature_toggles()` (`:29-34`) defaults **every toggle off** in that case, a
contract pinned by `test_settings.py:53`. `ensure_derma_settings_defaults()`
(`assessment.py:259-269`) seeds the child table only when empty and is called from
`install.after_migrate` (`install.py:14`).

**Every readiness threshold is a literal in `api.py`, not a setting.**

### Tests

`TestCompleteDermaSession` (`test_api.py:632-650`) has two tests, both about `docstatus`, with no
blocker set up or asserted. **No test module exercises any of the three engines.**

## Non-Goals

- **The hard-coded thresholds do not move into settings in this spec** — the due-day map
  (`api.py:3415`), the interval map (`:3462`) and the stock rules stay literals. They are named
  here as a later pass so this spec stays finishable.
- **No change to `create_procedure_from_mark`'s behaviour.** `_validate_marks_ready_for_procedure`
  moves house and keeps throwing at the same moment with the same message.
- **No change to the billing stub or the invoicing try/except** in `complete_derma_session`.
- **No change to `encounterAlertItems`** — the advisory strip stays a client concern.
- **No new readiness rules.** This spec reconciles and relocates the rules that exist.
- **No change to `_ensure_clinical_access` or `CLINICAL_ACCESS_ROLES`.**
- **`e2e_seed.py` is untouched.**

## Design

Move the engines into one package, let the server decide, make the decision configurable.

### 1. The package — `do_derma/readiness/`

```
do_derma/readiness/
  __init__.py        # get_session_readiness only — no lazy re-exports
  inventory.py       # from api.py:1357-1496
  followup.py        # from api.py:3371-3500
  procedure.py       # from api.py:2911-2955
  session.py         # get_session_readiness: the one owner
```

`api.py`'s whitelisted wrappers stay where they are and become thin — they keep their
`_ensure_clinical_access()` calls and their response shapes, so no client changes on that path.
This **shrinks `api.py`** by roughly 250 lines rather than growing it.

```python
def get_session_readiness(patient: str, appointment: str | None, encounter: str | None) -> dict:
	"""Every readiness item for one session, from one place."""
	marks = _get_marks(patient, appointment, encounter)
	templates = _templates_for_marks(marks)
	items = [*inventory.build(marks, templates), *followup.build(marks, templates)]
	if get_readiness_settings().todo_downgrades_blockers:
		items = [_downgrade_if_todo(item) for item in items]
	return {
		"items": items,
		"blockers": [item for item in items if item["blocking"]],
		"enforcement": get_readiness_settings().enforcement,
	}
```

`_downgrade_if_todo` makes today's hidden client rule explicit and server-side: an item with an
open ToDo becomes `blocking: False, severity: "medium"` and keeps a `downgraded_by_todo` marker so
the UI can say why.

### 2. Reconciling the lot rule

`inventory.build` drops the hard-coded `{"Botox", "Filler"}` category set (`api.py:1379-1382`) and
consults only `custom_derma_product_tracking_required`. A migration patch sets that flag on every
`Clinical Procedure Template` whose `custom_derma_category` is in the retiring set, so no clinic
loses a rule it currently has:

```python
def execute():
	if not _has_field("Clinical Procedure Template", "custom_derma_product_tracking_required"):
		return
	for name in frappe.get_all("Clinical Procedure Template",
		filters={"custom_derma_category": ["in", ("Botox", "Filler")], "custom_derma_product_tracking_required": 0},
		pluck="name"):
		frappe.db.set_value("Clinical Procedure Template", name, "custom_derma_product_tracking_required", 1)
```

Idempotent: the filter excludes already-set rows, so a re-run writes nothing.

### 3. Derma Settings gains two fields

Added by patch to the existing single doctype, in a new "Session Completion" section:

| fieldname | fieldtype | default | meaning |
|---|---|---|---|
| `blocker_enforcement` | Select `Warn\nBlock` | `Warn` | whether unresolved blockers refuse completion |
| `todo_downgrades_blockers` | Check | `1` | an open ToDo turns a follow-up blocker into a warning |

Both defaults reproduce **today's** behaviour, so migrating changes nothing until a clinic opts in.
They are read through `do_derma/settings.py`, which stays the single owner and keeps its
degraded-read contract — if the singleton is unreadable, enforcement falls back to `Warn` and the
ToDo downgrade to on, i.e. never stricter than today.

**`get_readiness_settings()` already exists** — spec 2 Phase 3 landed it in `do_derma/settings.py`
to feed the config workspace's read-only Readiness panel. It returns a **dict**
(`{"enforcement", "todo_downgrades_blockers", "is_configurable"}`), not the attribute-style object
sketched below, and it already assumes **these two fieldnames**. Renaming either field here means
editing that reader in the same commit, because no site has the fields yet: every existing test
exercises its fallback branch, so a rename fails nothing and silently reports "not configurable"
forever. This spec adds the fields; it does not re-introduce the reader.

### 4. `complete_derma_session` consults it — `api.py:2686-2734`

```python
	readiness = get_session_readiness(patient_id, appointment_id, encounter_id)
	if readiness["blockers"] and readiness["enforcement"] == "Block":
		if not override_reason:
			frappe.throw(_("{0} blockers must be resolved, or completed with a reason.").format(len(readiness["blockers"])))
		_record_completion_override(encounter_doc, override_reason, readiness["blockers"])
```

Inserted **before** `_complete_derma_procedures_for_session` (`:2702`), so a refused session
submits nothing at all. `_record_completion_override` writes
`custom_derma_completion_override_reason` on the encounter and adds a Comment naming
`frappe.session.user` and each overridden blocker's title.

The endpoint gains one optional `override_reason` argument and returns `readiness` in its response
either way, so a Warn-mode client can show what it proceeded past.

### 5. The chart renders, stops deciding — `DermaChart.vue`

`sessionBlockers()` (`:2082-2090`), `showBlockers()` (`:2092-2102`) and the `!item.todo` filter at
`:785` are deleted. The Review tab renders `readiness.items` from the chart payload, grouped by
severity with a source badge, and no six-item truncation. `completeSession()` (`:2129-2159`) shows
the server's blockers and, in Block mode, collects an override reason before retrying.

`inventoryStats` / `followupStats` (`:787-796`) and the two existing cards keep working by reading
the same list, filtered by source — no `data-test` attribute is renamed.

### 6. The custom field

`custom_derma_completion_override_reason` (Small Text, module `Do Derma`) on `Patient Encounter`,
created by a patch following `add_derma_annotation_title_field.py`: existence guard, field guard,
`create_custom_fields(..., ignore_validate=True)`, targeted `clear_cache`. It ships in `fixtures`
automatically via the `module = "Do Derma"` filter.

**What stays unchanged:** the three endpoints' names and response shapes, the procedure-creation
throw, `encounterAlertItems`, the billing stub, and `CLINICAL_ACCESS_ROLES`.

## Security

- No new whitelisted endpoint. `complete_derma_session` (`api.py:2694`),
  `get_inventory_readiness` (`:1349`) and `get_followup_intelligence` (`:3374`) keep their
  `_ensure_clinical_access()` calls, which stay the first statement in each.
- Functions inside `do_derma/readiness/` are **not** whitelisted and are unreachable from the
  client except through those gated wrappers. The package must not gain its own
  `@frappe.whitelist()` decorators.
- **This spec closes a real hole:** a session with unresolved blockers can currently be completed
  by anything that is not the chart UI. After it, the decision is the server's.
- The override reason is clinic-authored text stored on a patient record. It renders through Vue
  (escaped) and, if it ever reaches print, through `printing/render.py`, which escapes every value
  by hand because Frappe's print Jinja environment does not autoescape.
- Regression tests: `TestClinicalAccessGate` gains cases for `get_inventory_readiness` and
  `get_followup_intelligence`, neither of which is individually asserted today.

## Acceptance Criteria

1. `get_session_readiness` returns the same items the two existing endpoints return today, for the
   same data, apart from the lot-rule reconciliation.
2. In **Block** mode, `complete_derma_session` with live blockers and no reason throws, and the
   encounter stays `docstatus 0` — with **no** Clinical Procedure submitted.
3. In **Block** mode with a reason, completion proceeds and the reason plus the blocker titles are
   recorded on the encounter.
4. In **Warn** mode, completion proceeds and the response still carries the blockers.
5. A direct `frappe.call` to `complete_derma_session` is subject to the same gate as the chart.
6. With `todo_downgrades_blockers` on, a follow-up item with an open ToDo is non-blocking and
   marked as downgraded; with it off, it blocks.
7. After migration, a template in a category named Botox or Filler has the product-tracking flag
   set, and its lot rule behaves as before.
8. A site with an unreadable `Derma Settings` singleton falls back to Warn and downgrade-on — never
   stricter than today.
9. The chart shows every readiness item, not the first six, and computes none of them itself.
10. **No regression:** `create_procedure_from_mark` throws for exactly the same cases as today.
11. **No regression:** `TestCompleteDermaSession`'s two existing docstatus tests still pass, in
    Warn mode.

## Phases

**Phase 1 — the package, behaviour unchanged.** Move all three engines into `do_derma/readiness/`,
add `get_session_readiness`, leave the endpoints and the client exactly as they are. Ship with the
first tests these engines have ever had.
*Exit:* `bench run-tests --module do_derma.tests.test_readiness` passes and the chart is byte-for-byte
unchanged in behaviour.

**Phase 2 — the server decides.** Settings fields, `complete_derma_session` consults readiness,
override reason field and Comment. Default Warn, so nothing changes for existing sites.
*Exit:* a direct API call cannot complete a blocked session on a site set to Block.

**Phase 3 — one owner in the UI.** The chart renders the server's list; `sessionBlockers`,
`showBlockers` and the `!item.todo` filter are deleted; Block mode collects the reason.
*Exit:* the browser holds no readiness logic at all.

**Phase 4 — reconcile the lot rule.** Migration patch, the `{"Botox","Filler"}` set removed from
inventory, plus the readiness panel in the config workspace showing the current mode.
*Exit:* readiness behaviour no longer depends on how a clinic named its categories.

## Open Questions

- **Does an override reason have a minimum length?**
  *Default:* non-empty after strip. No length rule.
- **Should Block mode also refuse to submit the draft Clinical Procedures?**
  *Default:* yes — the check runs before `_complete_derma_procedures_for_session`, so a refused
  session submits nothing.
- **Does the readiness response get cached per request?**
  *Default:* no. It is computed once per call; `complete_derma_session` computes it once and reuses
  it within the call.
- **Should a Warn-mode completion also record that blockers were live?**
  *Default:* no. Only Block-mode overrides are recorded; revisit if a clinic asks for it.
- **Where does the enforcement switch live in the UI?**
  *Default:* the config workspace's Readiness panel (spec 2 Phase 3), reading and writing the same
  singleton.

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/readiness/__init__.py` | *(new)* `get_session_readiness` |
| `do_derma/readiness/inventory.py` | *(new)* moved from `api.py:1357-1496`, category set removed |
| `do_derma/readiness/followup.py` | *(new)* moved from `api.py:3371-3500` |
| `do_derma/readiness/procedure.py` | *(new)* moved from `api.py:2911-2955` |
| `do_derma/readiness/session.py` | *(new)* the single owner |
| `do_derma/api.py` | wrappers become thin; `complete_derma_session` consults readiness; ~250 lines removed |
| `do_derma/do_derma/doctype/derma_settings/derma_settings.json` | two fields |
| `do_derma/settings.py` | `get_readiness_settings()` — **already shipped** by spec 2 Phase 3; only its fieldname constants move if a field is renamed |
| `do_derma/patches/add_derma_completion_override_field.py` | *(new)* |
| `do_derma/patches/set_product_tracking_for_derma_categories.py` | *(new)* |
| `do_derma/patches.txt` | two entries |
| `public/js/chart/DermaChart.vue` | render server readiness; delete local blocker logic |
| `public/js/config/panels/ReadinessPanel.vue` | enforcement mode (file created by spec 2) |
| `do_derma/tests/test_readiness.py` | *(new)* |
| `do_derma/tests/test_api.py` | `TestCompleteDermaSession` gains blocker cases |
| `e2e/tests/readiness-blockers.spec.ts` | *(new)*, on `demo_seed` fixtures |

`bench build --app do_derma` is **required** (`DermaChart.vue` changes). No bundle filename
changes. `bench --site dermaone.localhost migrate` is required — two patches and a doctype change.
