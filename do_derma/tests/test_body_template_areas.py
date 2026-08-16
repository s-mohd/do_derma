from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma.patches.backfill_derma_mark_template_part import execute as backfill_template_part
from do_derma.tests.test_api import DermaTestHelpers


class TestMarkAreaVariables(DermaTestHelpers, IntegrationTestCase):
	"""Area variable values typed on a body-map region are clinical data on the mark,
	not a rendered badge string."""

	def _rows(self, mark):
		return frappe.get_all(
			"Derma Mark Variable",
			filters={"parent": mark, "parenttype": "Derma Chart Mark"},
			fields=["fieldname", "label", "value", "source", "idx"],
			order_by="idx asc",
		)

	def test_stores_one_row_per_declared_variable_including_blanks(self):
		patient = self._make_patient()
		mark = self._save_mark(
			patient,
			area_variables=[
				{"label": "Plane", "value": "Subdermal"},
				{"label": "Units", "value": 2.5},
				{"label": "Notes", "value": ""},
			],
		)

		rows = self._rows(mark["name"])
		self.assertEqual([row.fieldname for row in rows], ["plane", "units", "notes"])
		self.assertEqual([row.value for row in rows], ["Subdermal", "2.5", ""])
		self.assertEqual([row.label for row in rows], ["Plane", "Units", "Notes"])
		self.assertEqual({row.source for row in rows}, {"Area"})

	def test_check_values_are_stored_as_zero_or_one(self):
		patient = self._make_patient()
		mark = self._save_mark(
			patient,
			area_variables=[
				{"label": "Treated", "value": True},
				{"label": "Numbed", "value": False},
			],
		)

		self.assertEqual([row.value for row in self._rows(mark["name"])], ["1", "0"])

	def test_omitting_the_key_leaves_existing_rows_alone(self):
		patient = self._make_patient()
		mark = self._save_mark(patient, area_variables=[{"label": "Plane", "value": "Subdermal"}])

		api.save_chart_mark(json.dumps({"name": mark["name"], "patient": patient, "note": "later edit"}))

		self.assertEqual([row.value for row in self._rows(mark["name"])], ["Subdermal"])

	def test_a_variables_only_save_leaves_the_mark_where_it_was_placed(self):
		"""The studio writes area values back by name alone. Before this, the absent
		x/y clamped to 0 and moved every re-saved mark to the top-left corner."""
		patient = self._make_patient()
		mark = self._save_mark(patient, x_percent=41.5, y_percent=62.25)

		api.save_chart_mark(
			json.dumps(
				{
					"name": mark["name"],
					"patient": patient,
					"area_variables": [{"label": "Plane", "value": "Deep"}],
				}
			)
		)

		moved = frappe.db.get_value(
			"Derma Chart Mark", mark["name"], ["x_percent", "y_percent"], as_dict=True
		)
		self.assertEqual((moved.x_percent, moved.y_percent), (41.5, 62.25))

	def test_a_position_outside_the_template_is_clamped(self):
		patient = self._make_patient()
		mark = self._save_mark(patient, x_percent=140, y_percent=-12)

		self.assertEqual((mark["x_percent"], mark["y_percent"]), (100, 0))

	def test_an_empty_list_clears_the_rows(self):
		patient = self._make_patient()
		mark = self._save_mark(patient, area_variables=[{"label": "Plane", "value": "Subdermal"}])

		api.save_chart_mark(json.dumps({"name": mark["name"], "patient": patient, "area_variables": []}))

		self.assertEqual(self._rows(mark["name"]), [])

	def test_rows_arrive_json_encoded_from_the_browser(self):
		patient = self._make_patient()
		mark = self._save_mark(patient, area_variables=json.dumps([{"label": "Plane", "value": "Deep"}]))

		self.assertEqual([row.value for row in self._rows(mark["name"])], ["Deep"])

	def test_unnamed_rows_are_skipped(self):
		patient = self._make_patient()
		mark = self._save_mark(
			patient,
			area_variables=[{"label": "  ", "value": "orphan"}, {"label": "Plane", "value": "Deep"}],
		)

		self.assertEqual([row.fieldname for row in self._rows(mark["name"])], ["plane"])

	def test_marks_are_read_back_with_their_area_variables(self):
		patient = self._make_patient()
		self._save_mark(patient, area_variables=[{"label": "Plane", "value": "Subdermal"}])

		marks = api._get_marks(patient)

		self.assertEqual(len(marks), 1)
		self.assertEqual(
			marks[0]["area_variables"],
			[{"fieldname": "plane", "label": "Plane", "value": "Subdermal", "source": "Area"}],
		)

	def test_marks_without_rows_read_back_an_empty_list(self):
		patient = self._make_patient()
		self._save_mark(patient)

		self.assertEqual(api._get_marks(patient)[0]["area_variables"], [])

	def test_a_site_without_the_child_doctype_still_reads_marks(self):
		patient = self._make_patient()
		self._save_mark(patient)

		with patch.object(api, "_has_doctype", side_effect=lambda dt: dt == "Derma Chart Mark"):
			marks = api._get_marks(patient)

		self.assertEqual(len(marks), 1)
		self.assertNotIn("area_variables", marks[0])

	def test_a_site_without_the_field_ignores_the_key(self):
		patient = self._make_patient()
		real_has_field = api._has_field

		with patch.object(
			api,
			"_has_field",
			side_effect=lambda dt, fn: (
				False if (dt, fn) == ("Derma Chart Mark", "area_variables") else real_has_field(dt, fn)
			),
		):
			mark = self._save_mark(patient, area_variables=[{"label": "Plane", "value": "Subdermal"}])

		self.assertEqual(self._rows(mark["name"]), [])


class TestBodyTemplatePartSave(DermaTestHelpers, IntegrationTestCase):
	"""Saving a body map never destroys an area a mark may be standing on."""

	def _payload_part(self, part_name, **extra):
		return {
			"part_name": part_name,
			"shape_json": [[0, 0], [10, 0], [10, 10]],
			"variables": [],
			**extra,
		}

	def _variable_rows(self, part):
		return frappe.get_all(
			"Derma Template Part Variable",
			filters={"parent": part, "parenttype": "Derma Body Template Part"},
			fields=["name", "variable_name", "type", "idx"],
			order_by="idx asc",
		)

	def test_a_removed_area_is_soft_disabled_not_deleted(self):
		template = self._make_body_template()
		part = self._make_body_template_part(template, "Left Cheek")

		api.save_derma_body_template_parts(template, json.dumps([self._payload_part("Right Cheek")]))

		self.assertTrue(frappe.db.exists("Derma Body Template Part", part))
		self.assertEqual(frappe.db.get_value("Derma Body Template Part", part, "disabled"), 1)

	def test_an_empty_payload_deletes_nothing(self):
		template = self._make_body_template()
		part = self._make_body_template_part(template, "Left Cheek")

		api.save_derma_body_template_parts(template, json.dumps([]))

		self.assertTrue(frappe.db.exists("Derma Body Template Part", part))

	def test_a_mark_still_resolves_its_area_after_it_is_removed(self):
		patient = self._make_patient()
		template = self._make_body_template()
		part = self._make_body_template_part(template, "Left Cheek")
		self._save_mark(patient, body_template=template, body_template_part=part, region_label="Left Cheek")

		api.save_derma_body_template_parts(template, json.dumps([]))

		self.assertEqual(api._get_marks(patient)[0]["body_template_part"], part)

	def test_saving_without_touching_variables_leaves_the_child_rows_alone(self):
		template = self._make_body_template()
		part = self._make_body_template_part(
			template,
			"Left Cheek",
			variables=[
				{"variable_name": "Plane", "type": "Select", "options": "Deep\nSubdermal"},
				{"variable_name": "Units", "type": "Float"},
			],
		)
		before = self._variable_rows(part)

		api.save_derma_body_template_parts(
			template,
			json.dumps(
				[
					self._payload_part(
						"Left Cheek",
						name=part,
						variables=[
							{"variable_name": "Plane", "type": "Select", "options": "Deep\nSubdermal"},
							{"variable_name": "Units", "type": "Float"},
						],
					)
				]
			),
		)

		self.assertEqual(
			[(row.name, row.idx) for row in self._variable_rows(part)],
			[(row.name, row.idx) for row in before],
		)

	def test_changed_variables_are_rewritten(self):
		template = self._make_body_template()
		part = self._make_body_template_part(
			template, "Left Cheek", variables=[{"variable_name": "Plane", "type": "Data"}]
		)

		api.save_derma_body_template_parts(
			template,
			json.dumps(
				[
					self._payload_part(
						"Left Cheek",
						name=part,
						variables=[
							{"variable_name": "Plane", "type": "Data"},
							{"variable_name": "Units", "type": "Float"},
						],
					)
				]
			),
		)

		self.assertEqual([row.variable_name for row in self._variable_rows(part)], ["Plane", "Units"])

	def test_retired_areas_are_hidden_from_the_default_read(self):
		template = self._make_body_template()
		self._make_body_template_part(template, "Left Cheek", disabled=1)
		self._make_body_template_part(template, "Right Cheek")

		parts = api.get_derma_body_template_parts(template)

		self.assertEqual([part["part_name"] for part in parts], ["Right Cheek"])

	def test_retired_areas_are_returned_when_asked_for(self):
		template = self._make_body_template()
		self._make_body_template_part(template, "Left Cheek", disabled=1)
		self._make_body_template_part(template, "Right Cheek")

		parts = api.get_derma_body_template_parts(template, include_disabled=1)

		self.assertEqual(
			{part["part_name"]: part["disabled"] for part in parts},
			{"Left Cheek": 1, "Right Cheek": 0},
		)

	def test_the_save_response_carries_the_areas_it_retired(self):
		"""The designer merges the response by part_name and lists what it retired,
		so the response must name both sets."""
		template = self._make_body_template()
		self._make_body_template_part(template, "Left Cheek")

		saved = api.save_derma_body_template_parts(template, json.dumps([self._payload_part("Right Cheek")]))

		self.assertEqual(
			{part["part_name"]: part["disabled"] for part in saved},
			{"Left Cheek": 1, "Right Cheek": 0},
		)

	def test_a_retired_area_is_restored_by_saving_it_again(self):
		template = self._make_body_template()
		part = self._make_body_template_part(template, "Left Cheek", disabled=1)

		api.save_derma_body_template_parts(
			template, json.dumps([self._payload_part("Left Cheek", name=part)])
		)

		self.assertEqual(frappe.db.get_value("Derma Body Template Part", part, "disabled"), 0)

	def test_an_area_owned_by_another_body_template_is_never_re_parented(self):
		"""The payload names the areas to keep. A name belonging to another body map
		would otherwise move that area here and strip it from the map it was drawn on."""
		template = self._make_body_template()
		other_template = self._make_body_template()
		foreign_part = self._make_body_template_part(other_template, "Left Cheek")

		api.save_derma_body_template_parts(
			template, json.dumps([self._payload_part("Left Cheek", name=foreign_part)])
		)

		stored = frappe.db.get_value(
			"Derma Body Template Part", foreign_part, ["body_template", "disabled"], as_dict=True
		)
		self.assertEqual((stored.body_template, stored.disabled), (other_template, 0))
		self.assertEqual(
			[part["part_name"] for part in api.get_derma_body_template_parts(template)], ["Left Cheek"]
		)

	def test_retired_areas_never_reach_the_chart(self):
		template = self._make_body_template()
		self._make_body_template_part(template, "Left Cheek", disabled=1)
		self._make_body_template_part(template, "Right Cheek")

		charted = next(row for row in api._get_body_templates() if row["name"] == template)

		self.assertEqual([part["part_name"] for part in charted["parts"]], ["Right Cheek"])


class TestMarkTemplatePartLink(DermaTestHelpers, IntegrationTestCase):
	"""The mark names the area it sits on by Link, while body_region keeps the coarse
	15-value vocabulary every existing read depends on."""

	def test_a_mark_placed_on_an_area_links_to_that_part(self):
		patient = self._make_patient()
		template = self._make_body_template()
		part = self._make_body_template_part(template, "Left Cheek")

		mark = self._save_mark(
			patient,
			body_template=template,
			body_template_part=part,
			body_region="Left Cheek",
			region_label="Left Cheek",
		)

		stored = frappe.db.get_value(
			"Derma Chart Mark",
			mark["name"],
			["body_template_part", "body_region", "region_label"],
			as_dict=True,
		)
		self.assertEqual(stored.body_template_part, part)
		self.assertEqual(stored.body_region, "Face")
		self.assertEqual(stored.region_label, "Left Cheek")

	def test_the_part_link_is_read_back_with_the_mark(self):
		patient = self._make_patient()
		template = self._make_body_template()
		part = self._make_body_template_part(template, "Left Cheek")
		self._save_mark(patient, body_template=template, body_template_part=part, region_label="Left Cheek")

		self.assertEqual(api._get_marks(patient)[0]["body_template_part"], part)

	def test_a_mark_placed_off_any_area_keeps_a_null_link(self):
		patient = self._make_patient()

		mark = self._save_mark(patient, body_region="Face")

		self.assertIsNone(frappe.db.get_value("Derma Chart Mark", mark["name"], "body_template_part"))

	def test_the_backfill_links_an_unambiguous_region_label(self):
		patient = self._make_patient()
		template = self._make_body_template()
		part = self._make_body_template_part(template, "Left Cheek")
		mark = self._save_mark(patient, body_template=template, region_label="Left Cheek")

		backfill_template_part()

		self.assertEqual(frappe.db.get_value("Derma Chart Mark", mark["name"], "body_template_part"), part)

	def test_the_backfill_leaves_an_ambiguous_region_label_alone(self):
		patient = self._make_patient()
		template = self._make_body_template()
		self._make_body_template_part(template, "Left Cheek")
		self._make_body_template_part(template, "Left Cheek")
		mark = self._save_mark(patient, body_template=template, region_label="Left Cheek")

		backfill_template_part()

		self.assertIsNone(frappe.db.get_value("Derma Chart Mark", mark["name"], "body_template_part"))

	def test_the_backfill_ignores_parts_of_another_body_template(self):
		patient = self._make_patient()
		template = self._make_body_template()
		other_template = self._make_body_template()
		self._make_body_template_part(other_template, "Left Cheek")
		mark = self._save_mark(patient, body_template=template, region_label="Left Cheek")

		backfill_template_part()

		self.assertIsNone(frappe.db.get_value("Derma Chart Mark", mark["name"], "body_template_part"))

	def test_the_backfill_is_re_runnable_and_never_relinks(self):
		patient = self._make_patient()
		template = self._make_body_template()
		part = self._make_body_template_part(template, "Left Cheek")
		renamed = self._make_body_template_part(template, "Right Cheek")
		mark = self._save_mark(
			patient, body_template=template, body_template_part=renamed, region_label="Left Cheek"
		)

		backfill_template_part()
		backfill_template_part()

		self.assertEqual(frappe.db.get_value("Derma Chart Mark", mark["name"], "body_template_part"), renamed)
		self.assertNotEqual(renamed, part)

	def test_a_part_from_another_body_template_is_refused(self):
		"""The annotation fan-out copies client-authored values into the payload, so a part
		that belongs to a different body template must not label the mark."""
		patient = self._make_patient()
		template = self._make_body_template()
		foreign_part = self._make_body_template_part(self._make_body_template(), "Left Cheek")

		mark = self._save_mark(patient, body_template=template, body_template_part=foreign_part)

		self.assertIsNone(frappe.db.get_value("Derma Chart Mark", mark["name"], "body_template_part"))

	def test_a_part_that_no_longer_exists_is_refused(self):
		patient = self._make_patient()
		template = self._make_body_template()

		mark = self._save_mark(patient, body_template=template, body_template_part="gone-with-the-map")

		self.assertIsNone(frappe.db.get_value("Derma Chart Mark", mark["name"], "body_template_part"))

	def test_the_backfill_is_a_no_op_on_a_site_without_the_field(self):
		patient = self._make_patient()
		template = self._make_body_template()
		self._make_body_template_part(template, "Left Cheek")
		mark = self._save_mark(patient, body_template=template, region_label="Left Cheek")
		real_has_field = api._has_field
		with patch.object(
			api,
			"_has_field",
			side_effect=lambda dt, fn: (
				False if (dt, fn) == ("Derma Chart Mark", "body_template_part") else real_has_field(dt, fn)
			),
		):
			backfill_template_part()

		self.assertIsNone(frappe.db.get_value("Derma Chart Mark", mark["name"], "body_template_part"))
