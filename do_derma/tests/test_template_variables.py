from __future__ import annotations

import json

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma.patches.materialize_derma_template_required_fields import (
	execute as materialize_required_fields,
)
from do_derma.tests.test_config_workspace import ConfigTemplateHelpers


class TestRequiredFieldOwners(IntegrationTestCase):
	"""Required fields have one owner - the template's own JSON - plus the two safety
	flags, which stay authoritative because the procedure-creation gate re-checks them."""

	def test_the_template_owns_what_it_declares(self):
		owners = api._required_field_owners({"custom_derma_required_fields": json.dumps(["dose"])})

		self.assertEqual(owners, [{"fieldname": "dose", "source": "template"}])

	def test_a_clinic_named_category_grants_nothing(self):
		owners = api._required_field_owners({"custom_derma_category": "Botox"})

		self.assertEqual(owners, [])

	def test_the_safety_flags_still_append(self):
		owners = api._required_field_owners(
			{
				"custom_derma_product_tracking_required": 1,
				"custom_derma_device_settings_required": 1,
			}
		)

		self.assertEqual(
			[owner["fieldname"] for owner in owners],
			["product_name", "lot_no", "expiry_date", "device", "settings"],
		)

	def test_the_template_wins_over_a_flag_claiming_the_same_field(self):
		owners = api._required_field_owners(
			{
				"custom_derma_required_fields": json.dumps(["lot_no"]),
				"custom_derma_product_tracking_required": 1,
			}
		)

		self.assertEqual(
			[owner["source"] for owner in owners if owner["fieldname"] == "lot_no"], ["template"]
		)


class TestTemplateVariables(IntegrationTestCase):
	"""What the chart renders for one template."""

	def _variable(self, variables, fieldname):
		return next(row for row in variables if row["fieldname"] == fieldname)

	def test_a_declared_false_stays_false(self):
		variables = api._get_template_variables(
			{
				"custom_derma_required_fields": json.dumps(["dose"]),
				"custom_derma_variables_json": json.dumps([{"label": "Dose", "required": False}]),
			}
		)

		self.assertFalse(self._variable(variables, "dose")["required"])

	def test_a_row_without_the_key_inherits_the_required_set(self):
		variables = api._get_template_variables(
			{
				"custom_derma_required_fields": json.dumps(["dose"]),
				"custom_derma_variables_json": json.dumps([{"label": "Dose"}]),
			}
		)

		self.assertTrue(self._variable(variables, "dose")["required"])

	def test_a_safety_flag_field_cannot_be_declared_optional(self):
		"""The creation gate throws on `lot_no` while product tracking is on, so a row
		calling it optional would promise something the server refuses."""
		variables = api._get_template_variables(
			{
				"custom_derma_product_tracking_required": 1,
				"custom_derma_variables_json": json.dumps([{"label": "Lot No", "required": False}]),
			}
		)

		self.assertTrue(self._variable(variables, "lot_no")["required"])

	def test_a_required_field_with_no_row_of_its_own_is_appended(self):
		variables = api._get_template_variables({"custom_derma_required_fields": json.dumps(["dose"])})

		self.assertTrue(self._variable(variables, "dose")["required"])

	def test_an_unknown_required_fieldname_never_reaches_the_chart(self):
		variables = api._get_template_variables(
			{"custom_derma_required_fields": json.dumps(["invented_field"])}
		)

		self.assertEqual(variables, [])


class TestVariableSchemaShapes(IntegrationTestCase):
	"""Hand-written JSON in every shape the parser has ever tolerated keeps working."""

	def _fieldnames(self, value):
		variables, _seen = api._parse_template_variable_schema(value, [])
		return [row["fieldname"] for row in variables]

	def test_reads_an_array_of_objects(self):
		self.assertEqual(
			self._fieldnames(json.dumps([{"label": "Dose"}, {"fieldname": "plane"}])), ["dose", "plane"]
		)

	def test_reads_an_array_of_strings(self):
		self.assertEqual(self._fieldnames(json.dumps(["Dose", "Plane"])), ["dose", "plane"])

	def test_reads_a_wrapper_object(self):
		self.assertEqual(self._fieldnames(json.dumps({"variables": [{"label": "Dose"}]})), ["dose"])
		self.assertEqual(self._fieldnames(json.dumps({"fields": [{"label": "Plane"}]})), ["plane"])

	def test_reads_a_json_encoded_csv_string(self):
		self.assertEqual(self._fieldnames(json.dumps("Dose, Plane")), ["dose", "plane"])

	def test_unreadable_json_yields_no_variables(self):
		self.assertEqual(self._fieldnames("{not json"), [])

	def test_a_label_collapses_to_a_fieldname(self):
		self.assertEqual(self._fieldnames(json.dumps([{"label": "Lot  No."}])), ["lot_no"])

	def test_a_declared_type_is_normalised(self):
		variables, _seen = api._parse_template_variable_schema(
			json.dumps([{"label": "Dose", "type": "Float"}, {"label": "Notes", "fieldtype": "Nonsense"}]), []
		)

		self.assertEqual([row["fieldtype"] for row in variables], ["Float", "Data"])


class TestRequiredFieldParsing(IntegrationTestCase):
	def test_reads_a_list(self):
		self.assertEqual(api._parse_required_fields(["Lot No", "dose"]), ["lot_no", "dose"])

	def test_reads_a_json_list(self):
		self.assertEqual(api._parse_required_fields(json.dumps(["lot_no"])), ["lot_no"])

	def test_reads_a_json_encoded_csv_string(self):
		self.assertEqual(api._parse_required_fields(json.dumps("lot_no, dose")), ["lot_no", "dose"])

	def test_an_empty_value_requires_nothing(self):
		self.assertEqual(api._parse_required_fields(None), [])
		self.assertEqual(api._parse_required_fields("[]"), [])


class TestMarksReadyForProcedure(IntegrationTestCase):
	"""The gate at Clinical Procedure creation, which is the only place required fields
	are enforced. Its message names every field the clinician still has to fill."""

	def _mark(self, **values):
		return frappe._dict(values)

	def test_throws_naming_every_missing_required_field(self):
		template = frappe._dict(custom_derma_required_fields=json.dumps(["dose", "plane"]))

		with self.assertRaises(frappe.ValidationError) as caught:
			api._validate_marks_ready_for_procedure([self._mark()], template)

		self.assertIn("Dose", str(caught.exception))
		self.assertIn("Plane", str(caught.exception))

	def test_passes_when_every_required_field_is_filled(self):
		template = frappe._dict(custom_derma_required_fields=json.dumps(["dose"]))

		api._validate_marks_ready_for_procedure([self._mark(dose=2)], template)

	def test_one_unfilled_mark_of_several_is_enough_to_throw(self):
		template = frappe._dict(custom_derma_required_fields=json.dumps(["dose"]))

		with self.assertRaises(frappe.ValidationError):
			api._validate_marks_ready_for_procedure([self._mark(dose=2), self._mark()], template)

	def test_product_tracking_demands_a_lot_number(self):
		template = frappe._dict(custom_derma_product_tracking_required=1)

		with self.assertRaises(frappe.ValidationError) as caught:
			api._validate_marks_ready_for_procedure([self._mark(product_name="Botox 100")], template)

		self.assertIn("Lot", str(caught.exception))

	def test_photo_evidence_is_demanded_when_the_flag_is_on(self):
		template = frappe._dict(custom_derma_before_after_photo_required=1)

		with self.assertRaises(frappe.ValidationError) as caught:
			api._validate_marks_ready_for_procedure([self._mark()], template)

		self.assertIn("Photo", str(caught.exception))


class TestRequiredFieldMaterialisation(ConfigTemplateHelpers, IntegrationTestCase):
	"""The patch that makes the template the one owner: whatever the category-name table
	granted is written into the template before the table is deleted."""

	def _required_fields(self, template):
		return frappe.db.get_value("Clinical Procedure Template", template, "custom_derma_required_fields")

	def test_writes_the_category_table_set_into_the_template(self):
		category = self._make_category("Botox")
		template = self._make_derma_template(custom_derma_category=category)

		materialize_required_fields()

		self.assertEqual(
			json.loads(self._required_fields(template)),
			["product_name", "dose", "dose_unit", "lot_no", "expiry_date"],
		)

	def test_what_the_template_already_declared_stays_first(self):
		category = self._make_category("Botox")
		template = self._make_derma_template(
			custom_derma_category=category, custom_derma_required_fields=json.dumps(["plane"])
		)

		materialize_required_fields()

		self.assertEqual(json.loads(self._required_fields(template))[0], "plane")

	def test_a_second_run_writes_nothing(self):
		category = self._make_category("Botox")
		template = self._make_derma_template(custom_derma_category=category)
		materialize_required_fields()
		before = frappe.db.get_value("Clinical Procedure Template", template, "modified")
		written = self._required_fields(template)

		materialize_required_fields()

		self.assertEqual(self._required_fields(template), written)
		self.assertEqual(frappe.db.get_value("Clinical Procedure Template", template, "modified"), before)

	def test_a_template_whose_required_fields_cannot_be_read_is_left_alone(self):
		category = self._make_category("Botox")
		template = self._make_derma_template(
			custom_derma_category=category, custom_derma_required_fields="{not json"
		)

		materialize_required_fields()

		self.assertEqual(self._required_fields(template), "{not json")

	def test_the_safety_flags_are_not_materialised(self):
		"""The flags stay live, so what they append must not be frozen into the template."""
		category = self._make_category("Biopsy")
		template = self._make_derma_template(
			custom_derma_category=category, custom_derma_device_settings_required=1
		)

		materialize_required_fields()

		self.assertEqual(
			json.loads(self._required_fields(template)), ["lesion_id", "diagnosis", "body_region"]
		)

	def test_a_clinic_named_category_leaves_a_template_untouched(self):
		category = self._make_category(f"Derma Cfg {frappe.generate_hash(length=6)}")
		template = self._make_derma_template(custom_derma_category=category)

		materialize_required_fields()

		self.assertFalse(api._parse_required_fields(self._required_fields(template)))
