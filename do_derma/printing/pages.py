from __future__ import annotations

import frappe
from dateutil.relativedelta import relativedelta
from do_health.api.clinical_profile import build_clinical_profile
from frappe import _
from frappe.utils import escape_html, formatdate, getdate, today

from do_derma.printing.letterhead import (
	derma_letterhead_close,
	derma_letterhead_open,
	derma_practitioner_mark,
)

BODY_STYLE = "font-family:Arial,Helvetica,sans-serif;max-width:720px;margin:0 auto;color:#1a1a1a;line-height:1.4;padding:0 24px;"
DRAWING_PARENTS = ("Patient Encounter", "Clinical Procedure")
PRESCRIPTION_COLUMNS = (
	("dosage", "Dosage"),
	("period", "Duration"),
	("dosage_form", "Form"),
	("number_of_repeats_allowed", "Repeats"),
)
CELL_STYLE = "padding:6px 8px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top;"


def get_page(title: str, practitioner, body: str) -> dict[str, str]:
	"""A whole page: the Letter Head, the body, then the practitioner's mark."""
	# Joined as plain strings: adding a str to Markup would escape the body.
	html = "".join(
		[
			str(derma_letterhead_open(practitioner)),
			f'<div style="{BODY_STYLE}">{body}{derma_practitioner_mark(practitioner)}</div>',
			str(derma_letterhead_close(practitioner)),
		]
	)
	return {"title": title, "html": html}


def get_identity_line(parts: list) -> str:
	"""Who and what a sheet is for, so a paper copy can be filed. Escapes every part."""
	text = " · ".join(escape_html(str(part)) for part in parts if part)
	return f'<p style="margin:0 0 16px;color:#475569;font-size:13px;">{text}</p>'


def get_practitioner(*sources: tuple[str, str | None]):
	"""The Healthcare Practitioner of the first linked record that names one."""
	for doctype, name in sources:
		practitioner = name and frappe.db.get_value(doctype, name, "practitioner")
		if practitioner:
			return frappe.get_doc("Healthcare Practitioner", practitioner)
	return None


def get_patient_page(patient: str | None, encounter: str | None, title: str, body: str, practitioner) -> dict[str, str]:
	"""A consent-style page: patient, MRN and encounter above the body."""
	patient_name = frappe.db.get_value("Patient", patient, "patient_name") if patient else ""
	identity = get_identity_line([patient_name, f"{_('MRN')}: {patient}" if patient else "", encounter])
	return get_page(" - ".join(filter(None, [patient_name, title])), practitioner, identity + body)


def get_consent_page(doc) -> dict[str, str]:
	practitioner = get_practitioner(
		("Patient Encounter", doc.get("encounter")), ("Clinical Procedure", doc.get("clinical_procedure"))
	)
	title = doc.get("consent_form_template") or _("Consent Form")
	return get_patient_page(doc.get("patient"), doc.get("encounter"), title, doc.get("rendered_html") or "", practitioner)


def get_blank_consent_page(encounter: str, body: str | None) -> dict[str, str]:
	"""The unsaved consent the Consent panel built. Not sanitised: it returns only to its sender's window."""
	if not (body or "").strip():
		frappe.throw(_("Nothing to print: the consent preview is empty."), frappe.ValidationError)
	doc = frappe.get_doc("Patient Encounter", encounter)
	practitioner = get_practitioner(("Patient Encounter", doc.name))
	return get_patient_page(doc.patient, doc.name, _("Consent Form"), body, practitioner)


def get_annotation_page(name: str) -> dict[str, str]:
	"""A saved drawing with its legend, for the paper file."""
	annotation = frappe.get_doc("Health Annotation", name)
	row = frappe.db.get_value(
		"Health Annotation Table",
		{"annotation": name, "parenttype": ["in", DRAWING_PARENTS]},
		["parent", "parenttype", "annotation_data"],
		as_dict=True,
		order_by="creation desc",
	) or frappe._dict()
	practitioner = get_practitioner((row.parenttype, row.parent)) if row.parent else None
	patient = frappe.db.get_value(row.parenttype, row.parent, "patient") if row.parent else None
	patient_name = frappe.db.get_value("Patient", patient, "patient_name") if patient else ""
	label = annotation.get("custom_derma_body_template_title") or annotation.get("annotation_template") or _("Drawing")
	identity = get_identity_line(
		[
			f"{_('MRN')}: {patient}" if patient else "",
			label,
			formatdate(annotation.creation),
			practitioner and practitioner.practitioner_name,
			row.parent if row.parenttype == "Patient Encounter" else "",
		]
	)
	image = annotation.get("image")
	body = (
		f'<h2 style="margin:0 0 4px;">{escape_html(patient_name)}</h2>'
		+ identity
		+ (f'<img src="{escape_html(image)}" style="max-width:100%;max-height:60vh;" alt="">' if image else "")
		# The legend is escaped when it is generated.
		+ f'<div style="margin-top:16px;">{row.annotation_data or ""}</div>'
	)
	return get_page(" - ".join(filter(None, [patient_name, label])), practitioner, body)


def get_prescription_page(encounter: str) -> dict[str, str]:
	"""The visit's saved medications, standalone enough for an outside pharmacy."""
	doc = frappe.get_doc("Patient Encounter", encounter)
	rows = [row for row in doc.get("drug_prescription") or [] if row.medication]
	if not rows:
		frappe.throw(_("No medications to print: save the prescription first."), frappe.ValidationError)
	patient = frappe.get_doc("Patient", doc.patient)
	practitioner = get_practitioner(("Patient Encounter", doc.name))
	identity = get_identity_line(
		[
			f"{_('MRN')}: {patient.name}",
			patient.get("custom_cpr") and f"{_('CPR')}: {patient.custom_cpr}",
			patient.dob and _("{0} y").format(relativedelta(getdate(today()), getdate(patient.dob)).years),
			patient.sex,
			formatdate(doc.encounter_date),
			practitioner and practitioner.practitioner_name,
		]
	)
	body = (
		f'<h2 style="margin:0 0 4px;">&#8478; {escape_html(_("Prescription"))}</h2>'
		f'<h3 style="margin:0 0 4px;">{escape_html(patient.patient_name)}</h3>'
		+ identity
		+ get_allergy_line(patient)
		+ get_prescription_table(rows)
	)
	return get_page(" - ".join([patient.patient_name, _("Prescription")]), practitioner, body)


def get_allergy_line(patient) -> str:
	profile = build_clinical_profile(patient)
	allergens = [row["allergen"] for row in profile["allergies"]]
	if allergens:
		text, colour = ", ".join(allergens), "#b91c1c"
	else:
		text = _("None known") if profile["allergy_status"] == "none_known" else _("Not recorded")
		colour = "#475569"
	label = escape_html(_("Allergies"))
	return f'<p style="margin:0 0 16px;font-size:13px;color:{colour};"><strong>{label}:</strong> {escape_html(text)}</p>'


def get_prescription_table(rows) -> str:
	headings = ["#", _("Medication"), *(_(label) for _field, label in PRESCRIPTION_COLUMNS)]
	head = "".join(f'<th style="{CELL_STYLE}">{escape_html(heading)}</th>' for heading in headings)
	lines = []
	for index, row in enumerate(rows, start=1):
		medication = f"<strong>{escape_html(row.medication)}</strong>"
		if row.comment:
			medication += f'<div style="font-style:italic;color:#475569;">{escape_html(row.comment)}</div>'
		cells = [str(index), medication]
		cells += [escape_html(str(row.get(field) or "—")) for field, _label in PRESCRIPTION_COLUMNS]
		lines.append("<tr>" + "".join(f'<td style="{CELL_STYLE}">{cell}</td>' for cell in cells) + "</tr>")
	return (
		'<table style="width:100%;border-collapse:collapse;font-size:13px;">'
		f"<thead><tr>{head}</tr></thead><tbody>{''.join(lines)}</tbody></table>"
	)
