from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma import assessment
from do_derma.printing import inject, render
from do_derma.schema import ensure_derma_schema
from do_derma.tests.test_api import DermaTestHelpers
from do_derma.tests.test_config_workspace import ConfigTemplateHelpers
from do_derma.tests.test_consumables import ConsumableHelpers

LEGACY_BLOCK = """
<!-- do_derma:assessment -->
{% if doc.custom_derma_assessment_mode == "SOAP" %}
<div class="derma-soap"><h5>Assessment (SOAP)</h5></div>
{% endif %}

<!-- do_derma:assessment-structured -->
{% set derma_structured_values = [doc.custom_symptoms_notes] | select | list %}
{% if derma_structured_values %}
<div class="derma-structured"><h5>Assessment</h5></div>
{% endif %}
"""


class PrintingTestBase(DermaTestHelpers, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_derma_schema()

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")

	def _soap_encounter(self, **narratives):
		encounter = self._make_encounter(self._make_patient())
		encounter.set(assessment.MODE_FIELD, assessment.SOAP)
		for fieldname, value in narratives.items():
			encounter.set(fieldname, value)
		encounter.save(ignore_permissions=True)
		return encounter


class TestAssessmentPrintBlock(PrintingTestBase):
	def setUp(self):
		super().setUp()
		if not assessment.soap_is_supported():
			self.skipTest("SOAP custom fields are not installed on this site")

	def test_renders_soap_narratives_when_mode_is_soap(self):
		encounter = self._soap_encounter(
			custom_derma_soap_subjective="Itchy rash for three days",
			custom_derma_soap_objective="Erythematous plaques on both forearms",
			custom_derma_soap_assessment="Contact dermatitis",
			custom_derma_soap_plan="Topical steroid twice daily",
		)

		html = render.derma_assessment_html(encounter)

		self.assertIn("Assessment (SOAP)", html)
		self.assertIn("Itchy rash for three days", html)
		self.assertIn("Erythematous plaques on both forearms", html)
		self.assertIn("Contact dermatitis", html)
		self.assertIn("Topical steroid twice daily", html)

	def test_omits_structured_values_when_mode_is_soap(self):
		encounter = self._soap_encounter(
			custom_derma_soap_subjective="Itchy rash",
			custom_physical_examination="STRUCTURED-ONLY-MARKER",
		)

		html = render.derma_assessment_html(encounter)

		self.assertIn("Itchy rash", html)
		self.assertNotIn("STRUCTURED-ONLY-MARKER", html)

	def test_omits_empty_narratives(self):
		encounter = self._soap_encounter(custom_derma_soap_subjective="Only the subjective")

		html = render.derma_assessment_html(encounter)

		self.assertIn("Subjective", html)
		self.assertNotIn("Objective", html)
		self.assertNotIn("Plan", html)

	def test_escapes_html_in_narrative_fields(self):
		# Frappe's _sanitize_content already strips script tags on save, so the renderer is
		# asserted directly: it must escape whatever it is handed, sanitised or not.
		row = {"fieldtype": "Small Text", "fieldname": "custom_derma_soap_subjective"}

		escaped = render.format_field(row, "<script>alert('x')</script><b>bold</b>")

		self.assertNotIn("<script>", escaped)
		self.assertNotIn("<b>bold</b>", escaped)
		self.assertIn("&lt;script&gt;", escaped)

	def test_a_script_tag_never_reaches_the_printed_block(self):
		encounter = self._soap_encounter(
			custom_derma_soap_subjective="<script>alert('x')</script><b>bold</b>"
		)

		html = render.derma_assessment_html(encounter)

		self.assertNotIn("<script>", html)
		self.assertNotIn("<b>bold</b>", html)

	def test_newlines_become_line_breaks(self):
		encounter = self._soap_encounter(custom_derma_soap_plan="Line one\nLine two")

		html = render.derma_assessment_html(encounter)

		self.assertIn("Line one<br>Line two", html)

	def test_returns_empty_when_no_assessment_content(self):
		encounter = self._make_encounter(self._make_patient())

		self.assertEqual(render.derma_assessment_html(encounter), "")

	def test_renders_only_the_document_passed_in(self):
		other = self._soap_encounter(custom_derma_soap_subjective="OTHER-PATIENT-NARRATIVE")
		encounter = self._soap_encounter(custom_derma_soap_subjective="Mine alone")

		html = render.derma_assessment_html(encounter)

		self.assertIn("Mine alone", html)
		self.assertNotIn("OTHER-PATIENT-NARRATIVE", html)
		self.assertNotIn(other.name, html)

	def test_logs_and_returns_empty_on_failure(self):
		class Exploding:
			def get(self, *args, **kwargs):
				raise RuntimeError("boom")

		self.assertEqual(render.derma_assessment_html(Exploding()), "")


class TestStructuredPrintBlock(PrintingTestBase):
	def test_renders_structured_when_mode_is_structured(self):
		encounter = self._make_encounter(self._make_patient())
		encounter.set(assessment.MODE_FIELD, assessment.STRUCTURED)
		encounter.set("custom_physical_examination", "Plaques on both forearms")
		encounter.save(ignore_permissions=True)

		html = render.derma_assessment_html(encounter)

		self.assertIn("Plaques on both forearms", html)
		self.assertNotIn("(SOAP)", html)

	def test_renders_child_table_rows_comma_joined(self):
		diagnoses = [self._get_or_create_diagnosis(f"Derma Print {index}") for index in range(2)]
		encounter = self._make_encounter(self._make_patient())
		encounter.set(assessment.MODE_FIELD, assessment.STRUCTURED)
		encounter.set("custom_differential_diagnosis", [{"diagnosis": name} for name in diagnoses])
		encounter.save(ignore_permissions=True)

		html = render.derma_assessment_html(encounter)

		self.assertIn(f"{diagnoses[0]}, {diagnoses[1]}", html)

	def test_falls_back_to_other_mode_when_resolved_mode_is_empty(self):
		if not assessment.soap_is_supported():
			self.skipTest("SOAP custom fields are not installed on this site")
		encounter = self._make_encounter(self._make_patient())
		self._set_practitioner_default(encounter.practitioner, assessment.SOAP)
		encounter.set("custom_physical_examination", "Legacy structured content")
		encounter.save(ignore_permissions=True)

		self.assertEqual(assessment.get_assessment_mode(encounter), assessment.SOAP)
		self.assertIn("Legacy structured content", render.derma_assessment_html(encounter))

	def _set_practitioner_default(self, practitioner, mode):
		original = frappe.db.get_value(
			"Healthcare Practitioner", practitioner, assessment.PRACTITIONER_DEFAULT_FIELD
		)
		self.addCleanup(
			frappe.db.set_value,
			"Healthcare Practitioner",
			practitioner,
			assessment.PRACTITIONER_DEFAULT_FIELD,
			original,
		)
		frappe.db.set_value(
			"Healthcare Practitioner", practitioner, assessment.PRACTITIONER_DEFAULT_FIELD, mode
		)

	def _get_or_create_diagnosis(self, label):
		name = f"{label} {frappe.generate_hash(length=6)}"
		doc = frappe.get_doc({"doctype": "Diagnosis", "diagnosis": name}).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Diagnosis", doc.name, True)
		return doc.name


class TestPrintFormatInjection(PrintingTestBase):
	def _make_print_format(self, html="<div>Body</div>", **overrides):
		values = {
			"doctype": "Print Format",
			"name": f"Derma Test Format {frappe.generate_hash(length=8)}",
			"doc_type": "Patient Encounter",
			"module": "Do Derma",
			"standard": "No",
			"custom_format": 1,
			"print_format_type": "Jinja",
			"html": html,
		}
		values.update(overrides)
		doc = frappe.get_doc(values).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Print Format", doc.name, True)
		return doc.name

	def _html_of(self, name):
		return frappe.db.get_value("Print Format", name, "html") or ""

	def test_injects_block_once(self):
		name = self._make_print_format()

		inject.ensure_derma_blocks_in_print_formats()

		html = self._html_of(name)
		self.assertEqual(html.count(inject.ASSESSMENT.start), 1)
		self.assertEqual(html.count(inject.ASSESSMENT.end), 1)
		self.assertIn("derma_assessment_html(doc)", html)
		self.assertIn("<div>Body</div>", html)

	def test_injects_the_consumables_block_once_beside_the_assessment_block(self):
		name = self._make_print_format()

		inject.ensure_derma_blocks_in_print_formats()

		html = self._html_of(name)
		self.assertEqual(html.count(inject.CONSUMABLES.start), 1)
		self.assertEqual(html.count(inject.CONSUMABLES.end), 1)
		self.assertIn("derma_consumables_html(doc)", html)
		self.assertEqual(html.count(inject.ASSESSMENT.start), 1)

	def test_a_reverted_format_is_repaired_on_the_next_run(self):
		name = self._make_print_format()
		inject.ensure_derma_blocks_in_print_formats()
		repaired = self._html_of(name)
		frappe.db.set_value("Print Format", name, "html", "<div>Body</div>")

		inject.ensure_derma_blocks_in_print_formats()

		self.assertEqual(self._html_of(name), repaired)

	def test_second_run_is_a_no_op(self):
		name = self._make_print_format()
		inject.ensure_derma_blocks_in_print_formats()
		first_html = self._html_of(name)
		first_modified = frappe.db.get_value("Print Format", name, "modified")

		result = inject.ensure_derma_blocks_in_print_formats()

		self.assertIn(name, result["unchanged"])
		self.assertEqual(self._html_of(name), first_html)
		self.assertEqual(frappe.db.get_value("Print Format", name, "modified"), first_modified)

	def test_replaces_legacy_hand_injected_block(self):
		name = self._make_print_format(html=f"<div>Body</div>{LEGACY_BLOCK}")

		inject.ensure_derma_blocks_in_print_formats()

		html = self._html_of(name)
		self.assertNotIn("derma_structured_values", html)
		self.assertNotIn('class="derma-soap"', html)
		self.assertEqual(html.count(inject.ASSESSMENT.start), 1)
		self.assertIn("<div>Body</div>", html)

	def test_skips_print_format_builder_formats(self):
		name = self._make_print_format(print_format_builder=1)

		result = inject.ensure_derma_blocks_in_print_formats()

		self.assertNotIn(inject.ASSESSMENT.start, self._html_of(name))
		self.assertNotIn(name, result["updated"])

	def test_skips_disabled_formats(self):
		name = self._make_print_format(disabled=1)

		inject.ensure_derma_blocks_in_print_formats()

		self.assertNotIn(inject.ASSESSMENT.start, self._html_of(name))

	def test_skips_format_with_foreign_trailing_comment(self):
		name = self._make_print_format(
			html=f"<div>Body</div>{LEGACY_BLOCK}\n<!-- clinic footer -->\n<div>Footer</div>"
		)

		result = inject.ensure_derma_blocks_in_print_formats()

		self.assertIn(name, result["skipped"])
		self.assertIn("<!-- clinic footer -->", self._html_of(name))
		self.assertNotIn(inject.ASSESSMENT.start, self._html_of(name))

	def test_leaves_other_doctypes_alone(self):
		name = self._make_print_format(doc_type="Clinical Procedure")

		inject.ensure_derma_blocks_in_print_formats()

		self.assertNotIn(inject.ASSESSMENT.start, self._html_of(name))


class TestConsumablesPrintBlock(ConsumableHelpers, ConfigTemplateHelpers, PrintingTestBase):
	"""The paper record says what each procedure consumed, or says nothing at all."""

	def setUp(self):
		super().setUp()
		self.patient = self._make_patient()
		self.encounter = self._make_encounter(self.patient)

	def test_lists_item_quantity_unit_and_batch_grouped_by_procedure(self):
		item = self._make_stock_item(has_batch_no=1)
		batch = self._make_batch(item)
		template = self._make_consuming_template([])
		mark = self._make_mark(procedure_template=template, encounter=self.encounter.name)
		api.save_mark_consumables(
			mark.name, [{"item_code": item, "qty": 3, "uom": "Nos", "batch_no": batch}]
		)

		html = render.derma_consumables_html(self.encounter)

		self.assertIn("Consumables", html)
		self.assertIn(frappe.db.get_value("Clinical Procedure Template", template, "template"), html)
		self.assertIn("3 Nos", html)
		self.assertIn(batch, html)

	def test_renders_nothing_when_the_session_consumed_nothing(self):
		self.assertEqual(render.derma_consumables_html(self.encounter), "")

	def test_escapes_whatever_it_is_handed(self):
		lines = render.consumable_lines([{"item_name": "<b>Gauze</b>", "qty": 1, "uom": "Nos"}])

		self.assertNotIn("<b>", lines[0])
		self.assertIn("&lt;b&gt;", lines[0])

	def test_logs_and_returns_empty_on_failure(self):
		class Exploding:
			def get(self, *args, **kwargs):
				raise RuntimeError("boom")

		self.assertEqual(render.derma_consumables_html(Exploding()), "")


class TestPrintedEncounter(PrintingTestBase):
	def setUp(self):
		super().setUp()
		if not assessment.soap_is_supported():
			self.skipTest("SOAP custom fields are not installed on this site")

	def test_soap_note_reaches_the_rendered_print_format(self):
		name = f"Derma Test Format {frappe.generate_hash(length=8)}"
		doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": name,
				"doc_type": "Patient Encounter",
				"module": "Do Derma",
				"standard": "No",
				"custom_format": 1,
				"print_format_type": "Jinja",
				"html": "<div>Body</div>",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Print Format", doc.name, True)
		inject.ensure_derma_blocks_in_print_formats()
		encounter = self._soap_encounter(custom_derma_soap_plan="Topical steroid twice daily")

		printed = frappe.get_print("Patient Encounter", encounter.name, print_format=name)

		self.assertIn("Topical steroid twice daily", printed)
		self.assertIn("Assessment (SOAP)", printed)
