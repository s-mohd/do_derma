"""Printable assessment note: the format on screen, on the clinic's letterhead.

One standard Print Format on Patient Encounter. The body is the same block the
existing print injection uses (`derma_assessment_html`), so it always prints the
format the encounter is documented in - what the doctor sees is what prints.
"""

import frappe

from do_derma.assessment import HP, SOAP, STRUCTURED

PRINT_FORMAT = "Derma Assessment Note"  # prints whichever format the visit is documented in
# One print per report type - never mixed. The chart's Print button picks by the open tab.
PRINT_FORMATS = {
	HP: "Derma Assessment Note (H&P)",
	SOAP: "Derma Assessment Note (SOAP)",
	STRUCTURED: "Derma Assessment Note (Structured)",
}
TEMPLATE_MARKER = "<!-- derma-assessment-note v"
TEMPLATE_VERSION = 4

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
  {%- if doc.custom_derma_print_patient_advice and (doc.custom_derma_patient_advice or doc.custom_derma_patient_advice_ar) %}
  <div style="font-size:13px;margin-top:18px;padding-top:12px;border-top:1px solid #e5e7eb;">
    <h2 style="font-size:14px;color:#1a3a5c;margin:0 0 6px;">Patient Advice</h2>
    {% if doc.custom_derma_patient_advice %}<div style="white-space:pre-wrap;">{{ doc.custom_derma_patient_advice | e }}</div>{% endif %}
    {% if doc.custom_derma_patient_advice_ar %}<div dir="rtl" style="white-space:pre-wrap;margin-top:10px;">{{ doc.custom_derma_patient_advice_ar | e }}</div>{% endif %}
  </div>
  {%- endif %}
  <div style="margin-top:40px;font-size:12px;">
    <div style="border-top:1px solid #333;width:240px;padding-top:6px;">{{ (practitioner and practitioner.practitioner_name) or '' }}<br>
      <span style="color:#666;">{{ (practitioner and practitioner.designation) or '' }}</span></div>
  </div>
</div>
"""


def template_for(mode: str | None) -> str:
	"""The letter template pinned to one report type, or the documented-format one."""
	if not mode:
		return TEMPLATE
	return TEMPLATE.replace("derma_assessment_html(doc)", f'derma_assessment_html(doc, "{mode}")')


def ensure_assessment_print_format() -> str:
	"""Seed the print formats once. A clinic's own edit (marker removed) is kept."""
	done = []
	for mode, name in ((None, PRINT_FORMAT), *PRINT_FORMATS.items()):
		outcome = _ensure_format(name, template_for(mode))
		if outcome:
			done.append(outcome)
	return ", ".join(done)


def _ensure_format(name: str, html: str) -> str:
	existing = frappe.db.get_value("Print Format", name, ["name", "html"], as_dict=True)
	if existing:
		current = existing.html or ""
		if TEMPLATE_MARKER in current and f"{TEMPLATE_MARKER}{TEMPLATE_VERSION} -->" not in current:
			frappe.db.set_value("Print Format", existing.name, "html", html)
			return f"{name} (upgraded)"
		return ""
	frappe.get_doc(
		{
			"doctype": "Print Format",
			"name": name,
			"doc_type": "Patient Encounter",
			"module": "Do Derma",
			"print_format_type": "Jinja",
			"custom_format": 1,
			"standard": "No",
			"html": html,
		}
	).insert(ignore_permissions=True)
	return name
