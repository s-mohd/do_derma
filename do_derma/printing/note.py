"""Printable assessment note: the format on screen, on the clinic's letterhead.

One standard Print Format on Patient Encounter. The body is the same block the
existing print injection uses (`derma_assessment_html`), so it always prints the
format the encounter is documented in - what the doctor sees is what prints.
"""

import frappe

PRINT_FORMAT = "Derma Assessment Note"
TEMPLATE_MARKER = "<!-- derma-assessment-note v"
TEMPLATE_VERSION = 2

TEMPLATE = f"""{TEMPLATE_MARKER}{TEMPLATE_VERSION} -->
""" + """
{%- set company = frappe.get_doc("Company", doc.company) if doc.company else None -%}
{%- set patient = frappe.get_doc("Patient", doc.patient) if doc.patient else None -%}
{%- set practitioner = frappe.get_doc("Healthcare Practitioner", doc.practitioner) if doc.practitioner else None -%}
<div style="font-family:Arial,Helvetica,sans-serif;max-width:720px;margin:0 auto;color:#1a1a1a;line-height:1.55;padding:24px;">
  <table style="width:100%;border-bottom:2px solid #1a3a5c;padding-bottom:10px;margin-bottom:22px;"><tr>
    <td style="vertical-align:bottom;font-size:18px;font-weight:700;color:#1a3a5c;">{{ (company and company.company_name) or '' }}</td>
    <td style="vertical-align:bottom;text-align:right;font-size:12px;color:#666;">{{ frappe.utils.formatdate(doc.encounter_date) }}</td>
  </tr></table>
  <table style="width:100%;font-size:12px;margin-bottom:18px;border:1px solid #e5e7eb;"><tr>
    <td style="padding:6px 10px;"><b>Patient:</b> {{ (patient and patient.patient_name) or '' }}</td>
    <td style="padding:6px 10px;"><b>MRN:</b> {{ doc.patient }}</td>
    <td style="padding:6px 10px;"><b>Visit:</b> {{ frappe.utils.formatdate(doc.encounter_date) }}</td>
    <td style="padding:6px 10px;"><b>Clinician:</b> {{ (practitioner and practitioner.practitioner_name) or '' }}</td>
  </tr></table>
  <div style="font-size:13px;">{{ derma_assessment_html(doc) }}</div>
  <div style="margin-top:40px;font-size:12px;">
    <div style="border-top:1px solid #333;width:240px;padding-top:6px;">{{ (practitioner and practitioner.practitioner_name) or '' }}<br>
      <span style="color:#666;">{{ (practitioner and practitioner.designation) or '' }}</span></div>
  </div>
</div>
"""


def ensure_assessment_print_format() -> str:
	"""Seed the print format once. A clinic's own edit (marker removed) is kept."""
	existing = frappe.db.get_value("Print Format", PRINT_FORMAT, ["name", "html"], as_dict=True)
	if existing:
		html = existing.html or ""
		if TEMPLATE_MARKER in html and f"{TEMPLATE_MARKER}{TEMPLATE_VERSION} -->" not in html:
			frappe.db.set_value("Print Format", existing.name, "html", TEMPLATE)
			return f"{PRINT_FORMAT} (upgraded)"
		return ""
	frappe.get_doc(
		{
			"doctype": "Print Format",
			"name": PRINT_FORMAT,
			"doc_type": "Patient Encounter",
			"module": "Do Derma",
			"print_format_type": "Jinja",
			"custom_format": 1,
			"standard": "No",
			"html": TEMPLATE,
		}
	).insert(ignore_permissions=True)
	return PRINT_FORMAT
