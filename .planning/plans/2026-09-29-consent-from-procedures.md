# Consent from the Procedures tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the derma chart's Consent tab with a New Consent flow in the Procedures tab, where one signed consent covers several procedures.

**Architecture:** A new `do_derma/consent.py` owns which consent doctype the site writes (do_dental's `Encounter Consent` or do_health's `Consent Form`), its procedure table, rendering and coverage lookups. `Consent Form` gains a derma-owned child table through `schema.py`. The chart's procedure rows carry their covering consents; the UI opens the existing `ConsentPanel` in an overlay from the Procedures tab.

**Tech Stack:** Frappe v16 (Python, `IntegrationTestCase`), Vue 3 SFCs built by `bench build`.

**Spec:** `.planning/specs/2026-09-29-consent-from-procedures.md`

## Global Constraints

- Do not modify do_health or do_dental.
- On a site with do_dental, write `Encounter Consent` and its `procedure_items` table exactly as today.
- Existing consents are never modified; no data patch.
- Custom fields live in `schema.py`, never only in a patch.
- Tabs for indentation in Python; match surrounding Vue/CSS style. No top-of-file comments; terse docstrings.
- Test runs: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_consent` (whole module) or add `--test <bare_method_name>`. A run that prints only the header ran nothing.
- The suite has a standing red baseline on `main` (see memory `bench-v16-test-and-lint-quirks`); compare failing names against `main`, do not expect green.
- Lint changed Python files only: `pipx run ruff check <files>`.

## Review Focus

1. Duplicate procedure ids in one payload → stored once (Task 3 test `test_a_procedure_picked_twice_is_stored_once`).
2. A cancelled or unsigned consent → covers nothing (Task 2 tests `test_an_unsigned_consent_covers_nothing`, `test_a_cancelled_consent_covers_nothing`).
3. A cancelled Clinical Procedure → not offered in the checklist, not counted as needing consent (Task 7 `consentProcedureOptions` / `consentPendingProcedures` filter `docstatus !== 2`; browser check).
4. A procedure id from another patient or visit, or a cancelled one → refused (Task 3 test `test_a_procedure_from_another_visit_is_refused`).
5. A legacy consent linked only through `Consent Form.clinical_procedure` → still counts and still opens (Task 2 test `test_a_legacy_consent_with_only_its_procedure_link_still_counts`).

---

## File Structure

- Create `do_derma/do_derma/doctype/derma_consent_procedure/{__init__.py, derma_consent_procedure.json, derma_consent_procedure.py}` — the child row.
- Modify `do_derma/schema.py` — `Consent Form.custom_derma_procedures`.
- Create `do_derma/consent.py` — `ConsentDoctype`, selection/validation, render context, coverage.
- Modify `do_derma/api.py` — consent endpoints delegate to `consent.py`; chart procedure rows gain `consents` and `consent_required`; delete guard; `get_derma_consents` deleted.
- Create `do_derma/tests/test_consent.py`.
- Modify `do_derma/public/js/chart/components/ConsentPanel.vue` — overlay form: checklist, Cancel, no history column.
- Modify `do_derma/public/js/chart/components/ProcedurePanel.vue` — New Consent button, row badges.
- Modify `do_derma/public/js/chart/DermaChart.vue` — tab removed, overlay, alert, handlers.
- Modify `do_derma/public/js/chart/derma_chart.bundle.css` — overlay styles.

All paths below are relative to `/Users/hameed/Developer/bench-v16/apps/do_derma`.

---

### Task 1: Consent procedure table on Consent Form

**Files:**
- Create: `do_derma/do_derma/doctype/derma_consent_procedure/__init__.py` (empty)
- Create: `do_derma/do_derma/doctype/derma_consent_procedure/derma_consent_procedure.json`
- Create: `do_derma/do_derma/doctype/derma_consent_procedure/derma_consent_procedure.py`
- Modify: `do_derma/schema.py` (`DERMA_CUSTOM_FIELDS`, new `"Consent Form"` key)
- Test: `do_derma/tests/test_consent.py`

**Interfaces:**
- Produces: doctype `Derma Consent Procedure` (`clinical_procedure`, `procedure_template`, `display_name`); field `Consent Form.custom_derma_procedures`.

- [ ] **Step 1: Write the failing test**

Create `do_derma/tests/test_consent.py`:

```python
from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from do_derma import schema


class TestConsentSchema(IntegrationTestCase):
	def test_consent_form_carries_the_procedure_table(self):
		if not frappe.db.exists("DocType", "Consent Form"):
			self.skipTest("Consent Form is not installed.")
		schema.ensure_derma_schema()
		field = frappe.get_meta("Consent Form").get_field("custom_derma_procedures")
		self.assertIsNotNone(field)
		self.assertEqual((field.fieldtype, field.options), ("Table", "Derma Consent Procedure"))
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_consent`
Expected: FAIL, `field` is `None`.

- [ ] **Step 3: Create the child doctype**

`derma_consent_procedure.py`:

```python
from frappe.model.document import Document


class DermaConsentProcedure(Document):
	pass
```

`derma_consent_procedure.json`:

```json
{
 "actions": [],
 "creation": "2026-09-29 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "clinical_procedure",
  "procedure_template",
  "display_name"
 ],
 "fields": [
  {
   "fieldname": "clinical_procedure",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Clinical Procedure",
   "options": "Clinical Procedure",
   "reqd": 1
  },
  {
   "fieldname": "procedure_template",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Procedure Template",
   "options": "Clinical Procedure Template"
  },
  {
   "fieldname": "display_name",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Display Name"
  }
 ],
 "index_web_pages_for_search": 0,
 "istable": 1,
 "links": [],
 "modified": "2026-09-29 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Do Derma",
 "name": "Derma Consent Procedure",
 "naming_rule": "Random",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "creation",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 4: Declare the Table field**

In `do_derma/schema.py`, add a key to `DERMA_CUSTOM_FIELDS` after the `"Clinical Procedure Template"` entry (before `"Healthcare Practitioner"`). `ensure_derma_schema` already skips doctypes that are not installed and Table fields whose child doctype is missing.

```python
	# One consent can cover several procedures. do_health's Consent Form links only one, so derma
	# owns this table; clinical_procedure still holds the first row for do_health's own readers.
	"Consent Form": [
		{
			"fieldname": "custom_derma_procedures",
			"fieldtype": "Table",
			"label": "Procedures",
			"options": "Derma Consent Procedure",
			"insert_after": "clinical_procedure",
			"hidden": 1,
		},
	],
```

- [ ] **Step 5: Migrate and run the test**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost migrate && bench --site dermaone.localhost run-tests --module do_derma.tests.test_consent`
Expected: `Ran 1 test ... OK`.

- [ ] **Step 6: Commit**

```bash
git add do_derma/do_derma/doctype/derma_consent_procedure do_derma/schema.py do_derma/tests/test_consent.py
git commit -m "feat(consent): procedure table on Consent Form"
```

---

### Task 2: `consent.py` — doctype, rendering, coverage

**Files:**
- Create: `do_derma/consent.py`
- Test: `do_derma/tests/test_consent.py`

**Interfaces:**
- Consumes: `Consent Form.custom_derma_procedures` (Task 1).
- Produces:
  - `consent.ENCOUNTER_CONSENT = "Encounter Consent"`, `consent.CONSENT_FORM = "Consent Form"`.
  - `class ConsentDoctype`: attribute `name: str`; properties `is_installed: bool`, `is_encounter_consent: bool`, `procedures_field: str`; methods `set_procedures(doc, procedures: list[dict]) -> None`, `render(doc, procedures: list[dict]) -> None`.
  - `get_selected_procedures(values: dict) -> list[dict]` — rows `{clinical_procedure, procedure_template, display_name}`, distinct by `clinical_procedure`.
  - `validate_procedures(procedures: list[dict], patient: str, encounter: str, encounter_field: str | None) -> None` — throws `frappe.ValidationError`; overwrites each row's `procedure_template` from the database.
  - `get_render_context(doc, procedures: list[dict]) -> dict`.
  - `get_consent_coverage(procedure_names: list[str]) -> dict[str, list[dict]]` — each consent dict has `name, doctype, consent_form_template, status, signed_by, signed_on`.

- [ ] **Step 1: Write the failing tests**

Append to `do_derma/tests/test_consent.py` (merge the imports at the top of the file):

```python
import json

import do_derma.api as api
from do_derma import consent
from do_derma.tests.test_api import DermaTestHelpers

SIGNATURE = "data:image/png;base64,iVBORw0KGgo="
TEMPLATE_HTML = "<p>{{ patient_name }}: {% for row in procedures %}{{ row.display_name }};{% endfor %}</p>"


class ConsentHelpers(DermaTestHelpers):
	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")
		self.consent_doctype = consent.ConsentDoctype()
		if not self.consent_doctype.is_installed:
			self.skipTest("No consent doctype installed.")
		self.patient = self._make_patient()
		self.encounter = self._make_encounter(self.patient)
		self.first = self._make_visit_procedure()
		self.second = self._make_visit_procedure()
		self.template = self._make_consent_template()

	def _make_visit_procedure(self, encounter=None):
		procedure = self._make_clinical_procedure(self.patient)
		procedure.db_set(api._get_clinical_procedure_encounter_field(), (encounter or self.encounter).name)
		return procedure

	def _make_consent_template(self):
		return (
			frappe.get_doc(
				{
					"doctype": "Consent Form Template",
					"title": f"Derma Test {frappe.generate_hash(length=6)}",
					"language": "en",
					"version": 1,
					"template_html": TEMPLATE_HTML,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _payload(self, procedures, **extra):
		return {
			"patient": self.patient,
			"encounter": self.encounter.name,
			"consent_form_template": self.template,
			"signed_by": "Test Patient",
			"signature": SIGNATURE,
			"procedure_items": [
				{"clinical_procedure": row.name, "display_name": f"Shown {row.name}"} for row in procedures
			],
			**extra,
		}

	def _create(self, procedures, **extra):
		return api.create_derma_consent(payload=json.dumps(self._payload(procedures, **extra)))


class TestConsentCoverage(ConsentHelpers, IntegrationTestCase):
	def test_coverage_lists_every_covered_procedure(self):
		third = self._make_visit_procedure()
		created = self._create([self.first, self.second])

		coverage = consent.get_consent_coverage([self.first.name, self.second.name, third.name])

		self.assertEqual([row["name"] for row in coverage[self.first.name]], [created["name"]])
		self.assertEqual([row["name"] for row in coverage[self.second.name]], [created["name"]])
		self.assertNotIn(third.name, coverage)

	def test_an_unsigned_consent_covers_nothing(self):
		self._create([self.first], signature="")
		self.assertEqual(consent.get_consent_coverage([self.first.name]), {})

	def test_a_cancelled_consent_covers_nothing(self):
		created = self._create([self.first])
		frappe.get_doc(created["doctype"], created["name"]).cancel()
		self.assertEqual(consent.get_consent_coverage([self.first.name]), {})

	def test_a_legacy_consent_with_only_its_procedure_link_still_counts(self):
		if not frappe.db.exists("DocType", consent.CONSENT_FORM):
			self.skipTest("Consent Form is not installed.")
		legacy = frappe.get_doc(
			{
				"doctype": consent.CONSENT_FORM,
				"patient": self.patient,
				"clinical_procedure": self.first.name,
				"rendered_html": "<p>legacy</p>",
				"signature": SIGNATURE,
				"signed_by": "Test Patient",
			}
		).insert(ignore_permissions=True)
		legacy.submit()

		coverage = consent.get_consent_coverage([self.first.name])

		self.assertEqual([row["name"] for row in coverage[self.first.name]], [legacy.name])
		self.assertEqual(api.get_derma_consent_html(legacy.name)["rendered_html"], "<p>legacy</p>")

	def test_render_context_joins_the_procedure_names(self):
		doc = frappe.new_doc(self.consent_doctype.name)
		doc.patient = self.patient
		context = consent.get_render_context(doc, [{"display_name": "Laser"}, {"display_name": "Peel"}])
		self.assertEqual(context["procedure_names"], ["Laser", "Peel"])
		self.assertEqual(context["procedure"], "Laser, Peel")
		self.assertEqual(context["procedure_name"], "Laser, Peel")
```

`_create` calls `api.create_derma_consent`, which Task 3 rewires. On this bench the current endpoint already writes the first procedure to `Consent Form.clinical_procedure`, so these tests fail now on the second procedure and on `consent` not existing.

- [ ] **Step 2: Run them and watch them fail**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_consent`
Expected: ERROR, `ImportError: cannot import name 'consent' from 'do_derma'`.

- [ ] **Step 3: Write `do_derma/consent.py`**

```python
from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, now_datetime

ENCOUNTER_CONSENT = "Encounter Consent"
CONSENT_FORM = "Consent Form"
PROCEDURES_FIELD = "custom_derma_procedures"
SUMMARY_FIELDS = ["name", "consent_form_template", "status", "signed_by", "signed_on"]


class ConsentDoctype:
	"""The consent doctype this site writes: do_dental's Encounter Consent when installed, else Consent Form."""

	def __init__(self):
		self.name = ENCOUNTER_CONSENT if frappe.db.exists("DocType", ENCOUNTER_CONSENT) else CONSENT_FORM

	@property
	def is_installed(self) -> bool:
		return bool(frappe.db.exists("DocType", self.name))

	@property
	def is_encounter_consent(self) -> bool:
		return self.name == ENCOUNTER_CONSENT

	@property
	def procedures_field(self) -> str:
		return "procedure_items" if self.is_encounter_consent else PROCEDURES_FIELD

	def set_procedures(self, doc, procedures: list[dict[str, Any]]) -> None:
		for row in procedures:
			doc.append(self.procedures_field, row)
		if procedures and not self.is_encounter_consent:
			doc.clinical_procedure = procedures[0]["clinical_procedure"]
			doc.procedure_template = procedures[0].get("procedure_template")

	def render(self, doc, procedures: list[dict[str, Any]]) -> None:
		if self.is_encounter_consent:
			doc.render_template()
			return
		template = frappe.get_doc("Consent Form Template", doc.consent_form_template)
		doc.rendered_html = frappe.render_template(
			template.template_html or "", get_render_context(doc, procedures)
		)


def get_selected_procedures(values: dict[str, Any]) -> list[dict[str, Any]]:
	"""The payload's procedures, one row per distinct Clinical Procedure."""
	selected: dict[str, dict[str, Any]] = {}
	for row in values.get("procedure_items") or values.get("procedure_selection") or []:
		if isinstance(row, str):
			row = {"clinical_procedure": row}
		name = cstr(row.get("clinical_procedure") or row.get("value")).strip()
		if name and name not in selected:
			selected[name] = {
				"clinical_procedure": name,
				"procedure_template": row.get("procedure_template"),
				"display_name": row.get("display_name") or row.get("label") or name,
			}
	return list(selected.values())


def validate_procedures(
	procedures: list[dict[str, Any]], patient: str, encounter: str, encounter_field: str | None
) -> None:
	"""Every procedure must be a live one from this patient's visit."""
	if not procedures:
		frappe.throw(_("Select at least one procedure for this consent."), frappe.ValidationError)
	filters: dict[str, Any] = {
		"name": ["in", [row["clinical_procedure"] for row in procedures]],
		"patient": patient,
		"docstatus": ["<", 2],
	}
	if encounter_field:
		filters[encounter_field] = encounter
	templates = dict(
		frappe.get_all("Clinical Procedure", filters=filters, fields=["name", "procedure_template"], as_list=True)
	)
	foreign = [row["clinical_procedure"] for row in procedures if row["clinical_procedure"] not in templates]
	if foreign:
		frappe.throw(
			_("These procedures are not part of this visit: {0}").format(", ".join(foreign)),
			frappe.ValidationError,
		)
	for row in procedures:
		row["procedure_template"] = templates[row["clinical_procedure"]]


def get_render_context(doc, procedures: list[dict[str, Any]]) -> dict[str, Any]:
	"""Keys used by both do_health's Consent Form and do_dental's Encounter Consent templates."""
	patient = frappe.get_cached_doc("Patient", doc.patient).as_dict() if doc.get("patient") else frappe._dict()
	names = [row["display_name"] for row in procedures if row.get("display_name")]
	joined = ", ".join(names) or doc.get("procedure_template")
	return {
		"doc": doc,
		"patient": patient,
		"patient_name": patient.get("patient_name"),
		"encounter": doc.get("encounter"),
		"appointment": doc.get("appointment"),
		"company": doc.get("company"),
		"date": now_datetime(),
		"procedures": procedures,
		"procedure_names": names,
		"procedure": joined,
		"procedure_name": joined,
	}


def get_consent_coverage(procedure_names: list[str]) -> dict[str, list[dict[str, Any]]]:
	"""Signed consents covering each procedure, from every consent shape installed."""
	coverage: dict[str, list[dict[str, Any]]] = {}
	if not procedure_names:
		return coverage
	for doctype, links in get_consent_links(procedure_names).items():
		signed = frappe.get_all(
			doctype,
			filters={"name": ["in", list({parent for _procedure, parent in links})], "docstatus": 1},
			fields=SUMMARY_FIELDS,
		)
		by_name = {row.name: {**row, "doctype": doctype} for row in signed}
		for procedure, parent in sorted(links):
			found = by_name.get(parent)
			if found and found not in coverage.get(procedure, []):
				coverage.setdefault(procedure, []).append(found)
	return coverage


def get_consent_links(procedure_names: list[str]) -> dict[str, set[tuple[str, str]]]:
	"""(procedure, consent) pairs per consent doctype, signed or not."""
	links: dict[str, set[tuple[str, str]]] = {}
	for doctype, child_doctype, fieldname in get_procedure_tables():
		rows = frappe.get_all(
			child_doctype,
			filters={"parenttype": doctype, "parentfield": fieldname, "clinical_procedure": ["in", procedure_names]},
			fields=["clinical_procedure", "parent"],
		)
		links.setdefault(doctype, set()).update((row.clinical_procedure, row.parent) for row in rows)
	if frappe.db.exists("DocType", CONSENT_FORM):
		rows = frappe.get_all(
			CONSENT_FORM,
			filters={"clinical_procedure": ["in", procedure_names]},
			fields=["clinical_procedure", "name"],
		)
		links.setdefault(CONSENT_FORM, set()).update((row.clinical_procedure, row.name) for row in rows)
	return links


def get_procedure_tables() -> list[tuple[str, str, str]]:
	"""(consent doctype, child doctype, table field) for every consent procedure table installed."""
	tables = []
	for doctype, fieldname in ((ENCOUNTER_CONSENT, "procedure_items"), (CONSENT_FORM, PROCEDURES_FIELD)):
		if not frappe.db.exists("DocType", doctype):
			continue
		field = frappe.get_meta(doctype).get_field(fieldname)
		if field:
			tables.append((doctype, field.options, fieldname))
	return tables
```

- [ ] **Step 4: Run the render-context test (the others need Task 3)**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_consent --test test_render_context_joins_the_procedure_names`
Expected: `Ran 1 test ... OK`. The coverage tests still fail on the second procedure until Task 3.

- [ ] **Step 5: Lint and commit**

```bash
pipx run ruff check do_derma/consent.py do_derma/tests/test_consent.py
git add do_derma/consent.py do_derma/tests/test_consent.py
git commit -m "feat(consent): consent doctype, render context and coverage helpers"
```

---

### Task 3: Consent endpoints write every procedure

**Files:**
- Modify: `do_derma/api.py` — import line 14; `get_derma_consents` (≈3378-3402, delete); `create_derma_consent` (≈3405-3496); `render_derma_consent_preview` (≈3498-3532); `get_derma_consent_html` (≈3534-3556)
- Test: `do_derma/tests/test_consent.py`, existing `do_derma/tests/test_encounter_tabs.py::TestConsentPreview`

**Interfaces:**
- Consumes: everything Task 2 produces.
- Produces: `create_derma_consent(payload)` returns `{name, doctype, rendered_html, status, docstatus, created_on}` (unchanged); `render_derma_consent_preview(payload)` returns `{rendered_html[, error]}` (unchanged).

- [ ] **Step 1: Write the failing tests**

Append to `do_derma/tests/test_consent.py`:

```python
class TestCreateConsent(ConsentHelpers, IntegrationTestCase):
	def _stored_procedures(self, name):
		doc = frappe.get_doc(self.consent_doctype.name, name)
		return [row.clinical_procedure for row in doc.get(self.consent_doctype.procedures_field)]

	def test_one_consent_covers_every_selected_procedure(self):
		created = self._create([self.first, self.second])
		self.assertEqual(self._stored_procedures(created["name"]), [self.first.name, self.second.name])
		self.assertEqual(created["docstatus"], 1)

	def test_consent_form_keeps_the_first_procedure_on_its_own_link(self):
		if self.consent_doctype.is_encounter_consent:
			self.skipTest("Encounter Consent has no single procedure link.")
		created = self._create([self.first, self.second])
		self.assertEqual(
			frappe.db.get_value(consent.CONSENT_FORM, created["name"], "clinical_procedure"), self.first.name
		)

	def test_a_procedure_picked_twice_is_stored_once(self):
		created = self._create([self.first, self.first])
		self.assertEqual(self._stored_procedures(created["name"]), [self.first.name])

	def test_a_consent_needs_at_least_one_procedure(self):
		with self.assertRaises(frappe.ValidationError):
			self._create([])

	def test_a_procedure_from_another_visit_is_refused(self):
		other = self._make_visit_procedure(self._make_encounter(self.patient))
		with self.assertRaises(frappe.ValidationError):
			self._create([self.first, other])

	def test_renders_every_selected_procedure(self):
		created = self._create([self.first, self.second])
		html = frappe.db.get_value(created["doctype"], created["name"], "rendered_html")
		self.assertIn(f"Shown {self.first.name};", html)
		self.assertIn(f"Shown {self.second.name};", html)

	def test_preview_renders_the_selected_procedures(self):
		result = api.render_derma_consent_preview(payload=json.dumps(self._payload([self.first, self.second])))
		self.assertIn(f"Shown {self.first.name};Shown {self.second.name};", result["rendered_html"])
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_consent`
Expected: FAIL on `test_one_consent_covers_every_selected_procedure` (empty table), `test_a_consent_needs_at_least_one_procedure` (no error raised), `test_a_procedure_from_another_visit_is_refused`, and the coverage tests.

- [ ] **Step 3: Rewire the endpoints**

In `api.py` line 14 change the import to:

```python
from do_derma import assessment, consent, previous_visits, reopen, voice
```

Delete `get_derma_consents` entirely (its only caller, the Consent tab, goes in Task 7; do_dental uses its own `get_encounter_consents`). Confirm with `grep -rn get_derma_consents do_derma` that only `DermaChart.vue:2225` remains, which Task 7 removes.

Replace the body of `create_derma_consent` from `doctype = "Encounter Consent" if ...` down to `doc.insert(ignore_permissions=True)` with:

```python
	consent_doctype = consent.ConsentDoctype()
	if not consent_doctype.is_installed:
		frappe.throw(_("Consent Form is not installed."))
	procedures = consent.get_selected_procedures(values)
	consent.validate_procedures(procedures, patient, encounter, _get_clinical_procedure_encounter_field())

	doc = frappe.new_doc(consent_doctype.name)
	for fieldname, value in {
		"patient": patient,
		"encounter": encounter,
		"appointment": appointment,
		"consent_form_template": values.get("consent_form_template"),
		"company": values.get("company") or frappe.defaults.get_user_default("Company"),
		"signature": values.get("signature"),
		"signed_by": values.get("signed_by"),
		"relationship": values.get("relationship"),
	}.items():
		if value and _has_field(consent_doctype.name, fieldname):
			doc.set(fieldname, value)
	consent_doctype.set_procedures(doc, procedures)

	if doc.get("consent_form_template"):
		consent_doctype.render(doc, procedures)
	if values.get("rendered_html") and _has_field(consent_doctype.name, "rendered_html"):
		doc.rendered_html = values.get("rendered_html")

	doc.insert(ignore_permissions=True)
```

and in its return dict change `"doctype": doctype` to `"doctype": consent_doctype.name`.

Replace `render_derma_consent_preview` from `doctype = ...` to the end with:

```python
	consent_doctype = consent.ConsentDoctype()
	if not consent_doctype.is_installed:
		return {"rendered_html": ""}
	procedures = consent.get_selected_procedures(values)
	doc = frappe.new_doc(consent_doctype.name)
	for fieldname, value in {
		"patient": values.get("patient"),
		"encounter": values.get("encounter"),
		"appointment": values.get("appointment"),
		"consent_form_template": consent_template,
		"company": values.get("company") or frappe.defaults.get_user_default("Company"),
	}.items():
		if value and _has_field(consent_doctype.name, fieldname):
			doc.set(fieldname, value)
	consent_doctype.set_procedures(doc, procedures)
	try:
		consent_doctype.render(doc, procedures)
	except Exception as exc:
		# Name the template so an administrator can fix it instead of the clinician retrying.
		frappe.log_error(frappe.get_traceback(), "Derma consent preview render failed")
		return {
			"rendered_html": "",
			"error": _("Consent template {0} could not be rendered: {1}").format(
				consent_template, str(exc) or exc.__class__.__name__
			),
		}
	return {"rendered_html": doc.get("rendered_html") or ""}
```

In `get_derma_consent_html` replace the `doctype = (...)` expression with:

```python
	doctype = consent.ConsentDoctype().name
	if not frappe.db.exists(doctype, name):
		doctype = consent.CONSENT_FORM
```

- [ ] **Step 4: Run the new and the existing consent tests**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_consent && bench --site dermaone.localhost run-tests --module do_derma.tests.test_encounter_tabs`
Expected: `test_consent` all OK; `test_encounter_tabs` OK including `test_a_template_that_cannot_render_returns_an_error_naming_it` (a missing template now raises `DoesNotExistError` inside `render`, still named in the error).

- [ ] **Step 5: Lint and commit**

```bash
pipx run ruff check do_derma/consent.py do_derma/tests/test_consent.py
git add do_derma/api.py do_derma/tests/test_consent.py
git commit -m "feat(consent): one consent covers every selected procedure"
```

---

### Task 4: Chart procedure rows carry consent state; covered procedures cannot be deleted

**Files:**
- Modify: `do_derma/api.py` — `_get_derma_procedures` (≈1666-1727); `delete_clinical_procedure_entry` (≈3613-3625)
- Test: `do_derma/tests/test_consent.py`

**Interfaces:**
- Consumes: `consent.get_consent_coverage`.
- Produces: each row from `_get_derma_procedures` (and so `get_patient_derma_chart().procedures`) has `consents: list[dict]` and `consent_required: int`.

- [ ] **Step 1: Write the failing tests**

Append to `do_derma/tests/test_consent.py`:

```python
class TestChartConsentState(ConsentHelpers, IntegrationTestCase):
	def _rows(self):
		rows = api._get_derma_procedures(self.patient, encounter=self.encounter.name)
		return {row["name"]: row for row in rows}

	def test_rows_list_the_consents_covering_them(self):
		created = self._create([self.first])
		rows = self._rows()
		self.assertEqual([row["name"] for row in rows[self.first.name]["consents"]], [created["name"]])
		self.assertEqual(rows[self.second.name]["consents"], [])

	def test_rows_say_whether_their_template_requires_consent(self):
		fieldname = "custom_derma_consent_required"
		template = self.first.procedure_template
		previous = frappe.db.get_value("Clinical Procedure Template", template, fieldname)
		self.addCleanup(frappe.db.set_value, "Clinical Procedure Template", template, fieldname, previous)
		frappe.db.set_value("Clinical Procedure Template", template, fieldname, 1)

		self.assertEqual(self._rows()[self.first.name]["consent_required"], 1)

	def test_a_covered_procedure_cannot_be_deleted(self):
		self._create([self.first])
		with self.assertRaisesRegex(frappe.ValidationError, "signed consent covers"):
			api.delete_clinical_procedure_entry("Clinical Procedure", self.first.name)
		self.assertTrue(frappe.db.exists("Clinical Procedure", self.first.name))
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_consent`
Expected: `KeyError: 'consents'`, `KeyError: 'consent_required'`, and the delete test failing: either nothing is raised, or Frappe's own `LinkExistsError` (a `ValidationError` subclass) fires without the "signed consent covers" message. do_health's delete handlers may skip that link check, so the explicit guard is still needed.

- [ ] **Step 3: Enrich the rows**

In `_get_derma_procedures`, extend the template fields list to
`["name", "template", "custom_derma_category", "custom_derma_consent_required"]`, and inside the `if template:` block add:

```python
				row["consent_required"] = cint(template.get("custom_derma_consent_required"))
```

Replace the tail

```python
	if procedure_names:
		_enrich_derma_procedure_rows(rows, procedure_names)
	return rows
```

with

```python
	if procedure_names:
		_enrich_derma_procedure_rows(rows, procedure_names)
	coverage = consent.get_consent_coverage(procedure_names)
	for row in rows:
		row.setdefault("consent_required", 0)
		row["consents"] = coverage.get(row.get("name"), [])
	return rows
```

- [ ] **Step 4: Guard the delete**

In `delete_clinical_procedure_entry`, directly before `frappe.delete_doc(doctype, name, ignore_permissions=True)`:

```python
	if consent.get_consent_coverage([name]).get(name):
		frappe.throw(
			_("A signed consent covers this procedure, so it cannot be deleted."), frappe.ValidationError
		)
```

- [ ] **Step 5: Run the tests**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --module do_derma.tests.test_consent && bench --site dermaone.localhost run-tests --module do_derma.tests.test_procedure_teardown`
Expected: both OK.

- [ ] **Step 6: Commit**

```bash
git add do_derma/api.py do_derma/tests/test_consent.py
git commit -m "feat(consent): procedure rows carry consent state; covered procedures stay"
```

---

### Task 5: ConsentPanel becomes the overlay form

**Files:**
- Modify: `do_derma/public/js/chart/components/ConsentPanel.vue`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: component props `saving, sending, error, hasSessionContext, procedureOptions, preselected: string[], previewHtml, previewLoading, defaultSignedBy, resetKey, readOnly, enableWhatsappConsent`; emits `request-preview({consent_form_template, procedure_selection})`, `create({...values, rendered_html})`, `send-whatsapp(...)`, `cancel()`. `procedure_selection` is an array of Clinical Procedure names. Props `loading`, `encounterName`, `consents` and emits `open-consent`, `resend-consent`, `cancel-consent` are removed.

No JS unit-test harness exists in this repo; Task 8's browser check covers this component.

- [ ] **Step 1: Template**

Replace the `<header class="panel-header">…</header>` block's opening so it reads:

```html
    <header class="panel-header">
      <h3>{{ __("New Consent") }}</h3>
      <div class="actions">
        <button type="button" class="ghost" data-test="consent-cancel" :disabled="saving" @click="emitCancel">
          {{ __("Cancel") }}
        </button>
```

(keep the existing WhatsApp and Create buttons that follow; change both `:disabled` expressions from `loading || saving || sending || !canCreate` to `saving || sending || !canCreate`).

Delete the `<div v-if="loading" …>Loading consents…</div>` line and make the next line `<div v-if="!hasSessionContext" class="empty-state">`.

Replace `<div class="field-host" :ref="(el) => bindHost('procedure_selection', el)"></div>` with:

```html
          <fieldset class="procedure-checklist" data-test="consent-procedures">
            <legend>{{ __("Procedures") }}</legend>
            <label v-for="option in procedureOptions" :key="option.value" class="procedure-option">
              <input
                v-model="selectedProcedures"
                type="checkbox"
                :value="option.value"
                :disabled="readOnly"
                @change="handleProcedureChange"
              />
              <span class="name">{{ option.label }}</span>
              <span v-if="option.description" class="meta">{{ option.description }}</span>
            </label>
            <p v-if="!procedureOptions.length" class="text-muted">{{ __("No procedures on this visit.") }}</p>
          </fieldset>
```

Delete the whole `<div class="history-column">…</div>` block.

- [ ] **Step 2: Script**

- `defineProps`: remove `loading`, `encounterName`, `consents`; add `preselected: { type: Array, default: () => [] },`.
- `defineEmits(["request-preview", "create", "send-whatsapp", "cancel"])`.
- Add `const selectedProcedures = ref([...props.preselected])` after `formFieldValues`, and drop `procedure_selection` from `localValues`' initial object.
- Delete the `watch(() => props.procedureOptions, …)` block and the functions `normalizeSelection`, `syncProcedureOptions`, `bindProcedureChangeEvents`, `consentMeta`, `canManageRemote`.
- In `controlDef` delete the `procedure_selection` branch. In `renderControls` loop over `["consent_form_template"]` only, delete the `if (fieldname === "procedure_selection") bindProcedureChangeEvents(control)` lines and the trailing `syncProcedureOptions()` call.
- `resetDraft`: replace the `procedure_selection: []` entry and the whole `procedureControl` block with `selectedProcedures.value = [...props.preselected]`.
- `readValues`: replace the `selection` line with `const selection = [...selectedProcedures.value]` (keep `procedure_selection: selection` in the returned object).
- In `emitCreate`, after the template check:

```js
  if (!values.procedure_selection.length) {
    frappe.show_alert({ message: __("Select at least one procedure."), indicator: "orange" })
    return
  }
```

and change its guard to `if (!canCreate.value || props.saving) return`; in `emitSend` drop `props.loading ||`.
- Add:

```js
function emitCancel() {
  if (!formFieldValues.value.signature) return emit("cancel")
  frappe.confirm(__("Discard this signed consent draft?"), () => emit("cancel"))
}
```

- [ ] **Step 3: Styles**

In `<style scoped>`: delete the `.history-column` rules (the `position: sticky` block, the `.history-column` selectors inside the shared rules and the `@media` block), all `.consent-list`, `.consent-row*` rules; change `.document-grid` to `grid-template-columns: minmax(0, 1fr);`; change `.panel-header` `justify-content: end` to `justify-content: space-between`; add:

```css
.procedure-checklist {
  display: grid;
  gap: 6px;
  min-width: 0;
  margin: 0 0 10px;
  padding: 0;
  border: 0;
}

.procedure-checklist legend {
  margin-bottom: 4px;
  color: #475569;
  font-size: 11px;
  font-weight: 800;
}

.procedure-option {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 8px;
  align-items: baseline;
  font-size: 13px;
  color: #0f172a;
}

.procedure-option .meta {
  grid-column: 2;
  font-size: 12px;
  color: #64748b;
}
```

- [ ] **Step 4: Check nothing still names removed symbols**

Run: `grep -nE "procedure_selection'|bindProcedureChangeEvents|syncProcedureOptions|normalizeSelection|consentMeta|canManageRemote|history-column|props\.loading|props\.consents" do_derma/public/js/chart/components/ConsentPanel.vue`
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add do_derma/public/js/chart/components/ConsentPanel.vue
git commit -m "refactor(consent): ConsentPanel becomes a procedure-scoped overlay form"
```

---

### Task 6: Procedures tab — New Consent button and row badges

**Files:**
- Modify: `do_derma/public/js/chart/components/ProcedurePanel.vue` (header ≈49-66, status cell ≈209-215, `defineEmits` ≈537, `<style scoped>` from ≈1847)

**Interfaces:**
- Consumes: row fields `consents`, `consent_required` (Task 4).
- Produces: emits `new-consent(row?)` and `open-consents(row)`.

- [ ] **Step 1: Button**

Insert before the `data-test="procedure-new"` button:

```html
        <button
          type="button"
          class="ghost small"
          data-test="procedure-new-consent"
          :disabled="readOnly || !totalCount"
          @click="emit('new-consent')"
        >
          {{ __("New Consent") }}
        </button>
```

- [ ] **Step 2: Badges**

In the status `<td>`, after the closing `</span>` of the `pill`:

```html
                <button
                  v-if="row.consents?.length"
                  type="button"
                  class="consent-badge consented"
                  data-test="procedure-consent-badge"
                  @click.stop="emit('open-consents', row)"
                >
                  {{ row.consents.length > 1 ? __("Consented ({0})", [row.consents.length]) : __("Consented") }}
                </button>
                <button
                  v-else-if="row.consent_required && row.docstatus !== 2"
                  type="button"
                  class="consent-badge needed"
                  data-test="procedure-consent-needed"
                  :disabled="readOnly"
                  @click.stop="emit('new-consent', row)"
                >
                  {{ __("Consent needed") }}
                </button>
```

- [ ] **Step 3: Emits and styles**

Add `"new-consent"` and `"open-consents"` to `defineEmits`. Append inside `<style scoped>`:

```css
.consent-badge {
  display: block;
  margin-top: 4px;
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.consent-badge.consented {
  border: 1px solid #a7f3d0;
  background: #ecfdf5;
  color: #047857;
}

.consent-badge.needed {
  border: 1px solid #fcd34d;
  background: #fffbeb;
  color: #b45309;
}

.consent-badge:disabled {
  cursor: default;
  opacity: 0.7;
}
```

- [ ] **Step 4: Commit**

```bash
git add do_derma/public/js/chart/components/ProcedurePanel.vue
git commit -m "feat(consent): New Consent button and consent badges on procedure rows"
```

---

### Task 7: DermaChart — drop the tab, host the overlay

**Files:**
- Modify: `do_derma/public/js/chart/DermaChart.vue`
- Modify: `do_derma/public/js/chart/derma_chart.bundle.css`

**Interfaces:**
- Consumes: ConsentPanel props/emits (Task 5), ProcedurePanel emits (Task 6), row fields (Task 4).

- [ ] **Step 1: Tabs and aliases**

Delete `{ key: "consent", label: __("Consent"), hint: __("Forms") },` from `SECTION_TABS`. In `SECTION_ALIASES` replace `consents: "consent",` with:

```js
  consent: "procedures",
  consents: "procedures",
```

- [ ] **Step 2: State**

Replace the `consentPanel` reactive with:

```js
const consentPanel = reactive({
  open: false,
  preselected: [],
  saving: false,
  sending: false,
  error: "",
  previewHtml: "",
  previewLoading: false,
  resetKey: 0,
})
```

Remove `consents: false,` from `loadedTabs`.

- [ ] **Step 3: Remove the tab's loading paths**

Delete: the `if (normalized === "consent") { await loadConsentPanel(); return }` block (≈1121); the line `if (encounter.value.name) await loadConsentPanel(true)` (≈1165); the line `if (tab === "consents") return loadConsentPanel(force)` (≈1430); the whole `loadConsentPanel` function (≈2220-2234); `resendConsentViaWhatsApp` and `cancelRemoteConsent`.

Replace the `<ConsentPanel v-else-if="activeSection === 'consent'" … />` block (≈303-326) with nothing, and add the overlay directly after the `<ProcedurePanel … />` element (≈262):

```html
              <div v-if="consentPanel.open" class="consent-overlay" data-test="consent-overlay">
                <div class="consent-overlay-card" role="dialog" aria-modal="true" :aria-label="__('New Consent')">
                  <ConsentPanel
                    :saving="consentPanel.saving"
                    :sending="consentPanel.sending"
                    :error="consentPanel.error"
                    :has-session-context="hasSessionContext"
                    :procedure-options="consentProcedureOptions"
                    :preselected="consentPanel.preselected"
                    :preview-html="consentPanel.previewHtml"
                    :preview-loading="consentPanel.previewLoading"
                    :default-signed-by="patient.patient_name || patient.name"
                    :reset-key="consentPanel.resetKey"
                    :read-only="isEncounterLocked"
                    :enable-whatsapp-consent="!!featureToggles.enable_whatsapp_consent"
                    @request-preview="requestConsentPreview"
                    @create="createConsentFromPanel"
                    @send-whatsapp="sendConsentViaWhatsApp"
                    @cancel="consentPanel.open = false"
                  />
                </div>
              </div>
```

On `<ProcedurePanel>` add:

```html
                @new-consent="openNewConsent"
                @open-consents="openProcedureConsents"
```

- [ ] **Step 4: Options, pending list and alert**

Change `consentProcedureOptions` to start `procedures.value.filter((row) => row.docstatus !== 2).map((row) => {` (body unchanged). Add after it:

```js
const consentPendingProcedures = computed(() =>
  procedures.value.filter((row) => row.consent_required && row.docstatus !== 2 && !(row.consents || []).length)
)
```

Replace the alert block that tests `selectedTemplate.value?.custom_derma_consent_required` with:

```js
  if (consentPendingProcedures.value.length) {
    alerts.push({
      key: "consent",
      label: __("Consent Required"),
      detail: consentPendingProcedures.value.map(procedureDisplayName).join(", "),
      tone: "warning",
    })
  }
```

In `handleEncounterAlert` change `setActiveSection("consent")` to `setActiveSection("procedures")`.

- [ ] **Step 5: Open, create, view**

Add next to `requestConsentPreview`:

```js
function openNewConsent(row = null) {
  consentPanel.preselected = row ? [row.name] : consentPendingProcedures.value.map((item) => item.name)
  consentPanel.previewHtml = ""
  consentPanel.error = ""
  consentPanel.resetKey += 1
  consentPanel.open = true
}

function openProcedureConsents(row) {
  const consents = row?.consents || []
  if (consents.length === 1) return openSignedConsent(consents[0])
  const dialog = new frappe.ui.Dialog({
    title: __("Consents for {0}", [procedureDisplayName(row)]),
    fields: [
      {
        fieldname: "consent",
        fieldtype: "Select",
        label: __("Consent"),
        reqd: 1,
        options: consents.map((item) => ({
          value: item.name,
          label: [item.consent_form_template || item.name, item.signed_on].filter(Boolean).join(" · "),
        })),
      },
    ],
    primary_action_label: __("Open"),
    primary_action(values) {
      dialog.hide()
      openSignedConsent(consents.find((item) => item.name === values.consent))
    },
  })
  dialog.show()
  nameDialogControls(dialog)
}
```

In `createConsentFromPanel`, replace

```js
    if (response.message?.name) openSignedConsent({ name: response.message.name })
    loadedTabs.consents = false
    await loadConsentPanel(true)
    consentPanel.previewHtml = ""
    consentPanel.resetKey += 1
```

with

```js
    consentPanel.open = false
    consentPanel.previewHtml = ""
    await refresh()
    if (response.message?.name) openSignedConsent({ name: response.message.name })
```

- [ ] **Step 6: Overlay styles**

Check the file ends outside any `@media` block (`tail -20 do_derma/public/js/chart/derma_chart.bundle.css`; memory `derma-chart-css-traps`), then append:

```css
.dental-chart-page .consent-overlay {
  position: fixed;
  inset: 0;
  z-index: 1040;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 4vh 16px;
  overflow: auto;
  background: rgba(15, 23, 42, 0.45);
}

.dental-chart-page .consent-overlay-card {
  width: min(1100px, 100%);
}
```

- [ ] **Step 7: Check nothing still names removed symbols**

Run: `grep -nE "loadConsentPanel|loadedTabs\.consents|consentPanel\.(loading|consents|encounter)|resendConsentViaWhatsApp|cancelRemoteConsent|activeSection === 'consent'|get_derma_consents" do_derma/public/js/chart/DermaChart.vue`
Expected: no output.

- [ ] **Step 8: Build and commit**

Run: `cd /Users/hameed/Developer/bench-v16 && bench build --app do_derma`
Expected: build succeeds with no Vue compile errors.

```bash
git add do_derma/public/js/chart/DermaChart.vue do_derma/public/js/chart/derma_chart.bundle.css
git commit -m "feat(consent): create consents from the Procedures tab; drop the Consent tab"
```

---

### Task 8: Verify

- [ ] **Step 1: Full suite, diffed against main**

Run: `cd /Users/hameed/Developer/bench-v16 && bench --site dermaone.localhost run-tests --app do_derma 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s"`
Expected: the failing names are a subset of the `main` baseline in memory `bench-v16-test-and-lint-quirks`; nothing from `test_consent`, `test_encounter_tabs` or `test_procedure_teardown`.

- [ ] **Step 2: Browser check on dermaone**

Restart the web server after the build (assets 404 otherwise), get a login URL with `bench --site dermaone.localhost browse --user Administrator`, open a patient's derma chart with at least two draft procedures, one of whose template has Consent Required, then confirm:

1. No Consent tab. Set `localStorage.do_derma_chart_last_section = "consent"`, reload: the chart lands on Procedures.
2. The consent-required procedure shows **Consent needed**; the header alert names it and its click opens Procedures.
3. **New Consent** opens the overlay with that procedure pre-ticked; tick a second one; pick a template; the preview re-renders.
4. Create without a signature: blocked with the alert. Sign, Create: overlay closes, both rows show **Consented**, the signed consent opens.
5. Click **Consented** on a row: the consent opens. Create a second consent over the same row: the badge reads **Consented (2)** and the click offers both.
6. Delete the covered draft procedure: the refusal message shows and the row stays.
7. Cancel with a signature drawn: confirmation appears.

- [ ] **Step 3: Record results**

Report the suite diff and each browser item's result to the user. Fix any failure before finishing.
