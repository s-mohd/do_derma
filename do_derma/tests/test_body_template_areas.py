from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma.tests.test_api import DermaTestHelpers


class TestMarkAreaVariables(DermaTestHelpers, IntegrationTestCase):
	"""Area variable values typed on a body-map region are clinical data on the mark,
	not a rendered badge string."""

	def _save_mark(self, patient, **extra):
		payload = {"patient": patient, "x_percent": 10, "y_percent": 20, **extra}
		return api.save_chart_mark(json.dumps(payload))

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
