import json

import frappe

from do_derma.patches.helpers import upsert_sidebar_item

SIDEBAR_ITEM = {
	"section": "Patient Actions",
	"label": "Derma Chart",
	"display_group": "Clinical",
	"description": "Open the dermatology encounter chart with structured body map findings and treatments.",
	"icon": "fa-regular fa-person-dots-from-line",
	"item_behavior": "Route",
	"route_type": "Custom",
	"route_value": "do_derma.openChart",
	"context_requirement": "patient",
	"missing_context_behavior": "Disable",
	"missing_context_message": "Select a patient first.",
	"requires_app": "do_derma",
	"sequence": 36,
	"is_footer_action": 1,
	"is_active": 1,
}


TEMPLATES = [
	{
		"title": "Acne Follow-up",
		"workflow": "Medical",
		"body_view": "Face Front",
		"default_finding_type": "Acne",
		"narrative_template": "Acne activity reviewed with distribution, lesion type, scarring, pigmentation, medication tolerance, and adherence.",
		"findings_json": [{"finding_type": "Acne", "body_region": "Face", "severity": "Moderate"}],
	},
	{
		"title": "Full Skin Exam",
		"workflow": "Medical",
		"body_view": "Body Front",
		"default_finding_type": "Lesion",
		"narrative_template": "Full skin examination performed. Lesions of concern were mapped, photographed when indicated, and follow-up plan reviewed.",
		"findings_json": [{"finding_type": "Lesion", "status": "Monitoring"}],
	},
	{
		"title": "Botox Treatment",
		"workflow": "Aesthetic",
		"body_view": "Face Front",
		"default_finding_type": "",
		"narrative_template": "Botulinum toxin treatment documented by facial region with units, product, lot number, consent, and follow-up plan.",
		"treatments_json": [
			{"workflow": "Aesthetic", "procedure_type": "Botox", "body_region": "Face", "dose_unit": "Units"}
		],
	},
	{
		"title": "Laser Session",
		"workflow": "Aesthetic",
		"body_view": "Face Front",
		"default_finding_type": "Pigmentation",
		"narrative_template": "Laser session documented with region, device settings, endpoint, tolerance, post-care instructions, and next session timing.",
		"treatments_json": [{"workflow": "Aesthetic", "procedure_type": "Laser", "dose_unit": "pass"}],
	},
]


def _upsert_templates():
	if not frappe.db.exists("DocType", "Derma Chart Template"):
		return

	for template in TEMPLATES:
		name = frappe.db.get_value("Derma Chart Template", {"title": template["title"]}, "name")
		payload = {
			"disabled": 0,
			"findings_json": json.dumps(template.get("findings_json", []), indent=2),
			"treatments_json": json.dumps(template.get("treatments_json", []), indent=2),
			**{
				key: value
				for key, value in template.items()
				if key not in {"findings_json", "treatments_json"}
			},
		}
		if name:
			frappe.db.set_value("Derma Chart Template", name, payload)
		else:
			frappe.get_doc({"doctype": "Derma Chart Template", **payload}).insert(ignore_permissions=True)


def execute():
	upsert_sidebar_item(SIDEBAR_ITEM)
	_upsert_templates()
