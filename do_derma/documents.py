"""AI-written letters for one encounter, issued as do_health Patient Official Documents.

Four kinds - medical report, referral letter, patient education, patient explainer -
are drafted by the same LLM the voice scribe uses, from the saved note, the transcript
and the patient's earlier visits. Each draft becomes a Patient Official Document
(Draft); issuing it renders the seeded print template, attaches the PDF and stamps
the audit fields, exactly as any other clinic document.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, getdate

from do_derma import assessment, voice
from do_derma.assessment import HP, SOAP
from do_derma.schema import VOICE_TRANSCRIPT_FIELD

TEMPLATE_PREFIX = "Derma AI "
HISTORY_LIMIT = 5
KINDS: dict[str, dict[str, str]] = {
	"report": {"title": "Medical Report", "document_type": "Medical Report"},
	"referral": {"title": "Referral Letter", "document_type": "Referral Letter"},
	"education": {"title": "Patient Education Material", "document_type": "Patient Education Material"},
	"explainer": {"title": "Patient Explainer Letter", "document_type": "Patient Explainer Letter"},
}

DOC_COMMON = """You are SOULVD Health, the clinical documentation assistant of {clinic}, a dermatology clinic in {country}.

GROUNDING RULES (mandatory):
- Use ONLY the consultation note, patient data, prior-visit summaries and transcript you are given. Never invent findings, medications, doses, dates, results, or history. Where information is missing, omit the line or write "Not documented".
- Professional, clear English. No markdown other than "## " for the headings named below and "- " for list lines. No tables, no bold, no code fences.
- Use the clinician name, clinician title and clinic name exactly as passed in for any sign-off.
- Also produce text_ar: a faithful Arabic version of the same document (same structure and headings, translated; clinical Arabic as used in {country}; patient-facing letters in warm plain Arabic).
- Respond with ONLY a valid JSON object, no commentary: {"text": "...", "text_ar": "..."}"""

DOC_PROMPTS: dict[str, str] = {
	"report": DOC_COMMON
	+ """

TASK: Write a formal Medical Report for the patient with exactly these H2 sections in this order:
## Patient Demographic Data
## Past Medical and Surgical History
## Medications
## Allergies
## Vital Signs and Present Medical Condition and Management
## Summary of Reports in Chronological Order
Use the heading lines above verbatim. Demographic Data = name, MRN, age, gender (only the fields provided). Vital Signs section = vitals only if documented, then current condition (diagnosis), examination findings and the management given. Chronological Summary = one paragraph per visit, oldest first, each starting with the visit date, covering the prior visits provided and ending with the current visit.
Close with the clinician name and title on two separate lines.""",
	"referral": DOC_COMMON
	+ """

TASK: Write a Referral Letter following this exact structure and wording, as plain paragraphs (no headings except the two labelled lines):
Dear Dr. <addressee>,   (if no addressee given use "Dear Colleague,")
Thank you for seeing the patient below.
I am writing to refer my patient who is known with <condition(s)> and currently using <current treatment>.
They presented today with <presenting complaint>.
Clinical Summary: <one paragraph - history, examination findings, assessment>
Investigations: <"- " lines of investigations done or requested; "- None documented" if none>
Referral Details: <one paragraph - what the referral is for and the specific question or action requested>
Thank you for your attention to this matter.
Yours sincerely,
<clinician name>
<clinician title>
<clinic name>""",
	"education": DOC_COMMON
	+ """

TASK: Write Patient Education Material about the patient's primary condition (from the diagnosis), in plain lay English a patient can read at home. Structure exactly:
## Patient Education Material on <condition>
## What is <condition>?
<one or two paragraphs>
## Symptoms of <condition>
<"- " lines>
## Management and Lifestyle Recommendations
<one intro sentence, then "- " lines, each starting with a short lead-in followed by a colon, e.g. "- Sun Protection: ...">
Tailor recommendations to the plan actually given in the note. Do not mention any treatment the note does not contain. No disclaimers.""",
	"explainer": DOC_COMMON
	+ """

TASK: Write a Patient Explainer Letter addressed to the patient, warm and plain-English, following this exact structure:
Dear <patient first name>,
It was a pleasure to see you today and review your health concerns. I appreciate the time you took to share details about your health and personal life. I've summarised our discussion below to help you remember what we covered.
## Topic/Issue #1: <title>
<paragraph>
(2 to 4 topics in total, numbered #1, #2, ... - each a distinct issue discussed in the visit)
## Next Steps:
<"- " lines: treatments, how to use them, investigations, follow-up date if given>
Thank you for trusting me with your care. If you have any questions or concerns about anything we discussed, please do not hesitate to reach out.
Warm regards,
<clinician name>
<clinician title>
<clinic name>""",
}

# Jinja source of the seeded print templates. `values.body` is the AI text; "## " lines
# become headings and "- " lines become bullets, everything else a paragraph.
TEMPLATE_VERSION = 2
TEMPLATE_MARKER = "<!-- derma-ai-letter v"
LETTER_TEMPLATE = f"""{TEMPLATE_MARKER}{TEMPLATE_VERSION} -->
""" + """<div style="font-family:Arial,Helvetica,sans-serif;max-width:720px;margin:0 auto;color:#1a1a1a;line-height:1.55;padding:24px;">
  <table style="width:100%;border-bottom:2px solid #1a3a5c;padding-bottom:10px;margin-bottom:22px;"><tr>
    <td style="vertical-align:bottom;">
      <div style="font-size:18px;font-weight:700;color:#1a3a5c;">{{ (company and company.company_name) or (clinic and clinic.custom_clinic_name_en) or '' }}</div>
      <div style="font-size:11px;color:#666;">{{ (clinic and clinic.custom_clinic_address) or '' }}</div>
    </td>
    <td style="vertical-align:bottom;text-align:right;font-size:12px;color:#666;">{{ today }}</td>
  </tr></table>
  <h1 style="font-size:20px;color:#1a3a5c;margin:0 0 14px;">{{ values.title }}</h1>
  <table style="width:100%;font-size:12px;margin-bottom:18px;border:1px solid #e5e7eb;"><tr>
    <td style="padding:6px 10px;"><b>Patient:</b> {{ patient.patient_name if patient else '' }}</td>
    <td style="padding:6px 10px;"><b>MRN:</b> {{ patient.name if patient else '' }}</td>
    <td style="padding:6px 10px;"><b>Visit:</b> {{ encounter.encounter_date if encounter else today }}</td>
    <td style="padding:6px 10px;"><b>Clinician:</b> {{ practitioner.practitioner_name if practitioner else '' }}</td>
  </tr></table>
  <div style="font-size:13px;">
  {% for line in (values.body or '').split('\\n') %}
    {% if line.startswith('## ') %}<h2 style="font-size:14px;color:#1a3a5c;margin:16px 0 6px;">{{ line[3:] }}</h2>
    {% elif line.startswith('- ') %}<div style="padding-left:16px;text-indent:-10px;margin:2px 0;">&bull; {{ line[2:] }}</div>
    {% elif line.strip() %}<p style="margin:6px 0;">{{ line }}</p>{% endif %}
  {% endfor %}
  </div>
  <div style="margin-top:40px;font-size:12px;">
    <div style="border-top:1px solid #333;width:240px;padding-top:6px;">{{ practitioner.practitioner_name if practitioner else '' }}<br>
      <span style="color:#666;">{{ (practitioner and practitioner.designation) or '' }}</span></div>
  </div>
  {% if values.body_ar %}
  <div dir="rtl" style="page-break-before:always;font-size:13px;padding-top:12px;">
    <h1 style="font-size:20px;color:#1a3a5c;margin:0 0 14px;">{{ values.title }}</h1>
    {% for line in values.body_ar.split('\\n') %}
      {% if line.startswith('## ') %}<h2 style="font-size:14px;color:#1a3a5c;margin:16px 0 6px;">{{ line[3:] }}</h2>
      {% elif line.startswith('- ') %}<div style="padding-right:16px;margin:2px 0;">&bull; {{ line[2:] }}</div>
      {% elif line.strip() %}<p style="margin:6px 0;">{{ line }}</p>{% endif %}
    {% endfor %}
  </div>
  {% endif %}
</div>"""


@frappe.whitelist()
def generate_document(kind: str, encounter: str, addressee: str | None = None) -> dict[str, Any]:
	voice.require_enabled()
	spec = KINDS.get(kind)
	if not spec:
		frappe.throw(_("Unknown document kind: {0}").format(kind))
	encounter_doc = frappe.get_doc("Patient Encounter", encounter)
	if not frappe.has_permission("Patient Encounter", "write", encounter_doc):
		frappe.throw(_("Not permitted to write documents for this encounter."), frappe.PermissionError)

	context = build_document_context(encounter_doc, addressee)
	raw, usage = voice.chat_complete_with_usage(voice.fill_clinic(DOC_PROMPTS[kind], encounter_doc.company), build_document_prompt(kind, context))
	parsed = voice.safe_parse_json(raw)
	text = cstr((parsed or {}).get("text")).strip()
	text_ar = cstr((parsed or {}).get("text_ar")).strip()
	if not text:
		voice.record_usage("Document", encounter=encounter_doc.name, patient=encounter_doc.patient, status="Failed", error=f"unparseable {kind}", **usage)
		frappe.log_error(title=f"AI document: unparseable {kind}", message=raw[:4000])
		frappe.throw(_("The document could not be generated. Please try again."))
	voice.record_usage("Document", encounter=encounter_doc.name, patient=encounter_doc.patient, **usage)

	doc = frappe.get_doc(
		{
			"doctype": "Patient Official Document",
			"document_type": spec["document_type"],
			"print_template": template_name(kind),
			"patient": encounter_doc.patient,
			"appointment": encounter_doc.appointment,
			"encounter": encounter_doc.name,
			"practitioner": encounter_doc.practitioner,
			"company": encounter_doc.company,
			"values_json": json.dumps({"title": spec["title"], "body": text, "body_ar": text_ar, "addressee": cstr(addressee)}),
		}
	).insert()
	return serialize_document(doc)


@frappe.whitelist()
def queue_document(kind: str, encounter: str, addressee: str | None = None) -> dict[str, str]:
	voice.require_enabled()
	return voice.enqueue_ai_job("do_derma.documents.document_job", kind=kind, encounter=encounter, addressee=addressee)


def document_job(job: str, kind: str, encounter: str, addressee: str | None) -> None:
	voice.run_ai_job(job, lambda: generate_document(kind, encounter, addressee))


@frappe.whitelist()
def list_documents(encounter: str) -> list[dict[str, Any]]:
	from do_derma.api import _ensure_clinical_access  # lazy: api imports this module

	_ensure_clinical_access()
	rows = frappe.get_all(
		"Patient Official Document",
		filters={"encounter": encounter, "docstatus": ["<", 2], "print_template": ["like", f"{TEMPLATE_PREFIX}%"]},
		fields=["name", "document_type", "status", "docstatus", "creation", "issued_pdf_file", "values_json"],
		order_by="creation desc",
	)
	return [serialize_document(frappe._dict(row)) for row in rows]


@frappe.whitelist()
def issue_document(name: str) -> dict[str, Any]:
	doc = frappe.get_doc("Patient Official Document", name)
	if not frappe.has_permission("Patient Official Document", "submit", doc):
		frappe.throw(_("Not permitted to issue this document."), frappe.PermissionError)
	doc.submit()
	return serialize_document(doc)


def serialize_document(doc) -> dict[str, Any]:
	values = doc.get_values() if callable(getattr(doc, "get_values", None)) else json.loads(doc.get("values_json") or "{}")
	pdf = doc.get("issued_pdf_file")
	return {
		"name": doc.name,
		"document_type": doc.get("document_type"),
		"status": doc.get("status"),
		"docstatus": doc.get("docstatus"),
		"creation": cstr(doc.get("creation")),
		"title": values.get("title") or doc.get("document_type"),
		"body": values.get("body") or "",
		"body_ar": values.get("body_ar") or "",
		"pdf_url": frappe.db.get_value("File", pdf, "file_url") if pdf else "",
	}


def template_name(kind: str) -> str:
	title = TEMPLATE_PREFIX + KINDS[kind]["title"]
	name = frappe.db.get_value("Patient Print Template", {"title": title, "is_active": 1}, "name")
	if not name:
		frappe.throw(_("Print template {0} is missing. Run bench migrate.").format(title))
	return name


def build_document_context(encounter_doc, addressee: str | None = None) -> dict[str, Any]:
	practitioner = (
		frappe.db.get_value("Healthcare Practitioner", encounter_doc.practitioner, ["practitioner_name", "designation"], as_dict=True)
		if encounter_doc.practitioner
		else None
	) or {}
	patient = voice.patient_context(encounter_doc.patient)
	patient["mrn"] = encounter_doc.patient
	return {
		"patient": patient,
		"doctor": practitioner.get("practitioner_name") or "",
		"doctor_title": practitioner.get("designation") or "Dermatologist",
		"clinic": voice.clinic_context(encounter_doc.company)["clinic"],
		"visit_date": cstr(encounter_doc.encounter_date),
		"addressee": cstr(addressee),
		"diagnosis": current_diagnosis(encounter_doc),
		"note": note_text(encounter_doc),
		"transcript": cstr(encounter_doc.get(VOICE_TRANSCRIPT_FIELD)),
		"history": visit_history(encounter_doc),
	}


def build_document_prompt(kind: str, context: dict[str, Any]) -> str:
	parts = [f"DOCUMENT REQUESTED: {KINDS[kind]['title']}"]
	parts.append(f"CLINICIAN: {context['doctor']}\nCLINICIAN TITLE: {context['doctor_title']}\nCLINIC: {context['clinic']}")
	if kind == "referral" and context.get("addressee"):
		parts.append(f"ADDRESSEE (referral recipient): {context['addressee']}")
	if context.get("visit_date"):
		parts.append(f"VISIT DATE: {context['visit_date']}")
	patient = context.get("patient") or {}
	bits = [f"{label}: {patient[key]}" for label, key in (("Name", "name"), ("MRN", "mrn"), ("Age", "age"), ("Gender", "gender")) if patient.get(key)]
	if bits:
		parts.append("PATIENT DATA:\n" + "\n".join(bits))
	if context.get("diagnosis"):
		parts.append(f"DIAGNOSIS: {context['diagnosis']}")
	if context.get("history"):
		parts.append("PRIOR VISITS (oldest first):\n" + "\n\n".join(f"[{h['date']}]\n{h['note']}" for h in context["history"]))
	if context.get("note"):
		parts.append(f'CURRENT VISIT NOTE:\n"""\n{context["note"]}\n"""')
	if context.get("transcript"):
		parts.append(f'TRANSCRIPT (grounding reference only, do not quote):\n"""\n{context["transcript"][:6000]}\n"""')
	parts.append("Return the JSON object now.")
	return "\n\n".join(parts)


def note_text(encounter_doc) -> str:
	"""The visit note as labelled lines, from the stamped mode first, then any mode with content."""
	mode = assessment.get_assessment_mode(encounter_doc)
	for candidate in (mode, *[m for m in assessment.ASSESSMENT_MODES if m != mode]):
		lines = [
			f"{row['label']}: {cstr(encounter_doc.get(row['fieldname'])).strip()}"
			for row in assessment.get_layout(candidate)
			if row.get("is_value_field") and row.get("fieldtype") not in assessment.TABLE_FIELD_TYPES and cstr(encounter_doc.get(row["fieldname"])).strip()
		]
		if lines:
			return "\n".join(lines)
	return ""


def current_diagnosis(encounter_doc) -> str:
	for fieldname in ("custom_derma_soap_assessment", "custom_derma_hp_assessment"):
		value = cstr(encounter_doc.get(fieldname)).strip()
		if value:
			return value.splitlines()[0][:200]
	rows = encounter_doc.get("diagnosis") or []
	return ", ".join(cstr(row.get("diagnosis")) for row in rows if row.get("diagnosis"))


def visit_history(encounter_doc) -> list[dict[str, str]]:
	free_text_fields = [field for fields in assessment.MODE_FIELDS.values() for field in fields if assessment.has_field("Patient Encounter", field)]
	if not free_text_fields:
		return []
	rows = frappe.get_all(
		"Patient Encounter",
		filters={"patient": encounter_doc.patient, "name": ["!=", encounter_doc.name], "docstatus": ["<", 2]},
		fields=["name", "encounter_date", *free_text_fields],
		order_by="encounter_date desc, creation desc",
		limit=HISTORY_LIMIT,
	)
	history = []
	for row in reversed(rows):
		note = "\n".join(f"{field.split('_')[-1].title()}: {cstr(row.get(field)).strip()}" for field in free_text_fields if cstr(row.get(field)).strip())
		if note:
			history.append({"date": cstr(getdate(row.encounter_date)), "note": note[:1200]})
	return history


def ensure_document_templates() -> list[str]:
	"""Seed one print template per kind. Idempotent; a clinic's edits are kept."""
	if not frappe.db.exists("DocType", "Patient Print Template"):
		return []
	created = []
	for spec in KINDS.values():
		title = TEMPLATE_PREFIX + spec["title"]
		existing = frappe.db.get_value("Patient Print Template", {"title": title}, ["name", "template_source_code"], as_dict=True)
		if existing:
			# Our own older version is upgraded; a clinic-edited template (marker removed) is kept.
			source = existing.template_source_code or ""
			if TEMPLATE_MARKER in source and f"{TEMPLATE_MARKER}{TEMPLATE_VERSION} -->" not in source:
				frappe.db.set_value("Patient Print Template", existing.name, {"template_source_code": LETTER_TEMPLATE, "template_html": LETTER_TEMPLATE})
				created.append(f"{title} (upgraded)")
			continue
		frappe.get_doc(
			{
				"doctype": "Patient Print Template",
				"title": title,
				"category": "Other",
				"is_active": 1,
				"version": 1,
				"template_editor_mode": "HTML / Jinja",
				"template_source_code": LETTER_TEMPLATE,
				"template_html": LETTER_TEMPLATE,
				"variables": [
					{"variable_name": "title", "variable_label": "Title", "variable_type": "Data", "is_required": 1},
					{"variable_name": "body", "variable_label": "Body", "variable_type": "Data", "is_required": 1},
					{"variable_name": "body_ar", "variable_label": "Body (Arabic)", "variable_type": "Data"},
					{"variable_name": "addressee", "variable_label": "Addressee", "variable_type": "Data"},
				],
			}
		).insert(ignore_permissions=True)
		created.append(title)
	return created
