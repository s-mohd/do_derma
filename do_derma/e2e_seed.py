"""Deterministic fixtures for the Playwright E2E suite.

Run via::

	bench --site dermaone.localhost execute do_derma.e2e_seed.setup_e2e_data

Two properties matter and are load-bearing for the suite:

1. **Idempotent.** Every helper is check-then-act, so re-running creates no
   duplicates. This mirrors how ``patches.txt`` patches are written in this app.
2. **Schema-defensive.** The same script runs against sites where the
   ``custom_derma_*`` custom fields on ``Clinical Procedure Template`` were never
   migrated, or where ``Consent Form Template`` does not exist. It reuses
   ``api._has_doctype`` / ``api._has_field`` rather than re-implementing them, so
   there is one definition of "is this field present".

Everything created is prefixed with ``E2E `` and is looked up by that prefix from
``e2e/helpers/derma.ts``. The dev site is a production clone (40k+ Patients), so
the suite must never reach for whatever rows happen to exist.
"""

from __future__ import annotations

import json
import struct
import zlib
from typing import Any

import frappe
from frappe.utils import nowdate, nowtime

from do_derma.api import _has_doctype, _has_field

E2E_PREFIX = "E2E "

PATIENT_FIRST_NAME = "E2E Derma Patient"
PRACTITIONER_FIRST_NAME = "E2E Derma Practitioner"
APPOINTMENT_TYPE = "E2E Derma Visit"
ITEM_GROUP = "E2E Derma"
PROCEDURE_CATEGORY = "E2E Injectables"
POINT_TEMPLATE = "E2E Filler"
AREA_TEMPLATE = "E2E Area Peel"
FREEHAND_TEMPLATE = "E2E Freehand Graft"
BODY_TEMPLATE = "E2E Face Map"
BODY_PART_NAMES = ("E2E Left Cheek", "E2E Right Cheek")
CONSENT_TEMPLATE = "E2E Consent"
NO_ACCESS_EMAIL = "e2e-no-access@example.com"
NO_ACCESS_PASSWORD = "admin"

BODY_TEMPLATE_IMAGE_NAME = "e2e-face-map.png"
BODY_TEMPLATE_IMAGE_SIZE = (600, 800)
BODY_TEMPLATE_IMAGE_RGB = (232, 224, 216)

# Procedure variables rendered by VariableEditor in DermaAnnotationStudio.jsx.
POINT_TEMPLATE_VARIABLES = [
	{"variable_name": "Product", "fieldname": "product", "label": "Product", "type": "Data"},
	{
		"variable_name": "Plane",
		"fieldname": "plane",
		"label": "Plane",
		"type": "Select",
		"options": "Subdermal\nSupraperiosteal",
	},
]


def setup_e2e_data() -> dict[str, Any]:
	"""Create every fixture the Playwright suite needs. Safe to re-run."""

	summary: dict[str, Any] = {"skipped": []}

	summary["item_group"] = _ensure_item_group()
	summary["practitioner"] = _ensure_practitioner()
	summary["appointment_type"] = _ensure_appointment_type()
	summary["patient"] = _ensure_patient()
	summary["procedure_category"] = _ensure_procedure_category(summary)
	summary["body_template"] = _ensure_body_template(summary)
	summary["body_parts"] = _ensure_body_template_parts(summary["body_template"], summary)
	summary["procedure_templates"] = _ensure_procedure_templates(
		summary["item_group"], summary["procedure_category"], summary["body_template"], summary
	)
	summary["consent_template"] = _ensure_consent_template(summary)
	summary["no_access_user"] = _ensure_no_access_user()
	summary["encounter"] = _ensure_draft_encounter(
		summary["patient"], summary["practitioner"], summary["appointment_type"]
	)
	summary["clinical_procedure"] = _ensure_clinical_procedure(
		summary["patient"], summary["practitioner"], summary["encounter"], summary
	)

	frappe.db.commit()

	print("E2E_SEED_SUMMARY " + json.dumps(summary, default=str))
	return summary


# ---------------------------------------------------------------------------
# Clinical fixtures
# ---------------------------------------------------------------------------


def _ensure_item_group() -> str:
	if frappe.db.exists("Item Group", ITEM_GROUP):
		return ITEM_GROUP

	parent = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ""}, "name")
	doc = frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": ITEM_GROUP,
			"is_group": 0,
			"parent_item_group": parent,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_practitioner() -> str:
	existing = frappe.db.get_value("Healthcare Practitioner", {"first_name": PRACTITIONER_FIRST_NAME}, "name")
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Healthcare Practitioner",
			"first_name": PRACTITIONER_FIRST_NAME,
			"status": "Active",
		}
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
			"mobile": "+15550000001",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_draft_encounter(patient: str, practitioner: str, appointment_type: str) -> str:
	"""One draft encounter so the very first spec has context without writing."""

	existing = frappe.db.get_value(
		"Patient Encounter", {"patient": patient, "docstatus": 0}, "name", order_by="creation desc"
	)
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Patient Encounter",
			"patient": patient,
			"appointment_type": appointment_type,
			"practitioner": practitioner,
			"encounter_date": nowdate(),
			"encounter_time": nowtime(),
			"status": "Open",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_clinical_procedure(
	patient: str, practitioner: str, encounter: str, summary: dict[str, Any]
) -> str | None:
	"""One saved procedure so the Procedures tab has a row carrying a per-row Annotate button."""

	if not frappe.db.exists("Clinical Procedure Template", POINT_TEMPLATE):
		summary["skipped"].append(f"Clinical Procedure (template {POINT_TEMPLATE} missing)")
		return None

	existing = frappe.db.get_value(
		"Clinical Procedure", {"patient": patient, "procedure_template": POINT_TEMPLATE}, "name"
	)
	if existing:
		return existing

	values: dict[str, Any] = {
		"doctype": "Clinical Procedure",
		"patient": patient,
		"procedure_template": POINT_TEMPLATE,
		"practitioner": practitioner,
		"status": "Draft",
	}
	encounter_field = next(
		(field for field in ("patient_encounter", "custom_patient_encounter", "encounter") if _has_field("Clinical Procedure", field)),
		None,
	)
	if encounter_field:
		values[encounter_field] = encounter
	doc = frappe.get_doc(values)
	doc.insert(ignore_permissions=True)
	return doc.name


# ---------------------------------------------------------------------------
# Derma configuration
# ---------------------------------------------------------------------------


def _ensure_procedure_category(summary: dict[str, Any]) -> str | None:
	if not _has_doctype("Derma Procedure Category"):
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
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_body_template(summary: dict[str, Any]) -> str | None:
	if not _has_doctype("Derma Body Template"):
		summary["skipped"].append("Derma Body Template (doctype missing)")
		return None

	if frappe.db.exists("Derma Body Template", BODY_TEMPLATE):
		# DermaAnnotationStudio.jsx only lists templates that have an image, so
		# repair the link if a previous run left it empty - but do not touch (or
		# re-upload) an image that is already attached.
		if not frappe.db.get_value("Derma Body Template", BODY_TEMPLATE, "image"):
			image_url = _ensure_body_template_image()
			if image_url:
				frappe.db.set_value("Derma Body Template", BODY_TEMPLATE, "image", image_url)
		return BODY_TEMPLATE

	image_url = _ensure_body_template_image()
	doc = frappe.get_doc(
		{
			"doctype": "Derma Body Template",
			"title": BODY_TEMPLATE,
			"template_type": "Face",
			"gender": "Female",
			"view_key": "e2e_face_front",
			"image": image_url,
			"sequence": 1,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_body_template_image() -> str | None:
	"""Attach a generated PNG. Written from bytes so no binary lives in the repo."""

	# Frappe appends a hash to the stored file_name, so match on the stem.
	stem = BODY_TEMPLATE_IMAGE_NAME.rsplit(".", 1)[0]
	existing = frappe.db.get_value("File", {"file_name": ("like", f"{stem}%"), "is_private": 0}, "file_url")
	if existing:
		return existing

	try:
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": BODY_TEMPLATE_IMAGE_NAME,
				"is_private": 0,
				"content": _solid_png(*BODY_TEMPLATE_IMAGE_SIZE, BODY_TEMPLATE_IMAGE_RGB),
			}
		)
		file_doc.insert(ignore_permissions=True)
		return file_doc.file_url
	except Exception:
		frappe.log_error(title="E2E seed: body template image", message=frappe.get_traceback())
		return None


def _ensure_body_template_parts(body_template: str | None, summary: dict[str, Any]) -> list[str]:
	if not body_template or not _has_doctype("Derma Body Template Part"):
		summary["skipped"].append("Derma Body Template Part (doctype missing)")
		return []

	created: list[str] = []
	# Two non-overlapping boxes on the left and right halves of the map.
	shapes = (
		{"type": "rectangle", "x": 12, "y": 30, "width": 26, "height": 22},
		{"type": "rectangle", "x": 62, "y": 30, "width": 26, "height": 22},
	)

	for part_name, shape in zip(BODY_PART_NAMES, shapes, strict=True):
		existing = frappe.db.get_value(
			"Derma Body Template Part", {"body_template": body_template, "part_name": part_name}, "name"
		)
		if existing:
			created.append(existing)
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Derma Body Template Part",
				"body_template": body_template,
				"part_name": part_name,
				"shape_json": json.dumps(shape),
				"color": "#2980b9",
				"opacity": 0.3,
			}
		)
		if _has_doctype("Derma Template Part Variable"):
			doc.append(
				"variables", {"variable_name": "Severity", "type": "Select", "options": "Mild\nSevere"}
			)
		doc.insert(ignore_permissions=True)
		created.append(doc.name)

	return created


def _ensure_procedure_templates(
	item_group: str,
	category: str | None,
	body_template: str | None,
	summary: dict[str, Any],
) -> list[str]:
	"""Three Clinical Procedure Templates, one per placement path.

	``placementToolFor()`` in EmbeddedExcalidraw.jsx routes
	``area``/``hatch``/``five_lines`` to a drag-to-size rectangle,
	``freehand``/``stroke``/``paint`` to the pen, and everything else to a point
	stamp, so these three behaviors cover every path a practitioner can take.
	"""

	specs = (
		(POINT_TEMPLATE, "numbered_dot", "#c0392b"),
		(AREA_TEMPLATE, "area", "#8e44ad"),
		(FREEHAND_TEMPLATE, "freehand", "#0e7490"),
	)

	names: list[str] = []
	for template, behavior, color in specs:
		names.append(
			_ensure_procedure_template(
				template, behavior, color, item_group, category, body_template, summary
			)
		)

	return names


def _ensure_procedure_template(
	template: str,
	behavior: str,
	color: str,
	item_group: str,
	category: str | None,
	body_template: str | None,
	summary: dict[str, Any],
) -> str:
	if frappe.db.exists("Clinical Procedure Template", template):
		_apply_derma_template_fields(template, behavior, color, category, body_template, summary)
		return template

	doc = frappe.get_doc(
		{
			"doctype": "Clinical Procedure Template",
			"template": template,
			# healthcare's after_insert calls create_item_from_template(), which
			# reads doc.item_code straight into a new Item - leaving it unset
			# fails with "Item Code is required".
			"item_code": template,
			"description": f"{template} - fixture for the do_derma E2E suite.",
			"item_group": item_group,
		}
	)
	if _has_field("Clinical Procedure Template", "is_billable"):
		doc.set("is_billable", 0)
	doc.insert(ignore_permissions=True)

	_apply_derma_template_fields(doc.name, behavior, color, category, body_template, summary)
	return doc.name


def _apply_derma_template_fields(
	template: str,
	behavior: str,
	color: str,
	category: str | None,
	body_template: str | None,
	summary: dict[str, Any],
) -> None:
	"""Set the ``custom_derma_*`` fields that actually exist on this site.

	These are shipped as fixtures filtered on ``module = "Do Derma"`` and are
	also created by patches, so a site can legitimately be missing any of them.
	"""

	values = {
		"custom_derma_category": category,
		"custom_derma_marker_behavior": behavior,
		"custom_derma_marker_color": color,
		"custom_derma_variables_json": json.dumps(POINT_TEMPLATE_VARIABLES),
		"custom_derma_required_fields": json.dumps([]),
		"custom_derma_allowed_body_templates": body_template,
	}

	present = {}
	for fieldname, value in values.items():
		if value is None:
			continue
		if not _has_field("Clinical Procedure Template", fieldname):
			note = f"Clinical Procedure Template.{fieldname} (field missing)"
			if note not in summary["skipped"]:
				summary["skipped"].append(note)
			continue
		present[fieldname] = value

	if present:
		frappe.db.set_value("Clinical Procedure Template", template, present, update_modified=False)


def _ensure_consent_template(summary: dict[str, Any]) -> str | None:
	if not _has_doctype("Consent Form Template"):
		summary["skipped"].append("Consent Form Template (doctype missing)")
		return None

	# Consent Form Template does not autoname off `title` (it composes a name
	# like "E2E Consent--"), so the existence check must be on the field.
	existing = frappe.db.get_value("Consent Form Template", {"title": CONSENT_TEMPLATE}, "name")
	if existing:
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Consent Form Template",
			"title": CONSENT_TEMPLATE,
			"template_html": (
				"<p>E2E consent for {{ patient_name }} on {{ encounter_date }}.</p>"
				"<p>This document exists only to exercise the consent panel.</p>"
			),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def _ensure_no_access_user() -> str:
	"""A user with none of ``api.CLINICAL_ACCESS_ROLES``.

	This is the browser-side counterpart to ``TestClinicalAccessGate``: every
	whitelisted endpoint in ``api.py`` writes with ``ignore_permissions=True``,
	so ``_ensure_clinical_access()`` is the whole authorization boundary and
	needs a regression test that drives it over HTTP.
	"""

	from do_derma.api import CLINICAL_ACCESS_ROLES

	if not frappe.db.exists("User", NO_ACCESS_EMAIL):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": NO_ACCESS_EMAIL,
				"first_name": "E2E No Access",
				"enabled": 1,
				"send_welcome_email": 0,
				"user_type": "System User",
			}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)

	user = frappe.get_doc("User", NO_ACCESS_EMAIL)
	stale = [row for row in user.roles if row.role in CLINICAL_ACCESS_ROLES]
	if stale:
		user.set("roles", [row for row in user.roles if row.role not in CLINICAL_ACCESS_ROLES])
		user.save(ignore_permissions=True)

	frappe.utils.password.update_password(NO_ACCESS_EMAIL, NO_ACCESS_PASSWORD)
	return NO_ACCESS_EMAIL


# ---------------------------------------------------------------------------
# PNG generation
# ---------------------------------------------------------------------------


def _solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
	"""Minimal single-colour PNG encoder.

	Keeps a real image out of the repo. Excalidraw needs an image with genuine
	dimensions to scale the body template against, so a 1x1 pixel will not do.
	"""

	row = b"\x00" + bytes(rgb) * width
	raw = row * height

	def chunk(tag: bytes, payload: bytes) -> bytes:
		return (
			struct.pack(">I", len(payload))
			+ tag
			+ payload
			+ struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
		)

	header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
	return (
		b"\x89PNG\r\n\x1a\n"
		+ chunk(b"IHDR", header)
		+ chunk(b"IDAT", zlib.compress(raw, 9))
		+ chunk(b"IEND", b"")
	)
