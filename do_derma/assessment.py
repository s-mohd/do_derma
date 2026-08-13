"""Assessment Mode resolution, layout and serialisation for the derma chart.

Owns everything about how a visit is documented: which of the two Assessment Modes
an encounter is written in, the field layout each mode renders, and the rules that
stamp a mode without ever discarding the other mode's content.
"""

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from do_derma.settings import SETTINGS_DOCTYPE, get_settings_doc

STRUCTURED = "Structured"
SOAP = "SOAP"
ASSESSMENT_MODES = (STRUCTURED, SOAP)

MODE_FIELD = "custom_derma_assessment_mode"
PRACTITIONER_DEFAULT_FIELD = "custom_derma_default_assessment_mode"

SOAP_FIELDS = (
	"custom_derma_soap_subjective",
	"custom_derma_soap_objective",
	"custom_derma_soap_assessment",
	"custom_derma_soap_plan",
)

# The Structured Assessment defaults, per CONTEXT.md. Seeded into Derma Settings
# once; a clinic that edits the list keeps its edit across migrates.
DEFAULT_STRUCTURED_FIELDS = (
	"symptoms",
	"custom_symptom_duration",
	"custom_symptoms_notes",
	"custom_illness_progression",
	"diagnosis",
	"custom_differential_diagnosis",
	"custom_diagnosis_note",
	"custom_physical_examination",
	"custom_other_examination",
)

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
CHILD_INTERNAL_FIELDS = {
	"name",
	"doctype",
	"parent",
	"parenttype",
	"parentfield",
	"idx",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"docstatus",
}


def has_field(doctype: str, fieldname: str) -> bool:
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def soap_is_supported() -> bool:
	"""SOAP needs its five custom fields; a site that has not migrated lacks them."""
	if not has_field("Patient Encounter", MODE_FIELD):
		return False
	return all(has_field("Patient Encounter", fieldname) for fieldname in SOAP_FIELDS)


def available_modes() -> list[str]:
	return list(ASSESSMENT_MODES) if soap_is_supported() else [STRUCTURED]


def get_structured_fieldnames() -> list[str]:
	"""Configured field list, falling back to the defaults when unset."""
	settings = get_settings_doc()
	rows = settings.get("structured_assessment_fields") if settings else None
	configured = [row.fieldname for row in rows or [] if row.fieldname and cint(row.enabled)]
	return configured or list(DEFAULT_STRUCTURED_FIELDS)


def get_structured_layout() -> list[dict[str, Any]]:
	"""Layout rows for the configured fields, silently dropping absent ones."""
	meta = frappe.get_meta("Patient Encounter")
	layout = []
	for fieldname in get_structured_fieldnames():
		df = meta.get_field(fieldname)
		if df:
			layout.append(_layout_row(df))
	return layout


def get_soap_layout() -> list[dict[str, Any]]:
	if not soap_is_supported():
		return []
	meta = frappe.get_meta("Patient Encounter")
	return [_layout_row(meta.get_field(fieldname)) for fieldname in SOAP_FIELDS if meta.get_field(fieldname)]


def get_layout(mode: str) -> list[dict[str, Any]]:
	return get_soap_layout() if mode == SOAP else get_structured_layout()


def get_assessment_mode(encounter_doc) -> str:
	"""The stamped mode always wins, so a note reopens as it was written."""
	stamped = _stamped_mode(encounter_doc)
	if stamped:
		return stamped
	if not soap_is_supported():
		return STRUCTURED
	return practitioner_default(encounter_doc.get("practitioner")) or STRUCTURED


def practitioner_default(practitioner: str | None) -> str:
	if not practitioner or not has_field("Healthcare Practitioner", PRACTITIONER_DEFAULT_FIELD):
		return ""
	value = frappe.db.get_value("Healthcare Practitioner", practitioner, PRACTITIONER_DEFAULT_FIELD)
	return value if value in ASSESSMENT_MODES else ""


def serialize_values(encounter_doc, layout: list[dict[str, Any]]) -> dict[str, Any]:
	values = {}
	for row in layout:
		fieldname = row.get("fieldname")
		if not fieldname or not row.get("is_value_field"):
			continue
		if row.get("fieldtype") in TABLE_FIELD_TYPES:
			allowed = {field.get("fieldname") for field in row.get("fields") or [] if field.get("fieldname")}
			# Child rows are Document instances, not dicts - `key in child` raises
			# TypeError on frappe v16 (Document no longer implements __contains__).
			values[fieldname] = [
				{key: child_values.get(key) for key in allowed if key in child_values}
				for child_values in (child.as_dict() for child in encounter_doc.get(fieldname) or [])
			]
		else:
			values[fieldname] = encounter_doc.get(fieldname)
	return values


def read_assessment(encounter_doc) -> dict[str, Any]:
	"""The full assessment payload for one encounter, in both modes."""
	mode = get_assessment_mode(encounter_doc)
	structured_layout = get_structured_layout()
	soap_layout = get_soap_layout()
	values = serialize_values(encounter_doc, structured_layout)
	soap_values = serialize_values(encounter_doc, soap_layout)
	return {
		"encounter": encounter_doc.name,
		"docstatus": cint(encounter_doc.docstatus),
		"mode": mode,
		"is_stamped": bool(_stamped_mode(encounter_doc)),
		"is_filled": any(_has_content(value) for value in [*values.values(), *soap_values.values()]),
		"available_modes": available_modes(),
		"soap_supported": soap_is_supported(),
		"layout": structured_layout,
		"values": values,
		"soap_layout": soap_layout,
		"soap_values": soap_values,
		"context_values": {
			"patient": encounter_doc.get("patient"),
			"appointment": encounter_doc.get("appointment"),
			"practitioner": encounter_doc.get("practitioner"),
		},
	}


def empty_assessment() -> dict[str, Any]:
	structured_layout = get_structured_layout()
	return {
		"encounter": "",
		"docstatus": None,
		"mode": STRUCTURED,
		"is_stamped": False,
		"is_filled": False,
		"available_modes": available_modes(),
		"soap_supported": soap_is_supported(),
		"layout": structured_layout,
		"values": {},
		"soap_layout": get_soap_layout(),
		"soap_values": {},
		"context_values": {},
	}


def apply_assessment(encounter_doc, values: dict[str, Any], mode: str | None = None) -> None:
	"""Write whitelisted fields for one mode, then stamp the mode if content landed.

	Only fields belonging to the resolved mode are writable, so a client cannot
	name an arbitrary Patient Encounter column.
	"""
	if cint(encounter_doc.docstatus) == 2:
		frappe.throw(_("Cancelled encounters cannot be edited."))

	target_mode = normalize_mode(mode) or get_assessment_mode(encounter_doc)
	layout = get_layout(target_mode)
	field_map = {row["fieldname"]: row for row in layout if row.get("is_value_field")}
	only_allow_on_submit = cint(encounter_doc.docstatus) == 1

	wrote_content = False
	for fieldname, value in (values or {}).items():
		row = field_map.get(fieldname)
		if not row:
			continue
		if only_allow_on_submit and not cint(row.get("allow_on_submit")):
			continue
		if row.get("fieldtype") in TABLE_FIELD_TYPES:
			child_fields = {
				field.get("fieldname") for field in row.get("fields") or [] if field.get("fieldname")
			}
			encounter_doc.set(
				fieldname,
				[
					{key: child.get(key) for key in child_fields if key in child}
					for child in (value or [])
					if isinstance(child, dict)
				],
			)
		else:
			encounter_doc.set(fieldname, value)
		if _has_content(value):
			wrote_content = True

	if wrote_content and not _stamped_mode(encounter_doc) and has_field("Patient Encounter", MODE_FIELD):
		encounter_doc.set(MODE_FIELD, target_mode)


def stamp_mode(encounter_doc, mode: str) -> None:
	"""Change the documented format. Writes no content and deletes nothing."""
	target_mode = normalize_mode(mode)
	if not target_mode:
		frappe.throw(_("{0} is not a valid Assessment Mode.").format(mode), frappe.ValidationError)
	if target_mode == SOAP and not soap_is_supported():
		frappe.throw(_("SOAP Note fields are not installed on this site."))
	if cint(encounter_doc.docstatus) != 0:
		frappe.throw(_("The documentation format can only be changed while the encounter is a draft."))
	if not has_field("Patient Encounter", MODE_FIELD):
		frappe.throw(_("Assessment Mode is not installed on this site."))
	encounter_doc.set(MODE_FIELD, target_mode)


def normalize_mode(mode: str | None) -> str:
	return mode if mode in ASSESSMENT_MODES else ""


def ensure_derma_settings_defaults() -> bool:
	"""Seed the structured field list once. Never overwrites a clinic's edit."""
	if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
		return False
	settings = frappe.get_doc(SETTINGS_DOCTYPE)
	if settings.get("structured_assessment_fields"):
		return False
	for fieldname in DEFAULT_STRUCTURED_FIELDS:
		settings.append("structured_assessment_fields", {"fieldname": fieldname, "enabled": 1})
	settings.save(ignore_permissions=True)
	return True


def _stamped_mode(encounter_doc) -> str:
	return normalize_mode(encounter_doc.get(MODE_FIELD))


def _has_content(value: Any) -> bool:
	if value is None:
		return False
	if isinstance(value, str):
		return bool(value.strip())
	if isinstance(value, list | tuple):
		return bool(value)
	return True


def _layout_row(df) -> dict[str, Any]:
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
		"layout_key": f"{df.fieldname}-{df.idx}",
		"idx": df.idx,
	}
	if df.fieldtype in TABLE_FIELD_TYPES and df.options:
		row["fields"] = child_table_layout(df.options)
	return row


def child_table_layout(doctype: str) -> list[dict[str, Any]]:
	if not frappe.db.exists("DocType", doctype):
		return []
	fields = []
	for df in frappe.get_meta(doctype).fields:
		if not df.fieldname or df.fieldname in CHILD_INTERNAL_FIELDS:
			continue
		fields.append(
			{
				"fieldname": df.fieldname,
				"fieldtype": df.fieldtype,
				"label": df.label,
				"options": df.options,
				"reqd": cint(df.reqd),
				"read_only": cint(df.read_only),
				"hidden": cint(df.hidden),
				"in_list_view": cint(df.in_list_view),
				"columns": cint(getattr(df, "columns", 0) or 0),
				"default": df.default,
			}
		)
	return fields
