"""A patient part-way through a course of treatment, so every tab of the Derma
Chart has something real in it. Run via::

    bench --site dermaone.localhost execute do_derma.demo_seed.setup_demo_data
    bench --site dermaone.localhost execute do_derma.demo_seed.teardown_demo_data

This is **not** the Playwright fixture set. ``e2e_seed.py`` is deliberately
minimal because 40 specs assert exact counts against it; anything added there to
make manual testing nicer breaks them. Everything here is prefixed ``DEMO `` so
the two sets can never be confused, and ``teardown_demo_data`` removes all of it.

Two properties, mirroring ``e2e_seed.py`` and ``patches.txt``:

1. **Idempotent.** Every helper is check-then-act, so re-running creates no
   duplicates and repairs a half-finished run.
2. **Schema-defensive.** It runs on sites where an optional doctype or
   ``custom_*`` field never migrated, reusing ``api._has_doctype`` /
   ``api._has_field`` rather than assuming.

Clinical detail is written through the real endpoints (``save_chart_mark``,
``save_derma_annotation``, ``create_derma_chart_procedure``) rather than by
inserting documents, so the seeded rows are shaped exactly the way the app
shapes them - and a broken endpoint fails the seed rather than producing data
the chart cannot read.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import frappe
from frappe.utils import add_days, nowdate, nowtime

import do_derma.api as api
from do_derma.e2e_seed import solid_png

DEMO_PREFIX = "DEMO "

PATIENT_FIRST_NAME = "DEMO Amina Haddad"
PRACTITIONER_FIRST_NAME = "DEMO Dr Farah Nasser"
APPOINTMENT_TYPE = "DEMO Derma Consultation"
ITEM_GROUP = "DEMO Derma"
PROCEDURE_CATEGORY = "DEMO Aesthetics"
BODY_TEMPLATE = "DEMO Face Map"
CONSENT_TEMPLATE = "DEMO Consent"

BODY_TEMPLATE_IMAGE = ("demo-face-map.png", 600, 800, (238, 228, 220))
PHOTO_IMAGES = (("demo-photo-before.png", (214, 178, 168)), ("demo-photo-after.png", (226, 208, 200)))


def _rectangle_outline(left: float, top: float, width: float, height: float) -> list[list[float]]:
	"""A closed polygon in template-relative 0..1 coordinates.

	The Body Map Designer writes exactly this shape (`body-template-editor.bundle.jsx`) and the
	chart's `parsePartPoints` reads only this shape - an `{x, y, width, height}` object is
	silently dropped, leaving the template with areas that never draw.
	"""
	right, bottom = left + width, top + height
	return [[left, top], [right, top], [right, bottom], [left, bottom], [left, top]]


BODY_PARTS = (
	("DEMO Forehead", _rectangle_outline(0.30, 0.10, 0.40, 0.14)),
	("DEMO Left Cheek", _rectangle_outline(0.12, 0.38, 0.26, 0.20)),
	("DEMO Right Cheek", _rectangle_outline(0.62, 0.38, 0.26, 0.20)),
	("DEMO Chin", _rectangle_outline(0.38, 0.74, 0.24, 0.14)),
)

# An area someone removed from the map last week. It is soft-disabled, not deleted, so
# the designer's "Retired areas" list has a row to restore.
RETIRED_BODY_PART = ("DEMO Old Jawline", _rectangle_outline(0.24, 0.62, 0.52, 0.10))

AREA_VARIABLE = {"variable_name": "Severity", "type": "Select", "options": "Mild\nModerate\nSevere"}

TEMPLATE_VARIABLES = [
	{"variable_name": "Product", "fieldname": "product", "label": "Product", "type": "Data"},
	{"variable_name": "Units", "fieldname": "units", "label": "Units", "type": "Float"},
	{
		"variable_name": "Plane",
		"fieldname": "plane",
		"label": "Plane",
		"type": "Select",
		"options": "Subdermal\nSupraperiosteal\nIntradermal",
	},
]

# (template, marker behaviour, colour, category override). The three placement
# paths that placementToolFor() routes - point stamp, drag rectangle, pen - plus
# two categories that prove the Derma Treatment Entry procedure_type mapping:
# "Biopsy" is one of the Select's options and survives, "DEMO Aesthetics" is not
# and lands on "Other" (api._treatment_procedure_type).
PROCEDURE_TEMPLATES = (
	("DEMO Botox Glabella", "numbered_dot", "#c0392b", None),
	("DEMO Filler Cheek", "numbered_dot", "#8e44ad", None),
	("DEMO Peel Full Face", "area", "#d35400", None),
	("DEMO Laser Resurfacing", "freehand", "#0e7490", None),
	("DEMO Punch Biopsy", "x_mark", "#16a085", "Biopsy"),
)

# Three visits: two in the past to give the timeline, the history strip and
# "Copy marks from last visit" something to work with, and today's draft. The last
# element of a mark is the area it sits on and what was typed there, or None for a
# mark placed off every area.
VISITS = (
	{
		"key": "visit_1",
		"days_ago": 62,
		"mode": "SOAP",
		"marks": (
			(
				"DEMO Botox Glabella",
				50.0,
				18.0,
				{"product_name": "Botulinum A", "dose": 20, "dose_unit": "Units"},
				("DEMO Forehead", {"Severity": "Moderate"}),
			),
			(
				"DEMO Botox Glabella",
				38.0,
				22.0,
				{"product_name": "Botulinum A", "dose": 12, "dose_unit": "Units"},
				("DEMO Forehead", {"Severity": "Mild"}),
			),
			(
				"DEMO Filler Cheek",
				22.0,
				46.0,
				{"product_name": "HA Filler", "dose": 1.0, "dose_unit": "ml"},
				("DEMO Left Cheek", {"Severity": "Severe"}),
			),
		),
	},
	{
		"key": "visit_2",
		"days_ago": 31,
		"mode": "Structured",
		"marks": (
			("DEMO Peel Full Face", 50.0, 44.0, {"status": "Improving", "severity": "Mild"}, None),
			(
				"DEMO Punch Biopsy",
				74.0,
				40.0,
				{"status": "Biopsied", "diagnosis": "Seborrhoeic keratosis"},
				("DEMO Right Cheek", {"Severity": "Moderate"}),
			),
		),
	},
	{
		"key": "current",
		"days_ago": 0,
		"mode": None,
		"marks": (
			(
				"DEMO Filler Cheek",
				24.0,
				47.0,
				{"product_name": "HA Filler", "dose": 0.5, "dose_unit": "ml"},
				# Left blank on purpose: a declared variable with no value is documented
				# as "looked at, nothing to record", not as missing.
				("DEMO Left Cheek", {"Severity": ""}),
			),
			("DEMO Laser Resurfacing", 62.0, 56.0, {"status": "Active", "severity": "Moderate"}, None),
		),
	},
)

SOAP_NOTE = {
	"custom_derma_soap_subjective": "Returns for review of glabellar lines. Happy with the result, "
	"reports the effect softened around week ten.",
	"custom_derma_soap_objective": "Glabellar complex mobile on animation. No ptosis, no bruising. "
	"Mid-face volume loss unchanged since the last visit.",
	"custom_derma_soap_assessment": "Dynamic glabellar rhytides, partial return. Mid-face volume deficit.",
	"custom_derma_soap_plan": "Re-treat glabella. Discuss cheek filler at the next review.",
}

STRUCTURED_NOTE = {
	"custom_physical_examination": "Fitzpatrick III. Diffuse post-inflammatory pigmentation over both "
	"cheeks, no active inflammatory lesions.",
	"custom_symptoms_notes": "Reports pigmentation is the main concern; no itch, no pain.",
	"custom_diagnosis_note": "Post-inflammatory hyperpigmentation, responding to the peel course.",
	"custom_illness_progression": "Improving. Third of six planned peels.",
}


def setup_demo_data() -> dict[str, Any]:
	"""Create the whole demo patient. Safe to re-run."""

	summary: dict[str, Any] = {"skipped": []}

	summary["item_group"] = _ensure_item_group()
	summary["practitioner"] = _ensure_practitioner()
	summary["appointment_type"] = _ensure_appointment_type()
	summary["patient"] = _ensure_patient()
	summary["procedure_category"] = _ensure_procedure_category(summary)
	summary["body_template"] = _ensure_body_template(summary)
	summary["body_parts"] = _ensure_body_template_parts(summary["body_template"], summary)
	summary["procedure_templates"] = _ensure_procedure_templates(summary)
	summary["consent_template"] = _ensure_consent_template(summary)
	summary["visits"] = _ensure_visits(summary)
	summary["photo_set"] = _ensure_photo_set(summary)
	summary["findings"] = _ensure_findings(summary)
	summary["procedures"] = _ensure_clinical_procedures(summary)
	summary["annotations"] = _ensure_annotations(summary)

	frappe.db.commit()

	print("DEMO_SEED_SUMMARY " + json.dumps(summary, default=str))
	return summary


def teardown_demo_data() -> dict[str, Any]:
	"""Remove everything setup_demo_data created, children first."""

	summary: dict[str, Any] = {"deleted": {}}
	patient = frappe.db.get_value("Patient", {"first_name": PATIENT_FIRST_NAME}, "name")
	encounters = _demo_encounters(patient)
	procedures = (
		[
			row.name
			for row in frappe.get_all("Clinical Procedure", filters={"patient": patient}, fields=["name"])
		]
		if patient
		else []
	)

	summary["deleted"]["annotations"] = _delete_annotations(encounters, procedures)
	for doctype in ("Derma Chart Mark", "Derma Finding", "Derma Treatment Entry", "Derma Photo Set"):
		summary["deleted"][doctype] = _delete_where(doctype, {"patient": patient}) if patient else 0
	summary["deleted"]["Clinical Procedure"] = _delete_names("Clinical Procedure", procedures)
	summary["deleted"]["Patient Encounter"] = _delete_names("Patient Encounter", encounters)
	summary["deleted"]["Patient"] = _delete_names("Patient", [patient] if patient else [])

	templates = [template for template, *_ in PROCEDURE_TEMPLATES]
	summary["deleted"]["Clinical Procedure Template"] = _delete_names(
		"Clinical Procedure Template", templates
	)
	# healthcare's Clinical Procedure Template.after_insert calls
	# create_item_from_template(), so each template left an Item behind. Leaving
	# them makes a re-seed fail on a duplicate primary key rather than reuse them.
	summary["deleted"]["Item"] = _delete_names("Item", templates)

	summary["deleted"]["Derma Body Template Part"] = _delete_where(
		"Derma Body Template Part", {"body_template": BODY_TEMPLATE}
	)
	summary["deleted"]["Derma Body Template"] = _delete_names("Derma Body Template", [BODY_TEMPLATE])
	summary["deleted"]["Derma Procedure Category"] = _delete_names(
		"Derma Procedure Category", [PROCEDURE_CATEGORY]
	)

	frappe.db.commit()

	print("DEMO_TEARDOWN_SUMMARY " + json.dumps(summary, default=str))
	return summary


# ---------------------------------------------------------------------------
# Clinical fixtures
# ---------------------------------------------------------------------------


def _ensure_item_group() -> str:
	if frappe.db.exists("Item Group", ITEM_GROUP):
		return ITEM_GROUP

	parent = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ""}, "name")
	doc = frappe.get_doc(
		{"doctype": "Item Group", "item_group_name": ITEM_GROUP, "is_group": 0, "parent_item_group": parent}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_practitioner() -> str:
	existing = frappe.db.get_value("Healthcare Practitioner", {"first_name": PRACTITIONER_FIRST_NAME}, "name")
	if existing:
		return existing

	doc = frappe.get_doc(
		{"doctype": "Healthcare Practitioner", "first_name": PRACTITIONER_FIRST_NAME, "status": "Active"}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_appointment_type() -> str:
	if frappe.db.exists("Appointment Type", APPOINTMENT_TYPE):
		return APPOINTMENT_TYPE

	doc = frappe.get_doc(
		{
			"doctype": "Appointment Type",
			"appointment_type": APPOINTMENT_TYPE,
			"allow_booking_for": "Practitioner",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_patient() -> str:
	existing = frappe.db.get_value("Patient", {"first_name": PATIENT_FIRST_NAME}, "name")
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Patient",
			"first_name": PATIENT_FIRST_NAME,
			"sex": "Female",
			"mobile": "+15550100200",
			"dob": add_days(nowdate(), -365 * 38),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_procedure_category(summary: dict[str, Any]) -> str | None:
	if not api._has_doctype("Derma Procedure Category"):
		summary["skipped"].append("Derma Procedure Category (doctype missing)")
		return None

	if frappe.db.exists("Derma Procedure Category", PROCEDURE_CATEGORY):
		return PROCEDURE_CATEGORY

	doc = frappe.get_doc(
		{
			"doctype": "Derma Procedure Category",
			"title": PROCEDURE_CATEGORY,
			"workflow": "Aesthetic",
			"marker_behavior": "numbered_dot",
			"marker_color": "#c0392b",
		}
	)
	if api._has_field("Derma Procedure Category", "default_body_template"):
		doc.default_body_template = (
			BODY_TEMPLATE if frappe.db.exists("Derma Body Template", BODY_TEMPLATE) else None
		)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_body_template(summary: dict[str, Any]) -> str | None:
	if not api._has_doctype("Derma Body Template"):
		summary["skipped"].append("Derma Body Template (doctype missing)")
		return None

	if frappe.db.exists("Derma Body Template", BODY_TEMPLATE):
		# The studio only lists templates that carry an image, so repair a link a
		# half-finished run left empty without re-uploading one that is fine.
		if not frappe.db.get_value("Derma Body Template", BODY_TEMPLATE, "image"):
			frappe.db.set_value(
				"Derma Body Template", BODY_TEMPLATE, "image", _ensure_png(*BODY_TEMPLATE_IMAGE)
			)
		return BODY_TEMPLATE

	doc = frappe.get_doc(
		{
			"doctype": "Derma Body Template",
			"title": BODY_TEMPLATE,
			"template_type": "Face",
			"gender": "Female",
			"view_key": "demo_face_front",
			"image": _ensure_png(*BODY_TEMPLATE_IMAGE),
			"sequence": 1,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_body_template_parts(body_template: str | None, summary: dict[str, Any]) -> list[str]:
	if not body_template or not api._has_doctype("Derma Body Template Part"):
		summary["skipped"].append("Derma Body Template Part (doctype missing)")
		return []

	names: list[str] = []
	for part_name, shape in BODY_PARTS:
		names.append(_ensure_body_template_part(body_template, part_name, shape, disabled=0))
	retired_name, retired_shape = RETIRED_BODY_PART
	names.append(_ensure_body_template_part(body_template, retired_name, retired_shape, disabled=1))

	return names


def _ensure_body_template_part(
	body_template: str, part_name: str, shape: list[list[float]], disabled: int
) -> str:
	"""Converge one area's outline and its retired flag, so an area retired here is retired
	again even if it was restored in the designer. Variables are left as the designer left
	them - it owns them once the area exists."""

	existing = frappe.db.get_value(
		"Derma Body Template Part", {"body_template": body_template, "part_name": part_name}, "name"
	)
	if existing:
		# Converge the outline: rows planted before the polygon format was fixed hold a
		# shape the chart cannot read, and the areas silently never draw.
		frappe.db.set_value(
			"Derma Body Template Part", existing, {"shape_json": json.dumps(shape), "disabled": disabled}
		)
		_ensure_area_variable(existing)
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Derma Body Template Part",
			"body_template": body_template,
			"part_name": part_name,
			"shape_json": json.dumps(shape),
			"color": "#2980b9",
			"opacity": 0.3,
			"disabled": disabled,
		}
	)
	if api._has_doctype("Derma Template Part Variable"):
		doc.append("variables", dict(AREA_VARIABLE))
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_area_variable(part: str) -> None:
	"""An area that declares nothing gets the demo variable back. An area that declares
	something keeps it - the designer owns that list once the area exists, and the seeded
	marks would otherwise carry values no area asked for."""

	if not api._has_doctype("Derma Template Part Variable"):
		return
	if frappe.db.exists(
		"Derma Template Part Variable", {"parent": part, "parenttype": "Derma Body Template Part"}
	):
		return

	doc = frappe.get_doc("Derma Body Template Part", part)
	doc.append("variables", dict(AREA_VARIABLE))
	doc.save(ignore_permissions=True)


def _ensure_procedure_templates(summary: dict[str, Any]) -> list[str]:
	names = []
	for template, behavior, color, category_override in PROCEDURE_TEMPLATES:
		names.append(
			_ensure_procedure_template(
				template, behavior, color, category_override or summary["procedure_category"], summary
			)
		)
	return names


def _ensure_procedure_template(
	template: str, behavior: str, color: str, category: str | None, summary: dict[str, Any]
) -> str:
	if not frappe.db.exists("Clinical Procedure Template", template):
		doc = frappe.get_doc(
			{
				"doctype": "Clinical Procedure Template",
				"template": template,
				# healthcare's after_insert reads item_code straight into a new Item.
				"item_code": template,
				"description": f"{template} - demo fixture for the Derma Chart.",
				"item_group": summary["item_group"],
			}
		)
		if api._has_field("Clinical Procedure Template", "is_billable"):
			doc.set("is_billable", 0)
		doc.insert(ignore_permissions=True)

	values = {
		"custom_derma_category": category,
		"custom_derma_marker_behavior": behavior,
		"custom_derma_marker_color": color,
		"custom_derma_variables_json": json.dumps(TEMPLATE_VARIABLES),
		"custom_derma_required_fields": json.dumps([]),
		"custom_derma_allowed_body_templates": summary["body_template"],
	}
	present = {}
	for fieldname, value in values.items():
		if value is None:
			continue
		if not api._has_field("Clinical Procedure Template", fieldname):
			note = f"Clinical Procedure Template.{fieldname} (field missing)"
			if note not in summary["skipped"]:
				summary["skipped"].append(note)
			continue
		present[fieldname] = value

	if present:
		frappe.db.set_value("Clinical Procedure Template", template, present, update_modified=False)
	return template


def _ensure_consent_template(summary: dict[str, Any]) -> str | None:
	if not api._has_doctype("Consent Form Template"):
		summary["skipped"].append("Consent Form Template (doctype missing)")
		return None

	# It does not autoname off `title`, so the existence check is on the field.
	existing = frappe.db.get_value("Consent Form Template", {"title": CONSENT_TEMPLATE}, "name")
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Consent Form Template",
			"title": CONSENT_TEMPLATE,
			"template_html": (
				"<p>I, {{ patient_name }}, consent to the aesthetic procedure discussed on "
				"{{ encounter_date }}, including its risks, benefits and alternatives.</p>"
			),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


# ---------------------------------------------------------------------------
# The visits themselves
# ---------------------------------------------------------------------------


def _ensure_visits(summary: dict[str, Any]) -> dict[str, Any]:
	"""One encounter per visit, each with its assessment and its marks.

	All three stay in draft. Submitting the past two would read better, but a
	submitted encounter makes the chart read-only, and a demo whose history
	cannot be reopened is a worse demo than one whose dates do the storytelling.
	"""

	visits: dict[str, Any] = {}
	for visit in VISITS:
		encounter = _ensure_encounter(summary, visit["days_ago"])
		_apply_assessment(encounter, visit["mode"])
		visits[visit["key"]] = {
			"encounter": encounter,
			"mode": visit["mode"],
			"marks": _ensure_marks(summary, encounter, visit["marks"]),
		}
	return visits


def _ensure_encounter(summary: dict[str, Any], days_ago: int) -> str:
	encounter_date = add_days(nowdate(), -days_ago)
	existing = frappe.db.get_value(
		"Patient Encounter",
		{"patient": summary["patient"], "encounter_date": encounter_date, "docstatus": 0},
		"name",
	)
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Patient Encounter",
			"patient": summary["patient"],
			"appointment_type": APPOINTMENT_TYPE,
			"practitioner": summary["practitioner"],
			"encounter_date": encounter_date,
			"encounter_time": nowtime(),
			"status": "Open",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _apply_assessment(encounter: str, mode: str | None) -> None:
	"""Stamp the mode and write that format's content, so a visit reopens the way
	it was written (do_derma/assessment.py). Today's visit is left unstamped so
	the mode picker is reachable."""

	if not mode:
		return

	content = SOAP_NOTE if mode == "SOAP" else STRUCTURED_NOTE
	values = {
		fieldname: text
		for fieldname, text in content.items()
		if api._has_field("Patient Encounter", fieldname)
	}
	if api._has_field("Patient Encounter", "custom_derma_assessment_mode"):
		values["custom_derma_assessment_mode"] = mode
	if values:
		frappe.db.set_value("Patient Encounter", encounter, values, update_modified=False)


def _ensure_marks(summary: dict[str, Any], encounter: str, specs: tuple) -> list[str]:
	if not api._has_doctype("Derma Chart Mark"):
		note = "Derma Chart Mark (doctype missing)"
		if note not in summary["skipped"]:
			summary["skipped"].append(note)
		return []

	existing = frappe.get_all(
		"Derma Chart Mark", filters={"encounter": encounter}, pluck="name", order_by="creation asc"
	)
	if len(existing) >= len(specs):
		return existing

	names: list[str] = []
	for template, x_percent, y_percent, detail, area in specs:
		mark = api.save_chart_mark(
			{
				"patient": summary["patient"],
				"encounter": encounter,
				"procedure_template": template,
				"body_template": summary["body_template"],
				"x_percent": x_percent,
				"y_percent": y_percent,
				**detail,
				**_area_placement(summary["body_template"], area),
			}
		)
		names.append(mark["name"])
	return names


def _area_placement(body_template: str | None, area: tuple[str, dict[str, str]] | None) -> dict[str, Any]:
	"""Link a mark to the area it was drawn on and record what was typed there, the way
	the annotation studio does. A mark placed off every area sends nothing."""

	if not area or not body_template or not api._has_doctype("Derma Body Template Part"):
		return {}

	part_name, values = area
	part = frappe.db.get_value(
		"Derma Body Template Part", {"body_template": body_template, "part_name": part_name}, "name"
	)
	if not part:
		return {}

	return {
		"body_template_part": part,
		"body_region": part_name,
		"region_label": part_name,
		"area_variables": [
			{"fieldname": api._variable_fieldname(name), "label": name, "value": value}
			for name, value in values.items()
		],
	}


def _ensure_clinical_procedures(summary: dict[str, Any]) -> list[str]:
	"""Two procedures on today's visit, so the Procedures tab has rows to activate
	and to hang a per-row `Annotate (n)` button off."""

	encounter = summary["visits"]["current"]["encounter"]
	# Ordered, because _ensure_annotations anchors to the first of these and an
	# unordered read makes the second run anchor to a different procedure.
	existing = frappe.get_all(
		"Clinical Procedure",
		filters={"patient": summary["patient"]},
		pluck="name",
		order_by="creation asc",
		limit=5,
	)
	if existing:
		return existing

	names = []
	for template in ("DEMO Filler Cheek", "DEMO Laser Resurfacing"):
		result = api.create_derma_chart_procedure(
			{
				"patient": summary["patient"],
				"encounter": encounter,
				"procedure_template": template,
				"notes": f"{template} planned at today's visit.",
				"product_name": "HA Filler" if "Filler" in template else "Fractional CO2",
			}
		)
		names.append(result["clinical_procedure"]["name"])
	return names


def _ensure_findings(summary: dict[str, Any]) -> list[str]:
	if not api._has_doctype("Derma Finding"):
		summary["skipped"].append("Derma Finding (doctype missing)")
		return []

	existing = frappe.get_all(
		"Derma Finding", filters={"patient": summary["patient"]}, pluck="name", order_by="creation asc"
	)
	if existing:
		return existing

	specs = (
		{
			"finding_type": "Pigmentation",
			"body_region": "Face",
			"region_label": "Left cheek",
			"x_percent": 22.0,
			"y_percent": 46.0,
			"morphology": "Macule",
			"severity": "Moderate",
			"status": "Improving",
			"notes": "Post-inflammatory hyperpigmentation, responding to the peel course.",
			"encounter_key": "current",
		},
		{
			"finding_type": "Lesion",
			"body_region": "Face",
			"region_label": "Right temple",
			"x_percent": 74.0,
			"y_percent": 40.0,
			"morphology": "Papule",
			"severity": "Mild",
			"status": "Biopsied",
			"diagnosis": "Seborrhoeic keratosis",
			"follow_up_required": 1,
			"notes": "Punch biopsy taken at this visit; histology pending.",
			"encounter_key": "visit_2",
		},
	)

	names = []
	for spec in specs:
		values = dict(spec)
		encounter = summary["visits"][values.pop("encounter_key")]["encounter"]
		doc = frappe.get_doc(
			{
				"doctype": "Derma Finding",
				"patient": summary["patient"],
				"encounter": encounter,
				"body_view": "Face Front",
				**values,
			}
		)
		doc.insert(ignore_permissions=True)
		names.append(doc.name)
	return names


def _ensure_photo_set(summary: dict[str, Any]) -> str | None:
	"""A Before/After pair so the Photos tab and the Compare panel have images."""

	if not api._has_doctype("Derma Photo Set"):
		summary["skipped"].append("Derma Photo Set (doctype missing)")
		return None

	existing = frappe.db.get_value("Derma Photo Set", {"patient": summary["patient"]}, "name")
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Derma Photo Set",
			"patient": summary["patient"],
			"encounter": summary["visits"]["current"]["encounter"],
			"set_type": "Before/After",
			"body_view": "Face Front",
			"body_region": "Face",
			"notes": "Peel course - before at visit 2, after today.",
		}
	)
	for (filename, rgb), photo_type in zip(PHOTO_IMAGES, ("Before", "After"), strict=True):
		doc.append(
			"photos",
			{
				"image": _ensure_png(filename, 480, 640, rgb),
				"photo_type": photo_type,
				"view": "Face Front",
				"body_region": "Face",
			},
		)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_annotations(summary: dict[str, Any]) -> dict[str, Any]:
	"""One drawing on the consultation and one on a procedure, so both anchors and
	the `Annotations (N)` toolbar button on either doctype have something to show."""

	if not api._has_doctype("Health Annotation"):
		summary["skipped"].append("Health Annotation (doctype missing)")
		return {}

	encounter = summary["visits"]["current"]["encounter"]
	procedure = summary["procedures"][0] if summary["procedures"] else None

	saved = {
		"encounter": _existing_annotation("Patient Encounter", encounter)
		or api.save_derma_annotation(
			{
				"patient": summary["patient"],
				"encounter": encounter,
				"file_data": _png_data_url(600, 800, (238, 228, 220)),
				"json_text": json.dumps(_demo_scene(summary["body_template"])),
			}
		)["name"]
	}

	if procedure:
		saved["procedure"] = (
			_existing_annotation("Clinical Procedure", procedure)
			or api.save_derma_annotation(
				{
					"patient": summary["patient"],
					"encounter": encounter,
					"clinical_procedure": procedure,
					"file_data": _png_data_url(600, 800, (232, 236, 240)),
					"json_text": json.dumps(_demo_scene(summary["body_template"])),
				}
			)["name"]
		)

	return saved


def _demo_scene(body_template: str | None) -> dict[str, Any]:
	"""The minimum scene the fan-out will accept.

	_sync_chart_marks_for_annotation returns immediately unless an element carries
	kind "derma_template"/"derma_template_image" (api.py), so without this element
	the visit's marks would never be backlinked to the drawing.
	"""

	return {
		"elements": [
			{
				"id": "demo-template-element",
				"type": "image",
				"x": 0,
				"y": 0,
				"width": 600,
				"height": 800,
				"customData": {"kind": "derma_template", "template": {"name": body_template}},
			}
		],
		"derma_template": {"name": body_template},
	}


def _existing_annotation(parenttype: str, parent: str) -> str | None:
	"""The drawing already anchored to this document, if a previous run made one."""

	if not api._has_doctype("Health Annotation Table"):
		return None
	return frappe.db.get_value(
		"Health Annotation Table", {"parenttype": parenttype, "parent": parent}, "annotation"
	)


# ---------------------------------------------------------------------------
# Files and teardown
# ---------------------------------------------------------------------------


def _ensure_png(filename: str, width: int, height: int, rgb: tuple[int, int, int]) -> str | None:
	"""Attach a generated PNG, so no binary lives in the repo."""

	# Frappe appends a hash to the stored file_name, so match on the stem.
	stem = filename.rsplit(".", 1)[0]
	existing = frappe.db.get_value("File", {"file_name": ("like", f"{stem}%"), "is_private": 0}, "file_url")
	if existing:
		return existing

	try:
		doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": filename,
				"is_private": 0,
				"content": solid_png(width, height, rgb),
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.file_url
	except Exception:
		frappe.log_error(title="Demo seed: image", message=frappe.get_traceback())
		return None


def _png_data_url(width: int, height: int, rgb: tuple[int, int, int]) -> str:
	return "data:image/png;base64," + base64.b64encode(solid_png(width, height, rgb)).decode()


def _demo_encounters(patient: str | None) -> list[str]:
	if not patient:
		return []
	return frappe.get_all("Patient Encounter", filters={"patient": patient}, pluck="name")


def _delete_annotations(encounters: list[str], procedures: list[str]) -> int:
	parents = encounters + procedures
	if not parents or not api._has_doctype("Health Annotation Table"):
		return 0

	rows = frappe.get_all(
		"Health Annotation Table",
		filters={"parent": ["in", parents]},
		fields=["annotation"],
		limit=1000,
	)
	return _delete_names("Health Annotation", [row.annotation for row in rows if row.annotation])


def _delete_where(doctype: str, filters: dict[str, Any]) -> int:
	if not api._has_doctype(doctype):
		return 0
	return _delete_names(doctype, frappe.get_all(doctype, filters=filters, pluck="name"))


def _delete_names(doctype: str, names: list[str]) -> int:
	deleted = 0
	for name in dict.fromkeys(names):
		if not name or not frappe.db.exists(doctype, name):
			continue
		try:
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, delete_permanently=True)
		except Exception:
			# delete_doc can raise *after* the row is gone - a full background
			# queue (QueueOverloaded) is the usual one on a busy dev bench - so
			# the exception is logged but the database, not the exception, is
			# what decides whether the row went. A linked or submitted row that
			# genuinely refuses stays behind; everything here is prefixed DEMO,
			# so what survives is identifiable and inert.
			frappe.log_error(title=f"Demo teardown: {doctype} {name}", message=frappe.get_traceback())
		if not frappe.db.exists(doctype, name):
			deleted += 1
	return deleted
