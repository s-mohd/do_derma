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

DERMA_MODULE = "Do Derma"
ASSESSMENT_MODE_OPTIONS = "\nStructured\nSOAP"
SOAP_ONLY = "eval:doc.custom_derma_assessment_mode=='SOAP'"

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


def ensure_derma_schema() -> dict[str, list[str]]:
	"""Create every missing custom field. Returns what was created, per doctype."""
	created: dict[str, list[str]] = {}
	for doctype, specs in DERMA_CUSTOM_FIELDS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		for spec in specs:
			fieldname = spec["fieldname"]
			if has_field(doctype, fieldname):
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
