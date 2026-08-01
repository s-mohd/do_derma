# Derma Chart First Visit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make it possible for one clinician to chart one real dermatology visit end to end in `/app/derma-chart`, and clean up the misleading and redundant UI on the screens that change.

**Architecture:** New behaviour lands in new small modules (`schema.py`, `setup/defaults.py`, `assessment.py`, `install.py`) rather than growing the 3,481-line `api.py`; `api.py` keeps only thin whitelisted wrappers. Schema and configuration become self-healing through an `after_migrate` hook instead of one-shot patches. The Clinical Notes panel stops mirroring a non-existent Patient Encounter tab and instead renders one of two explicit assessment modes, stamped per encounter.

**Tech Stack:** Frappe v15 (Python 3.10+, MariaDB), Vue 3 for the chart page, esbuild bundles, Frappe `IntegrationTestCase` via the bench test runner.

**Design doc:** `docs/superpowers/specs/2026-08-01-derma-chart-first-visit-design.md`

## Global Constraints

- **All commands run from the bench root** `/Users/hameed/Developer/bench-v16`, never from the app directory.
- **Test runner is Frappe's, never pytest.** `bench --site dermaone.localhost run-tests --module <dotted.module>`. Tests are `IntegrationTestCase` subclasses and need a real site with `healthcare` and `do_health` installed.
- **Every new `@frappe.whitelist()` function calls `_ensure_clinical_access()` as its first statement.** That role check against `CLINICAL_ACCESS_ROLES` is the authorization boundary for this module — writes below it use `ignore_permissions=True`. `TestClinicalAccessGate` exists to enforce this.
- **Indentation:** new and modified `.py` files under `do_derma/` use **tabs** (matches `api.py` and `[tool.ruff.format] indent-style = "tab"`). `do_derma/tests/test_api.py` uses **4 spaces** — match the file you are editing. `.vue` files use 2 spaces.
- **Schema-defensive reads.** Never assume a field or doctype exists. Use `_has_doctype(dt)`, `_has_field(dt, fieldname)`, `_select_existing_fields(dt, FIELDS)` from `api.py`.
- **Never-clobbering rule.** Any function that writes a *configuration value* writes it only when the current value is empty. Creating a missing field is fine; overwriting a clinic's chosen value is not.
- `do_derma/tests/` has **no `__init__.py`** and does not need one — new test modules are discovered as namespace packages.
- Lint/format before each commit: `ruff check apps/do_derma && ruff format apps/do_derma` from the bench root.
- After touching anything under `public/js/`: `bench build --app do_derma`.
- Commit message format: `<type>: <description>` where type is one of feat, fix, refactor, docs, test, chore, perf, ci.

---

### Task 1: Schema spine — `ensure_derma_schema()` and the `after_migrate` hook

This is the task that repairs the current site. All 12 do_derma patches are recorded in `Patch Log` as applied, but `Custom Field` where `module = "Do Derma"` returns `[]`. Frappe runs a patch once ever, so no patch can fix this. An `after_migrate` hook runs on every migrate regardless of `Patch Log` state.

**Files:**
- Create: `do_derma/schema.py`
- Create: `do_derma/install.py`
- Create: `do_derma/tests/test_schema.py`
- Modify: `do_derma/hooks.py` (append `after_migrate` after the `fixtures` block, currently lines 18-21)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `do_derma.schema.DERMA_CUSTOM_FIELDS: dict[str, list[dict]]` — doctype name to list of Frappe custom-field dicts.
  - `do_derma.schema.ensure_custom_fields() -> list[str]` — returns `"<doctype>.<fieldname>"` for each field created this run; empty list when nothing was missing.
  - `do_derma.schema.ensure_derma_schema() -> list[str]` — top-level entry, currently just delegates to `ensure_custom_fields()`.
  - `do_derma.install.after_migrate() -> None`.

- [ ] **Step 1: Write the failing test**

Create `do_derma/tests/test_schema.py` (4-space indent, matching `test_api.py`):

```python
from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from do_derma import schema


class TestEnsureDermaSchema(IntegrationTestCase):
    def _delete_field(self, doctype, fieldname):
        name = frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname})
        if name:
            frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
            frappe.clear_cache(doctype=doctype)

    def test_creates_missing_custom_fields(self):
        self._delete_field("Patient Encounter", "custom_derma_soap_subjective")
        created = schema.ensure_custom_fields()
        self.assertIn("Patient Encounter.custom_derma_soap_subjective", created)
        self.assertTrue(frappe.get_meta("Patient Encounter").has_field("custom_derma_soap_subjective"))

    def test_second_run_is_noop(self):
        schema.ensure_custom_fields()
        created_again = schema.ensure_custom_fields()
        self.assertEqual(created_again, [])

    def test_never_overwrites_existing_value(self):
        schema.ensure_custom_fields()
        name = frappe.db.exists(
            "Custom Field", {"dt": "Patient Encounter", "fieldname": "custom_derma_soap_plan"}
        )
        frappe.db.set_value("Custom Field", name, "label", "Clinic Renamed Plan")
        schema.ensure_custom_fields()
        self.assertEqual(frappe.db.get_value("Custom Field", name, "label"), "Clinic Renamed Plan")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_schema
```

Expected: FAIL with `ModuleNotFoundError: No module named 'do_derma.schema'`.

- [ ] **Step 3: Write minimal implementation**

Create `do_derma/schema.py` (tab indent):

```python
from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ASSESSMENT_MODES = "Structured\nSOAP"

DERMA_CUSTOM_FIELDS: dict[str, list[dict]] = {
	"Patient Encounter": [
		{
			"fieldname": "custom_derma_assessment_section",
			"fieldtype": "Section Break",
			"label": "Derma Assessment",
			"insert_after": "custom_other_examination",
			"module": "Do Derma",
		},
		{
			"fieldname": "custom_derma_assessment_mode",
			"fieldtype": "Select",
			"label": "Assessment Mode",
			"options": ASSESSMENT_MODES,
			"description": "Format this visit was documented in. Stamped on first save.",
			"insert_after": "custom_derma_assessment_section",
			"module": "Do Derma",
		},
		{
			"fieldname": "custom_derma_soap_subjective",
			"fieldtype": "Small Text",
			"label": "Subjective",
			"insert_after": "custom_derma_assessment_mode",
			"module": "Do Derma",
		},
		{
			"fieldname": "custom_derma_soap_objective",
			"fieldtype": "Small Text",
			"label": "Objective",
			"insert_after": "custom_derma_soap_subjective",
			"module": "Do Derma",
		},
		{
			"fieldname": "custom_derma_soap_assessment",
			"fieldtype": "Small Text",
			"label": "Assessment",
			"insert_after": "custom_derma_soap_objective",
			"module": "Do Derma",
		},
		{
			"fieldname": "custom_derma_soap_plan",
			"fieldtype": "Small Text",
			"label": "Plan",
			"insert_after": "custom_derma_soap_assessment",
			"module": "Do Derma",
		},
	],
	"Healthcare Practitioner": [
		{
			"fieldname": "custom_derma_default_assessment_mode",
			"fieldtype": "Select",
			"label": "Default Derma Assessment Mode",
			"options": ASSESSMENT_MODES,
			"description": "Applies to new encounters only. Never overrides a stamped encounter.",
			"insert_after": "practitioner_name",
			"module": "Do Derma",
		},
	],
}


def ensure_custom_fields() -> list[str]:
	"""Create any missing Do Derma custom field. Never modifies an existing one."""
	created: list[str] = []
	for doctype, definitions in DERMA_CUSTOM_FIELDS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		missing = [d for d in definitions if not _field_exists(doctype, d["fieldname"])]
		if not missing:
			continue
		try:
			create_custom_fields({doctype: missing}, ignore_validate=True)
		except Exception:
			frappe.log_error(
				title="do_derma: failed to create custom fields",
				message=f"{doctype}: {[d['fieldname'] for d in missing]}\n{frappe.get_traceback()}",
			)
			continue
		created.extend(f"{doctype}.{d['fieldname']}" for d in missing)
		frappe.clear_cache(doctype=doctype)
	return created


def _field_exists(doctype: str, fieldname: str) -> bool:
	if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
		return True
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def ensure_derma_schema() -> list[str]:
	return ensure_custom_fields()
```

Create `do_derma/install.py` (tab indent):

```python
from __future__ import annotations

import frappe

from do_derma.schema import ensure_derma_schema


def after_migrate() -> None:
	"""Self-healing schema. Runs on every migrate, independent of Patch Log state."""
	try:
		created = ensure_derma_schema()
	except Exception:
		frappe.log_error(title="do_derma: after_migrate failed", message=frappe.get_traceback())
		return
	if created:
		print(f"do_derma: created {len(created)} custom field(s): {', '.join(created)}")
```

Modify `do_derma/hooks.py` — append directly after the `fixtures` block:

```python
after_migrate = "do_derma.install.after_migrate"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_schema
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Run a real migrate and confirm the site is repaired**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost migrate
```

Expected: the migrate output prints `do_derma: created 7 custom field(s): ...`. Confirm:

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost execute frappe.client.get_count --kwargs "{'doctype':'Custom Field','filters':{'module':'Do Derma'}}"
```

Expected: `7`.

- [ ] **Step 6: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
ruff check . && ruff format .
git add do_derma/schema.py do_derma/install.py do_derma/hooks.py do_derma/tests/test_schema.py
git commit -m "feat: self-healing derma schema via after_migrate hook"
```

---

### Task 2: Restore body-template images on the local bench

All 25 `Derma Body Template` rows have `File` records, so these images exist in production — this bench simply lacks the blobs, which is why the annotation canvas renders blank and the picker shows broken-image icons. Without them no later task can be visually verified, because marks are stored as percentages relative to the template element and correctness is a question of anatomical position.

**Files:**
- Create: `sites/dermaone.localhost/private/files/<25 image files>` (bench root, not the app repo — these are data, never committed)

**Interfaces:**
- Consumes: nothing.
- Produces: a bench where `Derma Body Template.image` paths resolve. No code artifact.

- [ ] **Step 1: List exactly which files are missing**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost console <<'EOF'
import frappe, os
site = frappe.get_site_path()
for t in frappe.get_all("Derma Body Template", fields=["name", "image"]):
    rel = (t["image"] or "").lstrip("/")
    if rel and not os.path.exists(os.path.join(site, rel)):
        print(t["image"])
EOF
```

Expected: 25 paths, all under `/private/files/`.

- [ ] **Step 2: Copy those files from production into the bench**

Copy each listed file into `/Users/hameed/Developer/bench-v16/sites/dermaone.localhost/private/files/`, preserving the exact filename — the `file_url` stored on each template must match byte for byte, including spaces (e.g. `WhatsApp Image 2024-10-11 at 16.03.11_d4c124f911b56d7a6912.jpg`).

These are anatomical diagrams and contain no patient data. Do not copy anything else out of production.

- [ ] **Step 3: Verify every template now resolves**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost console <<'EOF'
import frappe, os
site = frappe.get_site_path()
missing = [t["image"] for t in frappe.get_all("Derma Body Template", fields=["image"])
           if not os.path.exists(os.path.join(site, (t["image"] or "").lstrip("/")))]
print("MISSING:", len(missing))
EOF
```

Expected: `MISSING: 0`.

- [ ] **Step 4: Confirm visually**

Open `http://dermaone.localhost:8002/app/derma-chart`, select a patient, click **Annotate**, then **Templates**. Expected: thumbnails render as anatomical diagrams instead of broken-image icons, and selecting one paints the body map onto the canvas.

No commit — this task produces no repository changes.

---

### Task 3: Configuration seed — categories and the two live procedure templates

Nothing currently creates `Derma Procedure Category` records or tags any `Clinical Procedure Template`, so the annotation studio's procedure picker is empty even once Task 1 lands. `update_category_allowed_templates()` in `seed_standard_derma_body_templates.py` iterates templates where `custom_derma_category` is set — always an empty set today.

Laser (12,352 procedures, 81.5%) and Facial (1,543, 10.2%) cover 92% of everything ever recorded. The other 27 templates stay untagged and simply do not appear.

**Files:**
- Create: `do_derma/setup/__init__.py` (empty)
- Create: `do_derma/setup/defaults.py`
- Create: `do_derma/tests/test_defaults.py`
- Modify: `do_derma/install.py` (extend `after_migrate`)

**Interfaces:**
- Consumes: `do_derma.schema.ensure_derma_schema` (Task 1) — the `custom_derma_category` field must exist before templates can be tagged.
- Produces:
  - `do_derma.setup.defaults.DERMA_CATEGORIES: list[dict]`
  - `do_derma.setup.defaults.TEMPLATE_CONFIG: dict[str, dict]`
  - `do_derma.setup.defaults.ensure_categories() -> list[str]` — names created this run.
  - `do_derma.setup.defaults.ensure_template_configuration() -> list[str]` — `"<template>.<fieldname>"` for each value set this run.
  - `do_derma.setup.defaults.ensure_derma_defaults() -> dict[str, list[str]]` — `{"categories": [...], "templates": [...]}`.

**Clinical assumptions carried from the design doc.** These are configuration guesses requiring a clinician's sign-off before the pilot, not derived facts. They are encoded here so they are reviewable in one place:
- `marker_behavior = "area"` for both Laser and Facial.
- Laser variables: device, fluence, spot size, pulse width, passes.
- Facial variables: product, layers.

- [ ] **Step 1: Write the failing test**

Create `do_derma/tests/test_defaults.py` (4-space indent):

```python
from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from do_derma.setup import defaults


class TestDermaDefaults(IntegrationTestCase):
    def test_creates_all_categories(self):
        defaults.ensure_categories()
        for row in defaults.DERMA_CATEGORIES:
            self.assertTrue(frappe.db.exists("Derma Procedure Category", row["title"]))

    def test_second_run_creates_nothing(self):
        defaults.ensure_categories()
        self.assertEqual(defaults.ensure_categories(), [])

    def test_tags_laser_template_when_present(self):
        if not frappe.db.exists("Clinical Procedure Template", "Laser"):
            self.skipTest("Laser template not present on this site")
        frappe.db.set_value("Clinical Procedure Template", "Laser", "custom_derma_category", None)
        defaults.ensure_template_configuration()
        self.assertEqual(
            frappe.db.get_value("Clinical Procedure Template", "Laser", "custom_derma_category"),
            "Laser",
        )

    def test_never_overwrites_clinic_choice(self):
        if not frappe.db.exists("Clinical Procedure Template", "Laser"):
            self.skipTest("Laser template not present on this site")
        defaults.ensure_categories()
        frappe.db.set_value("Clinical Procedure Template", "Laser", "custom_derma_category", "Filler")
        defaults.ensure_template_configuration()
        self.assertEqual(
            frappe.db.get_value("Clinical Procedure Template", "Laser", "custom_derma_category"),
            "Filler",
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_defaults
```

Expected: FAIL with `ModuleNotFoundError: No module named 'do_derma.setup'`.

- [ ] **Step 3: Write minimal implementation**

Create `do_derma/setup/__init__.py` as an empty file. Create `do_derma/setup/defaults.py` (tab indent):

```python
from __future__ import annotations

import json

import frappe

DERMA_CATEGORIES: list[dict] = [
	{"title": "Botox", "workflow": "Aesthetic", "marker_behavior": "numbered_dot", "sequence": 10},
	{"title": "Filler", "workflow": "Aesthetic", "marker_behavior": "numbered_dot", "sequence": 20},
	{"title": "Laser", "workflow": "Aesthetic", "marker_behavior": "area", "sequence": 30},
	{"title": "Facial", "workflow": "Aesthetic", "marker_behavior": "area", "sequence": 40},
	{"title": "Acne", "workflow": "Medical", "marker_behavior": "finding_dot", "sequence": 50},
	{"title": "Scar", "workflow": "Medical", "marker_behavior": "finding_dot", "sequence": 60},
	{"title": "Pigmentation", "workflow": "Medical", "marker_behavior": "area", "sequence": 70},
	{"title": "Lesion", "workflow": "Medical", "marker_behavior": "target", "sequence": 80},
	{"title": "Biopsy", "workflow": "Medical", "marker_behavior": "x_mark", "sequence": 90},
]

LASER_VARIABLES = [
	{"fieldname": "device", "label": "Device", "fieldtype": "Data", "required": 1},
	{"fieldname": "fluence", "label": "Fluence (J/cm2)", "fieldtype": "Data", "required": 0},
	{"fieldname": "spot_size", "label": "Spot Size (mm)", "fieldtype": "Data", "required": 0},
	{"fieldname": "pulse_width", "label": "Pulse Width (ms)", "fieldtype": "Data", "required": 0},
	{"fieldname": "passes", "label": "Passes", "fieldtype": "Int", "required": 0},
]

FACIAL_VARIABLES = [
	{"fieldname": "product", "label": "Product", "fieldtype": "Data", "required": 1},
	{"fieldname": "layers", "label": "Layers", "fieldtype": "Int", "required": 0},
]

TEMPLATE_CONFIG: dict[str, dict] = {
	"Laser": {
		"custom_derma_category": "Laser",
		"custom_derma_marker_behavior": "area",
		"custom_derma_variables_json": json.dumps(LASER_VARIABLES, indent=2),
		"custom_derma_device_settings_required": 1,
	},
	"Facial": {
		"custom_derma_category": "Facial",
		"custom_derma_marker_behavior": "area",
		"custom_derma_variables_json": json.dumps(FACIAL_VARIABLES, indent=2),
		"custom_derma_product_tracking_required": 1,
	},
}


def ensure_categories() -> list[str]:
	if not frappe.db.exists("DocType", "Derma Procedure Category"):
		return []
	created: list[str] = []
	for row in DERMA_CATEGORIES:
		if frappe.db.exists("Derma Procedure Category", row["title"]):
			continue
		doc = frappe.new_doc("Derma Procedure Category")
		for fieldname, value in row.items():
			if doc.meta.has_field(fieldname):
				doc.set(fieldname, value)
		doc.insert(ignore_permissions=True)
		created.append(row["title"])
	return created


def ensure_template_configuration() -> list[str]:
	"""Set derma configuration on the live templates, never overwriting an existing value."""
	if not frappe.db.exists("DocType", "Clinical Procedure Template"):
		return []
	meta = frappe.get_meta("Clinical Procedure Template")
	applied: list[str] = []
	for template, values in TEMPLATE_CONFIG.items():
		if not frappe.db.exists("Clinical Procedure Template", template):
			continue
		for fieldname, value in values.items():
			if not meta.has_field(fieldname):
				continue
			if frappe.db.get_value("Clinical Procedure Template", template, fieldname):
				continue
			frappe.db.set_value(
				"Clinical Procedure Template", template, fieldname, value, update_modified=False
			)
			applied.append(f"{template}.{fieldname}")
	if applied:
		frappe.clear_cache(doctype="Clinical Procedure Template")
	return applied


def ensure_derma_defaults() -> dict[str, list[str]]:
	return {"categories": ensure_categories(), "templates": ensure_template_configuration()}
```

Modify `do_derma/install.py` — replace the body of `after_migrate` so defaults run after schema:

```python
from __future__ import annotations

import frappe

from do_derma.schema import ensure_derma_schema
from do_derma.setup.defaults import ensure_derma_defaults


def after_migrate() -> None:
	"""Self-healing schema and configuration. Runs on every migrate, independent of Patch Log."""
	try:
		created = ensure_derma_schema()
	except Exception:
		frappe.log_error(title="do_derma: schema ensure failed", message=frappe.get_traceback())
		created = []
	if created:
		print(f"do_derma: created {len(created)} custom field(s): {', '.join(created)}")

	try:
		seeded = ensure_derma_defaults()
	except Exception:
		frappe.log_error(title="do_derma: defaults ensure failed", message=frappe.get_traceback())
		return
	if seeded["categories"]:
		print(f"do_derma: seeded categories: {', '.join(seeded['categories'])}")
	if seeded["templates"]:
		print(f"do_derma: configured templates: {', '.join(seeded['templates'])}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_defaults
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Migrate and confirm the picker is populated**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost migrate
```

Expected output includes `do_derma: seeded categories:` with 9 names and `do_derma: configured templates:` with Laser and Facial entries.

- [ ] **Step 6: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
ruff check . && ruff format .
git add do_derma/setup do_derma/install.py do_derma/tests/test_defaults.py
git commit -m "feat: seed derma categories and configure Laser and Facial templates"
```

---

### Task 4: `Derma Settings` singleton for the structured field list

The Structured Assessment field list must be configurable per the design. A singleton doctype holds it; `assessment.py` (Task 5) falls back to a Python default when the singleton is absent or its field is blank.

**Files:**
- Create: `do_derma/do_derma/doctype/derma_settings/__init__.py` (empty)
- Create: `do_derma/do_derma/doctype/derma_settings/derma_settings.json`
- Create: `do_derma/do_derma/doctype/derma_settings/derma_settings.py`

**Interfaces:**
- Consumes: nothing.
- Produces: doctype `Derma Settings`, `issingle: 1`, with one field `structured_fields` (Small Text) holding newline-separated Patient Encounter fieldnames.

- [ ] **Step 1: Create the doctype JSON**

Create `do_derma/do_derma/doctype/derma_settings/derma_settings.json`:

```json
{
 "actions": [],
 "creation": "2026-08-01 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "structured_fields"
 ],
 "fields": [
  {
   "description": "Patient Encounter fieldnames shown in Structured Assessment mode, one per line. Leave blank to use the built-in default.",
   "fieldname": "structured_fields",
   "fieldtype": "Small Text",
   "label": "Structured Assessment Fields"
  }
 ],
 "index_web_pages_for_search": 1,
 "issingle": 1,
 "links": [],
 "modified": "2026-08-01 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Do Derma",
 "name": "Derma Settings",
 "owner": "Administrator",
 "permissions": [
  {
   "create": 1,
   "email": 1,
   "print": 1,
   "read": 1,
   "role": "System Manager",
   "share": 1,
   "write": 1
  },
  {
   "read": 1,
   "role": "Healthcare Administrator",
   "write": 1
  }
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 2: Create the controller and package marker**

Create `do_derma/do_derma/doctype/derma_settings/__init__.py` as an empty file. Create `do_derma/do_derma/doctype/derma_settings/derma_settings.py` (tab indent):

```python
from __future__ import annotations

from frappe.model.document import Document


class DermaSettings(Document):
	pass
```

- [ ] **Step 3: Migrate to create the doctype**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost migrate
```

- [ ] **Step 4: Verify the singleton exists**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost execute frappe.client.get_count --kwargs "{'doctype':'DocType','filters':{'name':'Derma Settings'}}"
```

Expected: `1`.

- [ ] **Step 5: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
ruff check . && ruff format .
git add do_derma/do_derma/doctype/derma_settings
git commit -m "feat: add Derma Settings singleton for structured assessment fields"
```

---

### Task 5: `assessment.py` — structured layout from a curated field list

`ASSESSMENT_TAB_FIELDNAME = "custom_assessment"` (`api.py:157`) and the tab-scan in `_assessment_tab_layout()` (`api.py:1129`) are replaced. That scan collects fields *after* matching a named Tab Break, but this site's Patient Encounter has only `encounter_details_tab` and `notes_tab`, both containing nothing but HTML render fields — all 88 real clinical fields sit before the first Tab Break, where a tab-name scan structurally cannot reach them.

The row shape produced here must stay byte-compatible with what `AssessmentPanel.vue` already consumes, or the frontend breaks.

**Files:**
- Create: `do_derma/assessment.py`
- Create: `do_derma/tests/test_assessment.py`

**Interfaces:**
- Consumes: `Derma Settings` (Task 4); `_child_table_layout` from `api.py:1166`.
- Produces:
  - `do_derma.assessment.MODE_STRUCTURED = "Structured"`, `MODE_SOAP = "SOAP"`
  - `do_derma.assessment.STRUCTURED_FIELDS_DEFAULT: list[str]`
  - `do_derma.assessment.SOAP_FIELDNAMES: list[str]` — the four `custom_derma_soap_*` names in S, O, A, P order.
  - `do_derma.assessment.get_structured_fieldnames() -> list[str]`
  - `do_derma.assessment.field_row(df, idx) -> dict` — the shared row builder.
  - `do_derma.assessment.structured_layout() -> list[dict]`
  - `do_derma.assessment.soap_layout() -> list[dict]`

- [ ] **Step 1: Write the failing test**

Create `do_derma/tests/test_assessment.py` (4-space indent):

```python
from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from do_derma import assessment


class TestStructuredLayout(IntegrationTestCase):
    def tearDown(self):
        frappe.db.set_single_value("Derma Settings", "structured_fields", "")

    def test_layout_returns_curated_fields(self):
        rows = assessment.structured_layout()
        names = [row["fieldname"] for row in rows]
        self.assertIn("custom_symptoms_notes", names)
        self.assertIn("custom_physical_examination", names)
        self.assertNotIn("naming_series", names)
        self.assertNotIn("company", names)

    def test_layout_skips_absent_fields(self):
        frappe.db.set_single_value(
            "Derma Settings", "structured_fields", "custom_symptoms_notes\nnot_a_real_field"
        )
        rows = assessment.structured_layout()
        self.assertEqual([row["fieldname"] for row in rows], ["custom_symptoms_notes"])

    def test_rows_carry_frontend_contract_keys(self):
        row = assessment.structured_layout()[0]
        for key in ("fieldname", "fieldtype", "label", "options", "reqd", "read_only",
                    "hidden", "depends_on", "default", "allow_on_submit",
                    "is_value_field", "layout_key", "idx"):
            self.assertIn(key, row)

    def test_soap_layout_is_four_fields_in_order(self):
        names = [row["fieldname"] for row in assessment.soap_layout()]
        self.assertEqual(names, [
            "custom_derma_soap_subjective",
            "custom_derma_soap_objective",
            "custom_derma_soap_assessment",
            "custom_derma_soap_plan",
        ])
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_assessment
```

Expected: FAIL with `ModuleNotFoundError: No module named 'do_derma.assessment'`.

- [ ] **Step 3: Write minimal implementation**

Create `do_derma/assessment.py` (tab indent):

```python
from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cint

MODE_STRUCTURED = "Structured"
MODE_SOAP = "SOAP"
VALID_MODES = (MODE_STRUCTURED, MODE_SOAP)

STRUCTURED_FIELDS_DEFAULT: list[str] = [
	"symptoms",
	"custom_symptom_duration",
	"custom_symptoms_notes",
	"custom_illness_progression",
	"diagnosis",
	"custom_differential_diagnosis",
	"custom_diagnosis_note",
	"custom_physical_examination",
	"custom_other_examination",
]

SOAP_FIELDNAMES: list[str] = [
	"custom_derma_soap_subjective",
	"custom_derma_soap_objective",
	"custom_derma_soap_assessment",
	"custom_derma_soap_plan",
]

TABLE_FIELD_TYPES = {"Table", "Table MultiSelect"}
NO_VALUE_FIELD_TYPES = {
	"Section Break",
	"Column Break",
	"Tab Break",
	"Button",
	"Image",
	"HTML",
	"Fold",
	"Heading",
}


def get_structured_fieldnames() -> list[str]:
	"""Configured list from Derma Settings, falling back to the built-in default."""
	configured = ""
	try:
		if frappe.db.exists("DocType", "Derma Settings"):
			configured = frappe.db.get_single_value("Derma Settings", "structured_fields") or ""
	except Exception:
		configured = ""
	names = [line.strip() for line in configured.splitlines() if line.strip()]
	return names or list(STRUCTURED_FIELDS_DEFAULT)


def field_row(df, idx: int) -> dict[str, Any]:
	"""Build one layout row. Shape is the contract AssessmentPanel.vue consumes."""
	row = {
		"fieldname": df.fieldname,
		"fieldtype": df.fieldtype,
		"label": df.label,
		"options": df.options,
		"reqd": cint(df.reqd),
		"read_only": cint(df.read_only),
		"hidden": cint(df.hidden),
		"depends_on": df.depends_on,
		"read_only_depends_on": df.read_only_depends_on,
		"mandatory_depends_on": df.mandatory_depends_on,
		"default": df.default,
		"allow_on_submit": cint(df.allow_on_submit),
		"is_value_field": df.fieldtype not in NO_VALUE_FIELD_TYPES,
		"show_if_empty": cint(getattr(df, "show_if_empty", 0)),
		"layout_key": f"{df.fieldname}-{idx}",
		"idx": idx,
	}
	if df.fieldtype in TABLE_FIELD_TYPES and df.options:
		from do_derma.api import _child_table_layout

		row["fields"] = _child_table_layout(df.options)
	return row


def _layout_for(fieldnames: list[str]) -> list[dict[str, Any]]:
	meta = frappe.get_meta("Patient Encounter")
	rows = []
	for position, fieldname in enumerate(fieldnames, start=1):
		df = meta.get_field(fieldname)
		if not df:
			continue
		rows.append(field_row(df, position))
	return rows


def structured_layout() -> list[dict[str, Any]]:
	return _layout_for(get_structured_fieldnames())


def soap_layout() -> list[dict[str, Any]]:
	return _layout_for(SOAP_FIELDNAMES)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_assessment
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
ruff check . && ruff format .
git add do_derma/assessment.py do_derma/tests/test_assessment.py
git commit -m "feat: build assessment layout from curated field list"
```

---

### Task 6: Mode resolution and stamping

Rules from the design, restated because they are the whole point of this task:

1. A new encounter opens in the practitioner's default (`Structured` when unset), unstamped.
2. The first save of any assessment content **stamps** `custom_derma_assessment_mode`.
3. A stamped encounter always reopens in its stamped mode; the practitioner default never overrides a stamp.
4. Changing format is allowed only while `docstatus = 0`.
5. **Switching never deletes.** Content in the inactive format stays stored.

**Files:**
- Modify: `do_derma/assessment.py` (append)
- Modify: `do_derma/tests/test_assessment.py` (append a test class)

**Interfaces:**
- Consumes: `structured_layout`, `soap_layout`, `MODE_STRUCTURED`, `MODE_SOAP` (Task 5); `custom_derma_assessment_mode` and `custom_derma_default_assessment_mode` (Task 1).
- Produces:
  - `do_derma.assessment.practitioner_default_mode(practitioner: str | None) -> str`
  - `do_derma.assessment.resolve_mode(encounter_doc) -> str`
  - `do_derma.assessment.is_stamped(encounter_doc) -> bool`
  - `do_derma.assessment.stamp_mode(encounter_doc, mode: str) -> None`
  - `do_derma.assessment.layout_for_mode(mode: str) -> list[dict]`

- [ ] **Step 1: Write the failing test**

Append to `do_derma/tests/test_assessment.py` (4-space indent):

```python
class TestAssessmentMode(IntegrationTestCase):
    def _encounter(self):
        patient = frappe.get_doc({
            "doctype": "Patient",
            "first_name": f"Mode{frappe.generate_hash(length=6)}",
            "sex": "Female",
        }).insert(ignore_permissions=True)
        practitioner = frappe.db.get_value("Healthcare Practitioner", {"status": "Active"}, "name")
        return frappe.get_doc({
            "doctype": "Patient Encounter",
            "patient": patient.name,
            "practitioner": practitioner,
            "encounter_date": nowdate(),
        }).insert(ignore_permissions=True)

    def test_unstamped_encounter_uses_structured_default(self):
        enc = self._encounter()
        self.assertFalse(assessment.is_stamped(enc))
        self.assertEqual(assessment.resolve_mode(enc), assessment.MODE_STRUCTURED)

    def test_mode_stamped_on_first_save(self):
        enc = self._encounter()
        assessment.stamp_mode(enc, assessment.MODE_SOAP)
        enc.reload()
        self.assertTrue(assessment.is_stamped(enc))
        self.assertEqual(enc.get("custom_derma_assessment_mode"), assessment.MODE_SOAP)

    def test_stamped_mode_honoured_on_reopen(self):
        enc = self._encounter()
        assessment.stamp_mode(enc, assessment.MODE_SOAP)
        practitioner = enc.get("practitioner")
        if practitioner:
            frappe.db.set_value(
                "Healthcare Practitioner", practitioner,
                "custom_derma_default_assessment_mode", assessment.MODE_STRUCTURED,
            )
        enc.reload()
        self.assertEqual(assessment.resolve_mode(enc), assessment.MODE_SOAP)

    def test_switch_preserves_other_format(self):
        enc = self._encounter()
        enc.db_set("custom_derma_soap_subjective", "itchy rash 3 days")
        assessment.stamp_mode(enc, assessment.MODE_SOAP)
        assessment.stamp_mode(enc, assessment.MODE_STRUCTURED)
        enc.reload()
        self.assertEqual(enc.get("custom_derma_assessment_mode"), assessment.MODE_STRUCTURED)
        self.assertEqual(enc.get("custom_derma_soap_subjective"), "itchy rash 3 days")

    def test_stamp_refuses_invalid_mode(self):
        enc = self._encounter()
        with self.assertRaises(frappe.ValidationError):
            assessment.stamp_mode(enc, "Freeform")

    def test_cannot_change_format_after_submit(self):
        enc = self._encounter()
        assessment.stamp_mode(enc, assessment.MODE_SOAP)
        enc.reload()
        enc.db_set("docstatus", 1, update_modified=False)
        enc.reload()
        with self.assertRaises(frappe.ValidationError):
            assessment.stamp_mode(enc, assessment.MODE_STRUCTURED)
```

Note the import at the top of this file must now include `nowdate`:

```python
from frappe.utils import nowdate
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_assessment
```

Expected: FAIL with `AttributeError: module 'do_derma.assessment' has no attribute 'is_stamped'`.

- [ ] **Step 3: Write minimal implementation**

Append to `do_derma/assessment.py` (tab indent):

```python
def practitioner_default_mode(practitioner: str | None) -> str:
	"""Practitioner preference for NEW encounters only."""
	if not practitioner:
		return MODE_STRUCTURED
	try:
		if not frappe.get_meta("Healthcare Practitioner").has_field(
			"custom_derma_default_assessment_mode"
		):
			return MODE_STRUCTURED
		value = frappe.db.get_value(
			"Healthcare Practitioner", practitioner, "custom_derma_default_assessment_mode"
		)
	except Exception:
		return MODE_STRUCTURED
	return value if value in VALID_MODES else MODE_STRUCTURED


def is_stamped(encounter_doc) -> bool:
	return (encounter_doc.get("custom_derma_assessment_mode") or "") in VALID_MODES


def resolve_mode(encounter_doc) -> str:
	"""A stamp always wins. The practitioner default applies only when unstamped."""
	if is_stamped(encounter_doc):
		return encounter_doc.get("custom_derma_assessment_mode")
	return practitioner_default_mode(encounter_doc.get("practitioner"))


def stamp_mode(encounter_doc, mode: str) -> None:
	"""Record the documentation format on the encounter. Never touches stored content."""
	if mode not in VALID_MODES:
		frappe.throw(frappe._("Unknown assessment mode: {0}").format(mode), frappe.ValidationError)
	if not frappe.get_meta("Patient Encounter").has_field("custom_derma_assessment_mode"):
		return
	if encounter_doc.get("custom_derma_assessment_mode") == mode:
		return
	if cint(encounter_doc.get("docstatus")) != 0 and is_stamped(encounter_doc):
		frappe.throw(
			frappe._("The assessment format cannot be changed after the encounter is submitted."),
			frappe.ValidationError,
		)
	encounter_doc.db_set("custom_derma_assessment_mode", mode, update_modified=False)


def layout_for_mode(mode: str) -> list[dict[str, Any]]:
	return soap_layout() if mode == MODE_SOAP else structured_layout()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_assessment
```

Expected: PASS, 9 tests (4 from Task 5, 5 new).

- [ ] **Step 5: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
ruff check . && ruff format .
git add do_derma/assessment.py do_derma/tests/test_assessment.py
git commit -m "feat: stamp assessment mode per encounter"
```

---

### Task 7: Wire the endpoints in `api.py`

`get_derma_assessment` and `set_derma_assessment` switch to the new module and start returning `mode`. A new endpoint sets the mode explicitly. `_assessment_tab_layout` and `ASSESSMENT_TAB_FIELDNAME` are deleted.

**Files:**
- Modify: `do_derma/api.py` — delete `ASSESSMENT_TAB_FIELDNAME` (line 157) and `_assessment_tab_layout` (lines 1129-1163); rewrite `get_derma_assessment` (line 2087) and `set_derma_assessment` (line 2106); add `set_derma_assessment_mode`
- Modify: `do_derma/tests/test_api.py` — extend `TestClinicalAccessGate`

**Interfaces:**
- Consumes: everything produced by Tasks 5 and 6.
- Produces:
  - `do_derma.api.get_derma_assessment(encounter=None, appointment=None, patient=None) -> dict` with keys `encounter`, `docstatus`, `mode`, `is_stamped`, `layout`, `values`, `context_values`, `other_mode_layout`, `other_mode_values`.
  - `do_derma.api.set_derma_assessment(payload=None, encounter=None, appointment=None, patient=None, mode=None) -> dict` — same shape.
  - `do_derma.api.set_derma_assessment_mode(mode, encounter=None, appointment=None, patient=None) -> dict` — same shape.

- [ ] **Step 1: Write the failing test**

Append these methods inside the existing `TestClinicalAccessGate` class in `do_derma/tests/test_api.py` (4-space indent):

```python
    def test_assessment_mode_endpoint_is_gated(self):
        frappe.set_user(self._make_limited_user())
        with self.assertRaises(frappe.PermissionError):
            api.set_derma_assessment_mode("SOAP", patient="does-not-matter")

    def test_get_assessment_is_gated(self):
        frappe.set_user(self._make_limited_user())
        with self.assertRaises(frappe.PermissionError):
            api.get_derma_assessment(patient="does-not-matter")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_api --test TestClinicalAccessGate
```

Expected: FAIL with `AttributeError: module 'do_derma.api' has no attribute 'set_derma_assessment_mode'`.

- [ ] **Step 3: Write minimal implementation**

In `do_derma/api.py`, delete the line `ASSESSMENT_TAB_FIELDNAME = "custom_assessment"` and the whole `_assessment_tab_layout` function. Add near the other imports:

```python
from do_derma import assessment as derma_assessment
```

Replace `get_derma_assessment` and `set_derma_assessment`, and add the new endpoint (tab indent):

```python
def _assessment_response(encounter_doc, mode: str) -> dict[str, Any]:
	other = (
		derma_assessment.MODE_STRUCTURED
		if mode == derma_assessment.MODE_SOAP
		else derma_assessment.MODE_SOAP
	)
	layout = derma_assessment.layout_for_mode(mode)
	other_layout = derma_assessment.layout_for_mode(other)
	if not encounter_doc:
		return {
			"encounter": "",
			"docstatus": None,
			"mode": mode,
			"is_stamped": False,
			"layout": layout,
			"values": {},
			"context_values": {},
			"other_mode": other,
			"other_mode_layout": other_layout,
			"other_mode_values": {},
		}
	return {
		"encounter": encounter_doc.name,
		"docstatus": cint(encounter_doc.docstatus),
		"mode": mode,
		"is_stamped": derma_assessment.is_stamped(encounter_doc),
		"layout": layout,
		"values": _serialize_assessment_values(encounter_doc, layout),
		"context_values": {
			"patient": encounter_doc.get("patient"),
			"appointment": encounter_doc.get("appointment"),
			"practitioner": encounter_doc.get("practitioner"),
		},
		"other_mode": other,
		"other_mode_layout": other_layout,
		"other_mode_values": _serialize_assessment_values(encounter_doc, other_layout),
	}


@frappe.whitelist()
def get_derma_assessment(encounter=None, appointment=None, patient=None):
	_ensure_clinical_access()
	encounter_doc = _resolve_patient_encounter_doc(
		encounter=encounter, appointment=appointment, patient=patient
	)
	mode = (
		derma_assessment.resolve_mode(encounter_doc)
		if encounter_doc
		else derma_assessment.MODE_STRUCTURED
	)
	return _assessment_response(encounter_doc, mode)


@frappe.whitelist()
def set_derma_assessment_mode(mode, encounter=None, appointment=None, patient=None):
	_ensure_clinical_access()
	encounter_doc = _resolve_patient_encounter_doc(
		encounter=encounter, appointment=appointment, patient=patient, ptype="write"
	)
	if not encounter_doc:
		frappe.throw(_("No encounter found for this session."), frappe.DoesNotExistError)
	derma_assessment.stamp_mode(encounter_doc, mode)
	encounter_doc.reload()
	return _assessment_response(encounter_doc, derma_assessment.resolve_mode(encounter_doc))
```

In `set_derma_assessment`, replace the `layout = _assessment_tab_layout()` line with mode-aware resolution, stamp after a successful write, and return the shared response. The existing docstatus guards and the `allow_on_submit` filtering loop stay exactly as they are:

```python
@frappe.whitelist()
def set_derma_assessment(payload=None, encounter=None, appointment=None, patient=None, mode=None):
	_ensure_clinical_access()
	values = _parse_payload(payload) or {}
	if not isinstance(values, dict):
		frappe.throw(_("Assessment payload must be an object."), frappe.ValidationError)

	encounter_doc = _resolve_patient_encounter_doc(
		encounter=encounter, appointment=appointment, patient=patient, ptype="write"
	)
	if not encounter_doc:
		frappe.throw(_("No encounter found for this session."), frappe.DoesNotExistError)
	if cint(encounter_doc.docstatus) == 2:
		frappe.throw(_("Cancelled encounters cannot be edited."))

	active_mode = mode if mode in derma_assessment.VALID_MODES else derma_assessment.resolve_mode(
		encounter_doc
	)
	layout = derma_assessment.layout_for_mode(active_mode)
	field_map = {
		row.get("fieldname"): row
		for row in layout
		if row.get("fieldname") and row.get("is_value_field")
	}

	# Keep api.py:2121-2135 verbatim: the `only_allow_on_submit` guard and the
	# `for fieldname, value in values.items()` loop that skips fields absent from
	# field_map and skips non-allow-on-submit fields on submitted encounters.

	derma_assessment.stamp_mode(encounter_doc, active_mode)
	encounter_doc.reload()
	return _assessment_response(encounter_doc, active_mode)
```

- [ ] **Step 4: Run the full backend suite**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --app do_derma
```

Expected: PASS. `TestClinicalAccessGate` now covers the two new gated calls.

- [ ] **Step 5: Confirm no reference to the removed tab scan survives**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma && grep -rn "custom_assessment\|_assessment_tab_layout" do_derma/ --include="*.py" --include="*.vue"
```

Expected: only the `AssessmentPanel.vue` empty-state string, which Task 8 replaces.

- [ ] **Step 6: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
ruff check . && ruff format .
git add do_derma/api.py do_derma/tests/test_api.py
git commit -m "feat: serve assessment layout by mode and stamp on save"
```

---

### Task 8: Split `AssessmentPanel.vue` and add the mode toggle

`AssessmentPanel.vue` is 855 lines. It splits into a shell plus two field renderers. The shell owns the mode banner and the read-only view of the other format — the safety mechanism that stops an empty format reading as an undocumented visit.

**Files:**
- Create: `do_derma/public/js/chart/components/SoapNoteFields.vue`
- Create: `do_derma/public/js/chart/components/StructuredAssessmentFields.vue`
- Modify: `do_derma/public/js/chart/components/AssessmentPanel.vue`
- Modify: `do_derma/public/js/chart/DermaChart.vue` — `loadAssessment` (line 2350), `saveAssessment` (line 2371), and the `<AssessmentPanel>` usage (lines 71-86)

**Interfaces:**
- Consumes: the `get_derma_assessment` / `set_derma_assessment` / `set_derma_assessment_mode` response shape from Task 7.
- Produces: `AssessmentPanel` gains props `mode: String`, `isStamped: Boolean`, `otherMode: String`, `otherModeLayout: Array`, `otherModeValues: Object`, and emits `change-mode` with a mode string. Existing props and the `request-edit` / `save` / `refresh` emits are unchanged.

- [ ] **Step 1: Extract the two field renderers**

Move the existing field-rendering block out of `AssessmentPanel.vue` into `StructuredAssessmentFields.vue`, keeping the Frappe control mounting logic (`fieldHosts`, `controls`, `renderToken`) exactly as it is — that logic is what binds Frappe controls into the Vue tree and is easy to break. Props: `layout`, `values`, `contextValues`, `editMode`, `allowOnSubmitFields`, `docstatus`. Emits: `update` with the working values object.

Create `SoapNoteFields.vue` rendering the four narrative fields as plain textareas, since they are `Small Text`:

```vue
<template>
  <div class="soap-fields">
    <label v-for="row in layout" :key="row.fieldname" class="soap-field">
      <span class="soap-field-label">{{ row.label }}</span>
      <textarea
        :value="values[row.fieldname] || ''"
        :readonly="!editMode"
        rows="4"
        @input="$emit('update', { ...values, [row.fieldname]: $event.target.value })"
      />
    </label>
  </div>
</template>

<script setup>
defineProps({
  layout: { type: Array, default: () => [] },
  values: { type: Object, default: () => ({}) },
  editMode: { type: Boolean, default: false },
})
defineEmits(["update"])
</script>
```

- [ ] **Step 2: Add the mode banner and other-format view to the shell**

In `AssessmentPanel.vue`, replace the empty-state string `"No fields found in Patient Encounter tab custom_assessment."` with a real empty state, and add the banner above the fields:

```vue
<div v-if="isStamped" class="assessment-mode-banner">
  <span>{{ mode === "SOAP" ? __("Documented as SOAP note") : __("Documented as structured assessment") }}</span>
  <button type="button" class="ghost small" @click="showOther = !showOther">
    {{ showOther
      ? __("Hide other format")
      : (otherMode === "SOAP" ? __("View SOAP note") : __("View structured fields")) }}
  </button>
</div>

<div v-if="showOther" class="assessment-other-format">
  <p class="status-note">
    {{ __("Read-only. This visit was documented in the {0} format.").replace("{0}", mode) }}
  </p>
  <SoapNoteFields v-if="otherMode === 'SOAP'" :layout="otherModeLayout" :values="otherModeValues" :edit-mode="false" />
  <StructuredAssessmentFields v-else :layout="otherModeLayout" :values="otherModeValues" :edit-mode="false" :docstatus="docstatus" />
</div>
```

Add a format switch, draft-only, behind a confirm:

```vue
<button
  v-if="Number(docstatus ?? 0) === 0"
  type="button"
  class="ghost small"
  @click="requestModeChange"
>
  {{ otherMode === "SOAP" ? __("Switch to SOAP note") : __("Switch to structured") }}
</button>
```

```js
function requestModeChange() {
  frappe.confirm(
    __("Switch this visit to the {0} format? Nothing you have already written is deleted — it stays stored and returns if you switch back.").replace("{0}", props.otherMode),
    () => emit("change-mode", props.otherMode)
  )
}
```

- [ ] **Step 3: Wire the new fields through `DermaChart.vue`**

In `loadAssessment` and `saveAssessment`, carry the new response keys onto `assessmentPanel`:

```js
assessmentPanel.mode = message.mode || "Structured"
assessmentPanel.isStamped = Boolean(message.is_stamped)
assessmentPanel.otherMode = message.other_mode || "SOAP"
assessmentPanel.otherModeLayout = message.other_mode_layout || []
assessmentPanel.otherModeValues = message.other_mode_values || {}
```

Add the handler and bind the new props on `<AssessmentPanel>`:

```js
async function changeAssessmentMode(mode) {
  const response = await frappe.call({
    method: "do_derma.api.set_derma_assessment_mode",
    args: { ...contextArgs(), mode },
  })
  const message = response.message || {}
  assessmentPanel.mode = message.mode
  assessmentPanel.isStamped = Boolean(message.is_stamped)
  assessmentPanel.layout = message.layout || []
  assessmentPanel.values = message.values || {}
  assessmentPanel.otherMode = message.other_mode
  assessmentPanel.otherModeLayout = message.other_mode_layout || []
  assessmentPanel.otherModeValues = message.other_mode_values || {}
}
```

- [ ] **Step 4: Build and verify in the browser**

```bash
cd /Users/hameed/Developer/bench-v16 && bench build --app do_derma
```

Open the chart for a patient with an appointment. Expected: Clinical Notes now renders real fields instead of *"No fields found in Patient Encounter tab custom_assessment."* Save content, reload, and confirm the mode banner names the format. Switch format and confirm the previously entered content reappears when you switch back.

- [ ] **Step 5: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git add do_derma/public/js/chart
git commit -m "feat: assessment mode toggle with read-only view of the other format"
```

---

### Task 9: Print formats

Both Patient Encounter print formats are hand-written HTML (`print_format_builder: 0`) and render only fields they name, so a SOAP-documented visit would print blank. The site default is `Encounter print (Dr Sadiq)`; `Encounter Print` is the standard fallback.

**Files:**
- Modify: Print Format `Encounter print (Dr Sadiq)` (database record, edited through the desk UI or a patch)
- Modify: Print Format `Encounter Print` (database record)
- Create: `do_derma/patches/add_derma_assessment_to_print_formats.py`
- Modify: `do_derma/patches.txt`

**Interfaces:**
- Consumes: `custom_derma_assessment_mode` and the four `custom_derma_soap_*` fields (Task 1).
- Produces: no Python API. A printed encounter renders the format it was documented in.

- [ ] **Step 1: Write the patch**

Create `do_derma/patches/add_derma_assessment_to_print_formats.py` (tab indent). It appends a marked block, and is a no-op if the marker is already present, so it is safe to re-run:

```python
from __future__ import annotations

import frappe

MARKER = "<!-- do_derma:assessment -->"

BLOCK = """
<!-- do_derma:assessment -->
{% if doc.custom_derma_assessment_mode == "SOAP" %}
<div class="derma-soap">
	<h5>Assessment (SOAP)</h5>
	{% if doc.custom_derma_soap_subjective %}<p><b>Subjective:</b> {{ doc.custom_derma_soap_subjective }}</p>{% endif %}
	{% if doc.custom_derma_soap_objective %}<p><b>Objective:</b> {{ doc.custom_derma_soap_objective }}</p>{% endif %}
	{% if doc.custom_derma_soap_assessment %}<p><b>Assessment:</b> {{ doc.custom_derma_soap_assessment }}</p>{% endif %}
	{% if doc.custom_derma_soap_plan %}<p><b>Plan:</b> {{ doc.custom_derma_soap_plan }}</p>{% endif %}
</div>
{% endif %}
"""

TARGETS = ("Encounter print (Dr Sadiq)", "Encounter Print")


def execute():
	for name in TARGETS:
		if not frappe.db.exists("Print Format", name):
			continue
		html = frappe.db.get_value("Print Format", name, "html") or ""
		if MARKER in html:
			continue
		frappe.db.set_value("Print Format", name, "html", html + BLOCK, update_modified=False)
	frappe.clear_cache()
```

Append to `do_derma/patches.txt` under `[post_model_sync]`:

```
do_derma.patches.add_derma_assessment_to_print_formats
```

- [ ] **Step 2: Run the patch**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost migrate
```

- [ ] **Step 3: Verify both formats carry the block**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost console <<'EOF'
import frappe
for n in ("Encounter print (Dr Sadiq)", "Encounter Print"):
    html = frappe.db.get_value("Print Format", n, "html") or ""
    print(n, "->", "do_derma:assessment" in html)
EOF
```

Expected: both print `True`.

- [ ] **Step 4: Verify a printed SOAP encounter**

Open a Patient Encounter documented in SOAP mode, choose Print, and confirm the four narrative fields appear. Repeat with a Structured encounter and confirm the SOAP block is absent.

- [ ] **Step 5: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
ruff check . && ruff format .
git add do_derma/patches/add_derma_assessment_to_print_formats.py do_derma/patches.txt
git commit -m "feat: render derma SOAP assessment in encounter print formats"
```

---

### Task 10: UI cleanup — misleading states

Three states currently misinform a clinician.

**Files:**
- Modify: `do_derma/public/js/chart/components/ProcedurePanel.vue` (Review empty state)
- Modify: `do_derma/public/js/chart/components/ConsentPanel.vue` (validation on mount)
- Modify: `do_derma/public/js/chart/annotation/DermaAnnotationStudio.jsx` and `do_derma/public/js/chart/excalidraw/EmbeddedExcalidraw.jsx` (image failure)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: no API changes.

- [ ] **Step 1: Rescope the Review empty state**

The panel currently reads *"No procedures added yet"* / *"Procedures will appear here after they are recorded for this patient"* while the timeline directly below lists 11 prior visits with procedures. The empty state is encounter-scoped; the copy is patient-scoped. Change to:

```
__("No procedures in this visit")
__("Procedures recorded during this visit appear here. Earlier visits are listed in the timeline below.")
```

- [ ] **Step 2: Stop validating Consent on mount**

The Consent Template field renders with a red required border before any interaction, because `ConsentPanel.vue:237` passes `reqd: 1` into the Frappe control at construction time. Introduce a `hasAttemptedSubmit` ref, initially `false`, flipped to `true` in the create handler that already emits *"Consent template is required."* (`ConsentPanel.vue:427`). Build the control with `reqd: 0` and re-apply `reqd: 1` via `set_df_property` only once `hasAttemptedSubmit` is true, so the field is neutral until the clinician actually tries to submit. Validation behaviour on submit is unchanged.

- [ ] **Step 3: Give a failed body-map image a real message**

Add an `onError` handler to the template thumbnails and to the canvas image load. On failure render a placeholder tile with:

```
__("Body map image unavailable")
__("The template image could not be loaded. Contact your administrator.")
```

Never leave a broken-image icon or a silently blank canvas.

- [ ] **Step 4: Build and verify**

```bash
cd /Users/hameed/Developer/bench-v16 && bench build --app do_derma
```

Verify: Review on a patient with history shows the rescoped copy; Consent opens with a neutral template field; temporarily renaming one template image on disk produces the placeholder rather than a broken icon.

- [ ] **Step 5: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git add do_derma/public/js/chart
git commit -m "fix: correct misleading empty, validation and image-failure states"
```

---

### Task 11: UI cleanup — remove redundancy

**Files:**
- Modify: `do_derma/public/js/chart/DermaChart.vue` (Photos tab composition, lines ~543-556 for the quick-actions bindings)
- Modify: `do_derma/public/js/chart/components/DermaQuickActionsPanel.vue`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `DermaQuickActionsPanel` no longer emits `new-procedure`. Any listener for it must be removed at the same time.

- [ ] **Step 1: Stop rendering Evidence and Compare twice**

The Photos tab renders `DermaEvidencePanel` and Photo Compare identically to the right rail — the same two panels twice on one screen. The Photos branch of the main column starts at `DermaChart.vue:116` (`<template v-else-if="activeSection === 'photos'">`); the rail copies live in the `derma-console-side` aside beginning at `DermaChart.vue:543`. Keep the main-column copies and add `v-if="activeSection !== 'photos'"` to the two rail panels, so they remain visible on every other section and appear exactly once on Photos.

- [ ] **Step 2: Collapse the duplicate annotate actions**

`@new-procedure="openAnnotationStudio"` (`DermaChart.vue:549`) makes *New Procedure* and *Annotate* the same handler, and *Annotate* appears three times on one screen — section bar, quick actions, and the Previous Annotations header. Remove the `new-procedure` button and emit from `DermaQuickActionsPanel.vue`, and remove the `@new-procedure` listener. Quick Actions keeps only distinct entries: New Prescription, Upload Photos, Consent, Follow-up. The section-bar Annotate button is the single annotate entry point.

- [ ] **Step 3: Build and verify**

```bash
cd /Users/hameed/Developer/bench-v16 && bench build --app do_derma
```

Verify: the Photos tab shows Evidence and Compare exactly once; the word Annotate appears once outside the studio; every remaining quick action leads somewhere distinct.

- [ ] **Step 4: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git add do_derma/public/js/chart
git commit -m "refactor: remove duplicated panels and annotate actions"
```

---

### Task 12: UI cleanup — design-system consistency

**Files:**
- Modify: `do_derma/public/js/chart/components/PrescriptionPanel.vue`
- Modify: `do_derma/public/js/chart/components/ProcedurePanel.vue` (remove Complete Session, line ~403)
- Modify: `do_derma/public/js/chart/DermaChart.vue` (remove the `@complete-session` listener, line 196)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `ProcedurePanel` no longer emits `complete-session`. `completeSession()` in `DermaChart.vue` stays — it is still the header's handler.

- [ ] **Step 1: Restyle the Prescription grid**

The panel embeds a raw Frappe grid whose Save renders in Frappe blue against the app's green palette. Wrap the grid in the app's panel styling and restyle its primary button to match the section-bar primary. Do not replace the grid control itself — it is the Frappe child-table editor and rebuilding it is out of scope.

- [ ] **Step 2: Remove the duplicate completion action**

*Complete Session* (`ProcedurePanel.vue:403`) and *Complete Encounter* both reach `completeSession()` → `do_derma.api.complete_derma_session`. One action behind two labels and two colours. Delete the `Complete Session` button and its `complete-session` emit, and drop the corresponding listener in `DermaChart.vue:196`. *Complete Encounter* keeps the header slot. Leave `Sync Billables` untouched.

- [ ] **Step 3: Build and verify**

```bash
cd /Users/hameed/Developer/bench-v16 && bench build --app do_derma
```

Verify: no blue primary buttons remain on the chart; Review has exactly one terminal action path, and completing from the header still works.

- [ ] **Step 4: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git add do_derma/public/js/chart
git commit -m "refactor: unify chart button styling and completion action"
```

---

### Task 13: UI cleanup — header readability

**Files:**
- Modify: `do_derma/public/js/chart/components/DermaEncounterHeader.vue`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: no API changes.

- [ ] **Step 1: Stop truncating the patient name**

The name truncates to *"MARWA JAMAL SALEH ALI BAR..."* with no tooltip, on the most-read strip of the page. Allow it to wrap to two lines, and add a `:title` attribute carrying the full name so it is recoverable on hover either way.

- [ ] **Step 2: Raise chip contrast**

The Allergies / Visit / Status / Insurance chips use low-contrast small-caps labels. Darken the label colour to meet WCAG AA (4.5:1) against the chip background, keeping the existing size and layout.

- [ ] **Step 3: Build and verify**

```bash
cd /Users/hameed/Developer/bench-v16 && bench build --app do_derma
```

Verify with a long patient name that the full name is readable, and check the chip labels against a contrast checker.

- [ ] **Step 4: Commit**

```bash
cd /Users/hameed/Developer/bench-v16/apps/do_derma
git add do_derma/public/js/chart/components/DermaEncounterHeader.vue
git commit -m "fix: make patient name and header chips readable"
```

---

### Task 14: Full-suite regression and acceptance walkthrough

**Files:**
- None. This task verifies.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a charted visit.

- [ ] **Step 1: Run the whole backend suite**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --app do_derma
```

Expected: PASS, no skips other than the two `Laser`-template guards in `test_defaults.py` if that template is absent.

- [ ] **Step 2: Walk the acceptance path**

Open `/app/derma-chart` for a patient with a Laser appointment and, in order: write an assessment in either mode; open the annotation studio; select a body template that renders; pick the Laser procedure; place marks; save; confirm the marks appear in Review; complete the encounter.

- [ ] **Step 3: Confirm marks were actually written**

```bash
cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost execute frappe.client.get_count --kwargs "{'doctype':'Derma Chart Mark'}"
```

Expected: greater than `0` — it is `0` today, and this is the number that proves the feature became usable.

- [ ] **Step 4: Confirm the note prints in the format it was written**

Print the encounter and confirm the assessment renders in its stamped format.

- [ ] **Step 5: Check the console is clean of app errors**

Open DevTools on the chart page. Expected: no errors originating from `do_derma` bundles. Pre-existing environmental noise is acceptable and out of scope — socket.io 404s (bench socketio not running locally), the Excalidraw `unload` permissions-policy violation, and the imagemapster non-passive listener warning.

---

## Open items carried from the design

These are recorded so they are not silently lost. Neither blocks this plan.

1. **Clinical sign-off on configuration guesses.** Marker behaviour (`area`) and the Laser and Facial variable sets in Task 3 are assumptions, not derived facts. A clinician must confirm them before the pilot, or the first real visit is charted against the wrong fields.
2. **The April 2026 annotation stoppage.** `Health Annotation` creation ran at 288–472 per month through March 2026, then zero across April, May, June and July, while Clinical Procedures and Patient Encounters continued at full volume. do_derma's first commit is 2026-06-17, two months later, so it is not the cause. Roughly 1,570 procedures have since been recorded with no body-map documentation. This is a do_health question and needs its own investigation.
