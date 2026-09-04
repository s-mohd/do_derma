"""Custom fields do_derma owns, created on every migrate instead of by patch.

Frappe runs a patch once ever, so a site whose Patch Log records the do_derma
patches as applied can never regain fields that went missing. This module runs
from after_migrate, bypassing Patch Log, and converges new and drifted sites
alike. It is idempotent and never clobbers: an existing field is left exactly as
the clinic has it.
"""

from typing import Any

import frappe
from frappe import _

from do_derma.config.marker_size import MARKER_SIZE_FIELD

DERMA_MODULE = "Do Derma"
ASSESSMENT_MODE_OPTIONS = "\nStructured\nSOAP"
# `freehand` and `line` are last because their patches appended them there.
MARKER_BEHAVIOR_OPTIONS = "\n".join(
	[
		"numbered_dot",
		"blue_dot",
		"three_dots",
		"triangle",
		"triangle_cluster",
		"hatch",
		"five_lines",
		"x_mark",
		"target",
		"area",
		"finding_dot",
		"freehand",
		"line",
	]
)
SOAP_ONLY = "eval:doc.custom_derma_assessment_mode=='SOAP'"
# Written when a clinic set to Block completes a session past its readiness blockers.
COMPLETION_OVERRIDE_FIELD = "custom_derma_completion_override_reason"

DERMA_CUSTOM_FIELDS: dict[str, list[dict[str, Any]]] = {
	"Patient Encounter": [
		{
			"fieldname": "custom_derma_assessment_section",
			"fieldtype": "Section Break",
			"label": "Derma Assessment",
			"insert_after": "encounter_comment",
			"collapsible": 1,
		},
		{
			"fieldname": "custom_derma_assessment_mode",
			"fieldtype": "Select",
			"label": "Assessment Mode",
			"options": ASSESSMENT_MODE_OPTIONS,
			"insert_after": "custom_derma_assessment_section",
			"read_only": 1,
			"description": "Stamped on the first save. A note reopens in the format it was written in.",
		},
		{
			"fieldname": "custom_derma_soap_subjective",
			"fieldtype": "Small Text",
			"label": "Subjective",
			"insert_after": "custom_derma_assessment_mode",
			"depends_on": SOAP_ONLY,
		},
		{
			"fieldname": "custom_derma_soap_objective",
			"fieldtype": "Small Text",
			"label": "Objective",
			"insert_after": "custom_derma_soap_subjective",
			"depends_on": SOAP_ONLY,
		},
		{
			"fieldname": "custom_derma_soap_assessment",
			"fieldtype": "Small Text",
			"label": "Assessment",
			"insert_after": "custom_derma_soap_objective",
			"depends_on": SOAP_ONLY,
		},
		{
			"fieldname": "custom_derma_soap_plan",
			"fieldtype": "Small Text",
			"label": "Plan",
			"insert_after": "custom_derma_soap_assessment",
			"depends_on": SOAP_ONLY,
		},
		{
			"fieldname": COMPLETION_OVERRIDE_FIELD,
			"fieldtype": "Small Text",
			"label": "Completion Override Reason",
			"insert_after": "custom_derma_soap_plan",
			"read_only": 1,
			"no_copy": 1,
			"description": "Why this session was completed with readiness blockers unresolved.",
		},
	],
	# do_health owns this child table; do_derma adds the column that carries the badge legend
	# rendered under a saved drawing. Its patch (add_derma_annotation_data_field) is recorded as
	# applied on sites where the field is nonetheless absent, which is what this module repairs.
	"Health Annotation Table": [
		{
			"fieldname": "annotation_data",
			"fieldtype": "Long Text",
			"label": "Annotation Data",
			"insert_after": "type",
			"read_only": 1,
		},
	],
	# The chart's price-override controls write these through
	# update_clinical_procedure_fields; without them the endpoint silently
	# dropped every value. The note itself rides on the core `notes` field,
	# which DERMA_PROPERTY_SETTERS unlocks for editing.
	"Clinical Procedure": [
		{
			"fieldname": "custom_derma_billing_section",
			"fieldtype": "Section Break",
			"label": "Derma Billing",
			"insert_after": "notes",
			"collapsible": 1,
		},
		{
			"fieldname": "custom_derma_price_list",
			"fieldtype": "Link",
			"label": "Price List",
			"options": "Price List",
			"insert_after": "custom_derma_billing_section",
		},
		{
			"fieldname": "custom_derma_price_override",
			"fieldtype": "Currency",
			"label": "Price Override",
			"insert_after": "custom_derma_price_list",
		},
		{
			"fieldname": "custom_derma_no_charge",
			"fieldtype": "Check",
			"label": "No Charge",
			"insert_after": "custom_derma_price_override",
		},
		{
			"fieldname": "custom_derma_price_override_reason",
			"fieldtype": "Small Text",
			"label": "Price Override Reason",
			"insert_after": "custom_derma_no_charge",
		},
		{
			# do_health declares this table on Patient Encounter only, so a procedure-anchored
			# drawing had nowhere to file itself and save_derma_annotation threw AttributeError
			# on the append. Same fieldname and child doctype, so one code path serves both
			# anchors and a site that later gains do_health's own field keeps what it has.
			"fieldname": "custom_annotations",
			"fieldtype": "Table",
			"label": "Annotations",
			"options": "Health Annotation Table",
			"insert_after": "custom_derma_price_override_reason",
			"hidden": 1,
		},
		{
			# Variables a template asks to capture once for the whole procedure instead of once
			# per mark. Keyed by procedure template inside the row, because the studio can tag
			# marks from several templates against one procedure.
			"fieldname": "custom_derma_procedure_variables",
			"fieldtype": "Table",
			"label": "Derma Procedure Variables",
			"options": "Derma Procedure Variable",
			"insert_after": "custom_annotations",
			"hidden": 1,
		},
	],
	# Every derma behaviour a procedure template carries. These were created by
	# seed_derma_v2_defaults and its successors, which `install_app` marks complete
	# without running on a fresh site, so a clinic that installed do_derma after those
	# patches shipped had none of these fields and could not save a template at all.
	"Clinical Procedure Template": [
		{
			"fieldname": "custom_derma_section",
			"fieldtype": "Section Break",
			"label": "Dermatology Chart Behavior",
			"insert_after": "description",
		},
		{
			"fieldname": "custom_derma_category",
			"fieldtype": "Link",
			"label": "Derma Category",
			"options": "Derma Procedure Category",
			"insert_after": "custom_derma_section",
		},
		{
			"fieldname": "custom_derma_allowed_body_templates",
			"fieldtype": "Small Text",
			"label": "Allowed Body Templates",
			"description": "Comma-separated Derma Body Template names.",
			"insert_after": "custom_derma_category",
		},
		{
			"fieldname": "custom_derma_variables_json",
			"fieldtype": "Code",
			"label": "Derma Variables JSON",
			"options": "JSON",
			"description": "Procedure variables shown in the derma annotation studio. Use fieldname, label, fieldtype, options, and required.",
			"insert_after": "custom_derma_allowed_body_templates",
		},
		{
			"fieldname": "custom_derma_marker_behavior",
			"fieldtype": "Select",
			"label": "Marker Behavior",
			"options": MARKER_BEHAVIOR_OPTIONS,
			"insert_after": "custom_derma_variables_json",
		},
		{
			"fieldname": "custom_derma_marker_color",
			"fieldtype": "Data",
			"label": "Marker Color",
			"insert_after": "custom_derma_marker_behavior",
		},
		{
			"fieldname": MARKER_SIZE_FIELD,
			"fieldtype": "Float",
			"label": "Marker Size",
			"precision": "2",
			"description": "Multiplier the chart stamps this marker at. Empty means 1.0.",
			"insert_after": "custom_derma_marker_color",
		},
		{
			"fieldname": "custom_derma_marker_preset_json",
			"fieldtype": "Code",
			"label": "Marker Preset JSON",
			"options": "JSON",
			"description": "Optional future-ready Excalidraw element preset for click-to-stamp charting.",
			"insert_after": MARKER_SIZE_FIELD,
		},
		{
			"fieldname": "custom_derma_required_fields",
			"fieldtype": "Code",
			"label": "Required Fields JSON",
			"options": "JSON",
			"insert_after": "custom_derma_marker_preset_json",
		},
		{
			"fieldname": "custom_derma_consent_required",
			"fieldtype": "Check",
			"label": "Consent Required",
			"insert_after": "custom_derma_required_fields",
		},
		{
			"fieldname": "custom_derma_before_after_photo_required",
			"fieldtype": "Check",
			"label": "Before / After Photo Required",
			"insert_after": "custom_derma_consent_required",
		},
		{
			"fieldname": "custom_derma_product_tracking_required",
			"fieldtype": "Check",
			"label": "Product / Lot Required",
			"insert_after": "custom_derma_before_after_photo_required",
		},
		{
			"fieldname": "custom_derma_device_settings_required",
			"fieldtype": "Check",
			"label": "Device Settings Required",
			"insert_after": "custom_derma_product_tracking_required",
		},
		{
			"fieldname": "custom_derma_variables_per_procedure",
			"fieldtype": "Check",
			"label": "Capture Variables Once Per Procedure",
			"insert_after": "custom_derma_device_settings_required",
			"description": "One set of values for the whole procedure instead of one per mark. A mark can still override.",
		},
		{
			"fieldname": "custom_derma_note_template",
			"fieldtype": "Small Text",
			"label": "Note Sentence Template",
			"insert_after": "custom_derma_variables_per_procedure",
		},
	],
	"Healthcare Practitioner": [
		{
			"fieldname": "custom_derma_default_assessment_mode",
			"fieldtype": "Select",
			"label": "Default Derma Assessment Mode",
			"options": ASSESSMENT_MODE_OPTIONS,
			"insert_after": "practitioner_name",
			"description": "Applies to new encounters only. It never overrides a mode already stamped on a visit.",
		},
	],
}


# healthcare marks Clinical Procedure.notes set_only_once, which turned every
# correction to a procedure note into a silent no-op. The chart owns the note, so
# do_derma unlocks the field instead of shadowing it with a second one.
DERMA_PROPERTY_SETTERS: list[dict[str, Any]] = [
	{
		"doctype_or_field": "DocField",
		"doctype": "Clinical Procedure",
		"fieldname": "notes",
		"property": "set_only_once",
		"property_type": "Check",
		"value": "0",
	},
	{
		"doctype_or_field": "DocField",
		"doctype": "Clinical Procedure",
		"fieldname": "notes",
		"property": "allow_on_submit",
		"property_type": "Check",
		"value": "1",
	},
]


def ensure_derma_schema() -> dict[str, list[str]]:
	"""Create every missing custom field and property setter. Returns what was created."""
	created: dict[str, list[str]] = {}
	_ensure_property_setters()
	for doctype, specs in DERMA_CUSTOM_FIELDS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		for spec in specs:
			fieldname = spec["fieldname"]
			if has_field(doctype, fieldname):
				continue
			# A Table field whose child doctype is not installed cannot be created at all.
			if spec["fieldtype"] == "Table" and not frappe.db.exists("DocType", spec["options"]):
				continue
			try:
				_create_custom_field(doctype, spec)
			except Exception:
				# One bad field definition must not abort a migrate.
				frappe.log_error(
					title=_("Derma schema: {0}.{1}").format(doctype, fieldname),
					message=frappe.get_traceback(),
				)
				continue
			created.setdefault(doctype, []).append(fieldname)
	return created


def _ensure_property_setters() -> None:
	for spec in DERMA_PROPERTY_SETTERS:
		doctype, fieldname = spec["doctype"], spec["fieldname"]
		if not frappe.db.exists("DocType", doctype) or not has_field(doctype, fieldname):
			continue
		existing = frappe.db.exists(
			"Property Setter",
			{"doc_type": doctype, "field_name": fieldname, "property": spec["property"]},
		)
		if existing:
			frappe.db.set_value("Property Setter", existing, "value", spec["value"])
			frappe.clear_cache(doctype=doctype)
			continue
		try:
			frappe.make_property_setter(spec, is_system_generated=False, module=DERMA_MODULE)
		except Exception:
			frappe.log_error(
				title=_("Derma schema: {0}.{1}").format(doctype, fieldname),
				message=frappe.get_traceback(),
			)


def has_field(doctype: str, fieldname: str) -> bool:
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def _create_custom_field(doctype: str, spec: dict[str, Any]) -> None:
	field = frappe.new_doc("Custom Field")
	field.update({**spec, "dt": doctype, "module": DERMA_MODULE})
	# A missing anchor would place the field unpredictably; append instead.
	if spec.get("insert_after") and not has_field(doctype, spec["insert_after"]):
		field.insert_after = None
	field.insert(ignore_permissions=True)
	frappe.clear_cache(doctype=doctype)
