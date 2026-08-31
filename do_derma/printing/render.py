"""The assessment block a Patient Encounter print format renders.

Registered as the Jinja global `derma_assessment_html`, so a print format carries one
call instead of a copy of the field list. The layout comes from `assessment.py`, which
is the one owner of what each Assessment Mode contains.
"""

from typing import Any

import frappe
from frappe import _
from frappe.utils.formatters import format_value
from markupsafe import Markup, escape

from do_derma import assessment
from do_derma.consumables import encounter as encounter_consumables

# Fieldtypes whose stored value is already HTML, written through the desk form that owns
# them. None of the shipped assessment fields use one; a clinic that configures one into
# the Structured list gets it rendered, not escaped.
MARK_SAFE_FIELDTYPES = {"Text Editor", "HTML Editor", "Markdown Editor"}
FORMATTED_FIELDTYPES = {"Date", "Datetime", "Time", "Currency", "Float", "Int", "Percent"}


def derma_assessment_html(doc) -> Markup:
	"""Jinja global. The assessment block for one encounter, or empty."""
	try:
		encounter = doc if hasattr(doc, "get") else frappe.get_doc("Patient Encounter", doc)
		mode = assessment.get_assessment_mode(encounter)
		block = render_mode(encounter, mode)
		# A legacy encounter resolves to a mode it holds no content in. Never print a blank
		# heading over real clinical content written in the other mode.
		return block or render_mode(encounter, other_mode(mode))
	except Exception:
		# A raise here 500s the printview for every encounter, including ones with no derma
		# content at all. Degrade to nothing printed, loudly logged.
		frappe.log_error(title="Derma assessment print block", message=frappe.get_traceback())
		return Markup("")


def derma_consumables_html(doc) -> Markup:
	"""Jinja global. What each procedure on one encounter consumed, or empty."""
	try:
		encounter = doc if hasattr(doc, "get") else frappe.get_doc("Patient Encounter", doc)
		return render_consumables(encounter_consumables.get_encounter_consumables(encounter.get("name")))
	except Exception:
		# A raise here 500s the printview for every encounter, the same way it would for
		# the assessment block. Degrade to nothing printed, loudly logged.
		frappe.log_error(title="Derma consumables print block", message=frappe.get_traceback())
		return Markup("")


def render_consumables(groups: list[dict[str, Any]]) -> Markup:
	"""One paragraph per procedure, or empty when the session consumed nothing."""
	if not groups:
		return Markup("")
	paragraphs = [
		Markup("<p><b>{procedure}:</b> {lines}</p>").format(
			procedure=group["procedure"], lines=Markup(", ").join(consumable_lines(group["rows"]))
		)
		for group in groups
	]
	return (
		Markup('<div class="derma-consumables"><h5>{heading}</h5>').format(heading=_("Consumables"))
		+ Markup("").join(paragraphs)
		+ Markup("</div>")
	)


def consumable_lines(rows: list[dict[str, Any]]) -> list[Markup]:
	"""Item, quantity, unit and batch, so paper can be reconciled against a stock ledger."""
	lines = []
	for row in rows:
		text = " ".join(
			part
			for part in [
				str(row.get("item_name") or row.get("item_code") or ""),
				f"{frappe.utils.flt(row.get('qty')):g}",
				str(row.get("uom") or ""),
			]
			if part
		)
		if row.get("batch_no"):
			text = _("{0} (Batch {1})").format(text, row["batch_no"])
		lines.append(escape(text))
	return lines


def render_mode(encounter, mode: str) -> Markup:
	layout = assessment.get_layout(mode)
	values = assessment.serialize_values(encounter, layout)
	rows = [
		(row, format_field(row, values.get(row["fieldname"]))) for row in layout if row.get("is_value_field")
	]
	filled = [(row, text) for row, text in rows if text]
	if not filled:
		return Markup("")

	heading = _("Assessment (SOAP)") if mode == assessment.SOAP else _("Assessment")
	paragraphs = [
		Markup("<p><b>{label}:</b> ").format(label=row.get("label") or row["fieldname"])
		+ text
		+ Markup("</p>")
		for row, text in filled
	]
	css_class = "derma-soap" if mode == assessment.SOAP else "derma-structured"
	return (
		Markup('<div class="{css_class}"><h5>{heading}</h5>').format(css_class=css_class, heading=heading)
		+ Markup("").join(paragraphs)
		+ Markup("</div>")
	)


def other_mode(mode: str) -> str:
	return assessment.STRUCTURED if mode == assessment.SOAP else assessment.SOAP


def format_field(row: dict[str, Any], value: Any) -> Markup:
	"""One field's printable HTML. Every value is escaped here or nowhere."""
	fieldtype = row.get("fieldtype")
	if fieldtype in assessment.TABLE_FIELD_TYPES:
		return format_table(row, value)
	if value is None or value == "":
		return Markup("")
	if fieldtype == "Check":
		return Markup(_("Yes")) if frappe.utils.cint(value) else Markup("")
	if fieldtype in MARK_SAFE_FIELDTYPES:
		return Markup(value)
	if fieldtype in FORMATTED_FIELDTYPES:
		return escape(format_value(value, row))
	text = str(value).strip()
	return escape(text).replace("\n", Markup("<br>")) if text else Markup("")


def format_table(row: dict[str, Any], rows: Any) -> Markup:
	"""Child rows joined with commas, each shown through its list-view columns."""
	columns = display_columns(row.get("fields") or [])
	rendered = []
	for child in rows or []:
		parts = [escape(str(child.get(column)).strip()) for column in columns if child.get(column)]
		if parts:
			rendered.append(Markup(" ").join(parts))
	return Markup(", ").join(rendered)


def display_columns(fields: list[dict[str, Any]]) -> list[str]:
	value_fields = [
		field
		for field in fields
		if field.get("fieldname")
		and field.get("fieldtype") not in assessment.NO_VALUE_FIELD_TYPES
		and field.get("fieldtype") not in assessment.TABLE_FIELD_TYPES
	]
	listed = [field["fieldname"] for field in value_fields if field.get("in_list_view")]
	return listed or [field["fieldname"] for field in value_fields[:1]]
