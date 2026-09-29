from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, now_datetime

ENCOUNTER_CONSENT = "Encounter Consent"
CONSENT_FORM = "Consent Form"
PROCEDURES_FIELD = "custom_derma_procedures"
SUMMARY_FIELDS = ["name", "consent_form_template", "status", "signed_by", "signed_on"]


class ConsentDoctype:
	"""The consent doctype this site writes: do_dental's Encounter Consent when installed, else Consent Form."""

	def __init__(self):
		self.name = ENCOUNTER_CONSENT if frappe.db.exists("DocType", ENCOUNTER_CONSENT) else CONSENT_FORM

	@property
	def is_installed(self) -> bool:
		return bool(frappe.db.exists("DocType", self.name))

	@property
	def is_encounter_consent(self) -> bool:
		return self.name == ENCOUNTER_CONSENT

	@property
	def procedures_field(self) -> str:
		return "procedure_items" if self.is_encounter_consent else PROCEDURES_FIELD

	def set_procedures(self, doc, procedures: list[dict[str, Any]]) -> None:
		for row in procedures:
			doc.append(self.procedures_field, row)
		if procedures and not self.is_encounter_consent:
			doc.clinical_procedure = procedures[0]["clinical_procedure"]
			doc.procedure_template = procedures[0].get("procedure_template")

	def render(self, doc, procedures: list[dict[str, Any]]) -> None:
		if self.is_encounter_consent:
			doc.render_template()
			return
		template = frappe.get_doc("Consent Form Template", doc.consent_form_template)
		doc.rendered_html = frappe.render_template(
			template.template_html or "", get_render_context(doc, procedures)
		)


def get_selected_procedures(values: dict[str, Any]) -> list[dict[str, Any]]:
	"""The payload's procedures, one row per distinct Clinical Procedure."""
	selected: dict[str, dict[str, Any]] = {}
	for row in values.get("procedure_items") or values.get("procedure_selection") or []:
		if isinstance(row, str):
			row = {"clinical_procedure": row}
		name = cstr(row.get("clinical_procedure") or row.get("value")).strip()
		if name and name not in selected:
			selected[name] = {
				"clinical_procedure": name,
				"procedure_template": row.get("procedure_template"),
				"display_name": row.get("display_name") or row.get("label") or name,
			}
	return list(selected.values())


def validate_procedures(
	procedures: list[dict[str, Any]], patient: str, encounter: str, encounter_field: str | None
) -> None:
	"""Every procedure must be a live one from this patient's visit."""
	if not procedures:
		frappe.throw(_("Select at least one procedure for this consent."), frappe.ValidationError)
	filters: dict[str, Any] = {
		"name": ["in", [row["clinical_procedure"] for row in procedures]],
		"patient": patient,
		"docstatus": ["<", 2],
	}
	if encounter_field:
		filters[encounter_field] = encounter
	templates = dict(
		frappe.get_all("Clinical Procedure", filters=filters, fields=["name", "procedure_template"], as_list=True)
	)
	foreign = [row["clinical_procedure"] for row in procedures if row["clinical_procedure"] not in templates]
	if foreign:
		frappe.throw(
			_("These procedures are not part of this visit: {0}").format(", ".join(foreign)),
			frappe.ValidationError,
		)
	for row in procedures:
		row["procedure_template"] = templates[row["clinical_procedure"]]


def get_render_context(doc, procedures: list[dict[str, Any]]) -> dict[str, Any]:
	"""Keys used by both do_health's Consent Form and do_dental's Encounter Consent templates."""
	patient = frappe.get_cached_doc("Patient", doc.patient).as_dict() if doc.get("patient") else frappe._dict()
	names = [row["display_name"] for row in procedures if row.get("display_name")]
	joined = ", ".join(names) or doc.get("procedure_template")
	return {
		"doc": doc,
		"patient": patient,
		"patient_name": patient.get("patient_name"),
		"encounter": doc.get("encounter"),
		"appointment": doc.get("appointment"),
		"company": doc.get("company"),
		"date": now_datetime(),
		"procedures": procedures,
		"procedure_names": names,
		"procedure": joined,
		"procedure_name": joined,
	}


def get_consent_coverage(procedure_names: list[str]) -> dict[str, list[dict[str, Any]]]:
	"""Signed consents covering each procedure, from every consent shape installed."""
	coverage: dict[str, list[dict[str, Any]]] = {}
	if not procedure_names:
		return coverage
	for doctype, links in get_consent_links(procedure_names).items():
		signed = frappe.get_all(
			doctype,
			filters={"name": ["in", list({parent for _procedure, parent in links})], "docstatus": 1},
			fields=SUMMARY_FIELDS,
		)
		by_name = {row.name: {**row, "doctype": doctype} for row in signed}
		for procedure, parent in sorted(links):
			found = by_name.get(parent)
			if found and found not in coverage.get(procedure, []):
				coverage.setdefault(procedure, []).append(found)
	return coverage


def get_consent_links(procedure_names: list[str]) -> dict[str, set[tuple[str, str]]]:
	"""(procedure, consent) pairs per consent doctype, signed or not."""
	links: dict[str, set[tuple[str, str]]] = {}
	for doctype, child_doctype, fieldname in get_procedure_tables():
		rows = frappe.get_all(
			child_doctype,
			filters={"parenttype": doctype, "parentfield": fieldname, "clinical_procedure": ["in", procedure_names]},
			fields=["clinical_procedure", "parent"],
		)
		links.setdefault(doctype, set()).update((row.clinical_procedure, row.parent) for row in rows)
	if frappe.db.exists("DocType", CONSENT_FORM):
		rows = frappe.get_all(
			CONSENT_FORM,
			filters={"clinical_procedure": ["in", procedure_names]},
			fields=["clinical_procedure", "name"],
		)
		links.setdefault(CONSENT_FORM, set()).update((row.clinical_procedure, row.name) for row in rows)
	return links


def get_procedure_tables() -> list[tuple[str, str, str]]:
	"""(consent doctype, child doctype, table field) for every consent procedure table installed."""
	tables = []
	for doctype, fieldname in ((ENCOUNTER_CONSENT, "procedure_items"), (CONSENT_FORM, PROCEDURES_FIELD)):
		if not frappe.db.exists("DocType", doctype):
			continue
		field = frappe.get_meta(doctype).get_field(fieldname)
		if field:
			tables.append((doctype, field.options, fieldname))
	return tables
