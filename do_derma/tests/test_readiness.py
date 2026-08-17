from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

import do_derma.api as api
from do_derma.patches.set_product_tracking_for_derma_categories import (
	execute as set_product_tracking,
)
from do_derma.readiness import followup, inventory, procedure
from do_derma.readiness.session import get_session_readiness
from do_derma.tests.test_api import DermaTestHelpers
from do_derma.tests.test_config_workspace import ConfigTemplateHelpers


class ReadinessMarkHelpers:
	def _mark(self, **values):
		"""A mark row shaped the way `_get_marks` returns it."""
		return {"name": f"MARK-{frappe.generate_hash(length=6)}", **values}


class TestInventoryReadiness(ReadinessMarkHelpers, ConfigTemplateHelpers, IntegrationTestCase):
	"""Product, lot, expiry and stock, grouped the way the clinic consumes them."""

	def test_a_mark_with_no_product_data_and_no_tracking_is_ignored(self):
		self.assertEqual(inventory.build([self._mark()]), [])

	def test_product_data_alone_raises_a_row(self):
		rows = inventory.build([self._mark(product_name="Botox 100", dose=2, dose_unit="Units")])

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["product_name"], "Botox 100")

	def test_a_missing_lot_number_blocks_and_says_so(self):
		rows = inventory.build([self._mark(product_name="Botox 100", dose=2)])

		self.assertTrue(rows[0]["blocking"])
		self.assertEqual(rows[0]["status"], "blocked")
		self.assertIn("Lot", rows[0]["message"])

	def test_an_expired_product_blocks(self):
		rows = inventory.build(
			[
				self._mark(
					product_name="Botox 100",
					dose=2,
					lot_no="LOT-1",
					expiry_date=add_days(nowdate(), -1),
				)
			]
		)

		self.assertTrue(rows[0]["blocking"])
		self.assertIn("expired", rows[0]["message"].lower())

	def test_a_complete_row_is_ready(self):
		rows = inventory.build(
			[
				self._mark(
					product_name="Botox 100",
					dose=2,
					lot_no="LOT-1",
					expiry_date=add_days(nowdate(), 90),
				)
			]
		)

		self.assertFalse(rows[0]["blocking"])
		self.assertEqual(rows[0]["status"], "ready")

	def test_marks_sharing_a_lot_sum_their_dose(self):
		shared = {"product_name": "Botox 100", "lot_no": "LOT-1", "dose_unit": "Units"}
		rows = inventory.build([self._mark(dose=2, **shared), self._mark(dose=3, **shared)])

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["dose"], 5)
		self.assertEqual(len(rows[0]["marks"]), 2)

	def test_a_second_lot_is_a_second_row(self):
		rows = inventory.build(
			[
				self._mark(product_name="Botox 100", lot_no="LOT-1", dose=2),
				self._mark(product_name="Botox 100", lot_no="LOT-2", dose=2),
			]
		)

		self.assertEqual(sorted(row["lot_no"] for row in rows), ["LOT-1", "LOT-2"])

	def test_the_tracking_flag_raises_a_row_for_a_mark_carrying_nothing(self):
		template = self._make_derma_template(custom_derma_product_tracking_required=1)
		if not api._has_field("Clinical Procedure Template", "custom_derma_product_tracking_required"):
			self.skipTest("Clinical Procedure Template.custom_derma_product_tracking_required is missing")

		rows = inventory.build([self._mark(procedure_template=template)])

		self.assertEqual(len(rows), 1)
		self.assertTrue(rows[0]["blocking"])

	def test_a_category_named_botox_no_longer_forces_tracking(self):
		"""Readiness follows the template's flag alone, so it no longer depends on how a
		clinic named a category. `set_product_tracking_for_derma_categories` carries the
		templates the name rule was covering onto the flag."""
		self.assertEqual(inventory.build([self._mark(category="Botox")]), [])


class TestFollowupReadiness(ReadinessMarkHelpers, ConfigTemplateHelpers, IntegrationTestCase):
	"""What each mark still owes after the visit."""

	def _item(self, items, key_suffix):
		return next(row for row in items if row["key"].endswith(key_suffix))

	def test_a_plain_active_mark_owes_nothing(self):
		self.assertEqual(followup.build([self._mark(status="Active")]), [])

	def test_a_worse_mark_blocks_and_is_due_in_a_week(self):
		items = followup.build([self._mark(status="Worse")])

		item = self._item(items, "-status")
		self.assertTrue(item["blocking"])
		self.assertEqual(item["due_date"], add_days(nowdate(), 7))

	def test_a_monitoring_mark_is_a_review_that_does_not_block(self):
		items = followup.build([self._mark(status="Monitoring")])

		item = self._item(items, "-status")
		self.assertFalse(item["blocking"])
		self.assertEqual(item["type"], "Review")
		self.assertEqual(item["due_date"], add_days(nowdate(), 30))

	def test_a_missing_photo_blocks_when_the_template_demands_evidence(self):
		template = self._make_derma_template(custom_derma_before_after_photo_required=1)
		if not api._has_field("Clinical Procedure Template", "custom_derma_before_after_photo_required"):
			self.skipTest("Clinical Procedure Template.custom_derma_before_after_photo_required is missing")

		items = followup.build([self._mark(procedure_template=template)])

		item = self._item(items, "-photo")
		self.assertTrue(item["blocking"])

	def test_a_missing_lot_blocks_when_the_template_tracks_product(self):
		template = self._make_derma_template(custom_derma_product_tracking_required=1)
		if not api._has_field("Clinical Procedure Template", "custom_derma_product_tracking_required"):
			self.skipTest("Clinical Procedure Template.custom_derma_product_tracking_required is missing")

		items = followup.build([self._mark(procedure_template=template, product_name="Botox 100")])

		item = self._item(items, "-inventory")
		self.assertTrue(item["blocking"])
		self.assertEqual(item["severity"], "high")

	def test_a_completed_botox_mark_earns_a_non_blocking_next_session(self):
		items = followup.build([self._mark(category="Botox", clinical_procedure="CP-0001")])

		item = self._item(items, "-next-session")
		self.assertFalse(item["blocking"])
		self.assertEqual(item["due_date"], add_days(nowdate(), 90))

	def test_the_most_urgent_item_comes_first(self):
		items = followup.build(
			[self._mark(status="Monitoring"), self._mark(status="Worse")],
		)

		self.assertEqual([item["severity"] for item in items], ["high", "medium"])


class TestSessionReadiness(DermaTestHelpers, IntegrationTestCase):
	"""One owner: both engines read through here, and the ToDo rule that used to live in
	the browser is applied on the server."""

	def setUp(self):
		self.patient = self._make_patient()

	def _readiness(self, todo_downgrades_blockers=True, enforcement="Warn"):
		settings = {
			"enforcement": enforcement,
			"todo_downgrades_blockers": todo_downgrades_blockers,
			"is_configurable": True,
		}
		with patch("do_derma.readiness.session.get_readiness_settings", return_value=settings):
			return get_session_readiness(self.patient)

	def test_no_patient_is_no_readiness(self):
		readiness = get_session_readiness(None)

		self.assertEqual(readiness["items"], [])
		self.assertEqual(readiness["blockers"], [])

	def test_every_item_names_the_engine_it_came_from(self):
		self._save_mark(self.patient, status="Worse", product_name="Botox 100", dose=2)

		sources = {item["source"] for item in self._readiness()["items"]}

		self.assertEqual(sources, {inventory.SOURCE, followup.SOURCE})

	def test_an_inventory_row_gets_a_title_and_a_detail(self):
		self._save_mark(self.patient, product_name="Botox 100", dose=2)

		item = next(row for row in self._readiness()["items"] if row["source"] == inventory.SOURCE)

		self.assertEqual(item["title"], "Botox 100")
		self.assertTrue(item["detail"])

	def test_blockers_are_the_blocking_items(self):
		self._save_mark(self.patient, status="Worse")

		readiness = self._readiness()

		self.assertTrue(readiness["blockers"])
		self.assertTrue(all(item["blocking"] for item in readiness["blockers"]))

	def test_the_enforcement_mode_is_reported(self):
		self.assertEqual(self._readiness(enforcement="Block")["enforcement"], "Block")

	def test_an_open_todo_downgrades_a_blocker(self):
		mark = self._save_mark(self.patient, status="Worse")
		api.create_followup_todo(json.dumps({"mark": mark["name"], "description": "Review"}))

		item = self._status_item(self._readiness(todo_downgrades_blockers=True))

		self.assertFalse(item["blocking"])
		self.assertEqual(item["severity"], "medium")
		self.assertTrue(item["downgraded_by_todo"])

	def test_with_the_setting_off_an_open_todo_still_blocks(self):
		mark = self._save_mark(self.patient, status="Worse")
		api.create_followup_todo(json.dumps({"mark": mark["name"], "description": "Review"}))

		item = self._status_item(self._readiness(todo_downgrades_blockers=False))

		self.assertTrue(item["blocking"])
		self.assertNotIn("downgraded_by_todo", item)

	def _status_item(self, readiness):
		return next(item for item in readiness["items"] if item["key"].endswith("-status"))


class TestChartContextReadiness(DermaTestHelpers, IntegrationTestCase):
	"""The chart reads readiness the server computed - it no longer gets two engine
	payloads to aggregate itself."""

	def setUp(self):
		self.patient = self._make_patient()

	def test_the_chart_carries_one_readiness_section(self):
		self._save_mark(self.patient, status="Worse", product_name="Botox 100", dose=2)

		readiness = api.get_patient_derma_chart(patient_id=self.patient)["readiness"]

		self.assertTrue(readiness["blockers"])
		self.assertEqual({item["source"] for item in readiness["items"]}, {inventory.SOURCE, followup.SOURCE})
		self.assertEqual(readiness["enforcement"], api.get_readiness_settings()["enforcement"])

	def test_the_two_engine_sections_are_gone(self):
		chart = api.get_patient_derma_chart(patient_id=self.patient)

		self.assertNotIn("inventory_readiness", chart)
		self.assertNotIn("followup_items", chart)

	def test_a_broken_readiness_query_degrades_to_an_empty_session(self):
		with patch("do_derma.readiness.session.get_session_readiness", side_effect=ValueError("boom")):
			chart = api.get_patient_derma_chart(patient_id=self.patient)

		self.assertIn("readiness", chart["context_errors"])
		self.assertEqual(chart["readiness"], {"items": [], "blockers": [], "enforcement": "Warn"})


class TestProductTrackingMigration(DermaTestHelpers, ConfigTemplateHelpers, IntegrationTestCase):
	"""What the retiring category-name rule was tracking keeps being tracked, because
	the migration writes it onto each template's own flag."""

	def setUp(self):
		super().setUp()
		for fieldname in ("custom_derma_product_tracking_required", "custom_derma_category"):
			if not api._has_field("Clinical Procedure Template", fieldname):
				self.skipTest(f"Clinical Procedure Template.{fieldname} is missing")

	def _tracking_flag(self, template):
		return frappe.db.get_value(
			"Clinical Procedure Template", template, "custom_derma_product_tracking_required"
		)

	def _make_mark_for(self, template, category):
		return (
			frappe.get_doc(
				{
					"doctype": "Derma Chart Mark",
					"patient": self._make_patient(),
					"procedure_template": template,
					"category": category,
					"x_percent": 40,
					"y_percent": 60,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def test_a_template_in_a_retired_category_gains_the_flag(self):
		template = self._make_derma_template(custom_derma_category=self._make_category("Botox"))

		set_product_tracking()

		self.assertTrue(self._tracking_flag(template))

	def test_every_retired_category_is_carried_over(self):
		template = self._make_derma_template(custom_derma_category=self._make_category("Filler"))

		set_product_tracking()

		self.assertTrue(self._tracking_flag(template))

	def test_a_template_a_mark_named_a_retired_category_for_gains_the_flag(self):
		"""The retired rule read the mark's category before the template's, so a mark can
		be tracked today while the template it points at is in another category."""
		template = self._make_derma_template(custom_derma_category=self._make_category("Laser"))
		self._make_mark_for(template, self._make_category("Botox"))

		set_product_tracking()

		self.assertTrue(self._tracking_flag(template))

	def test_a_category_named_in_another_case_is_not_migrated(self):
		"""The rule this replaces matched exactly, so migrating `botox` would start
		tracking a template nothing tracks today. Written past the Link field, which
		canonicalises to the docname a case-insensitive database already holds."""
		template = self._make_derma_template(custom_derma_category=self._make_category("Laser"))
		frappe.db.set_value(
			"Clinical Procedure Template", template, "custom_derma_category", "botox", update_modified=False
		)

		set_product_tracking()

		self.assertFalse(self._tracking_flag(template))

	def test_a_template_in_another_category_is_left_alone(self):
		template = self._make_derma_template(custom_derma_category=self._make_category("Laser"))

		set_product_tracking()

		self.assertFalse(self._tracking_flag(template))

	def test_the_migrated_template_blocks_on_a_missing_lot_as_it_did_before(self):
		category = self._make_category("Botox")
		template = self._make_derma_template(custom_derma_category=category)

		set_product_tracking()
		rows = inventory.build([{"name": "MARK-1", "procedure_template": template, "category": category}])

		self.assertEqual(len(rows), 1)
		self.assertTrue(rows[0]["blocking"])

	def test_a_second_run_writes_nothing(self):
		template = self._make_derma_template(custom_derma_category=self._make_category("Botox"))
		set_product_tracking()
		before = frappe.db.get_value("Clinical Procedure Template", template, "modified")

		set_product_tracking()

		self.assertTrue(self._tracking_flag(template))
		self.assertEqual(frappe.db.get_value("Clinical Procedure Template", template, "modified"), before)


class TestMarksReadyForProcedure(IntegrationTestCase):
	"""The gate at Clinical Procedure creation, which is the only place required fields
	are enforced. Its message names every field the clinician still has to fill."""

	def _mark(self, **values):
		return frappe._dict(values)

	def test_throws_naming_every_missing_required_field(self):
		template = frappe._dict(custom_derma_required_fields=json.dumps(["dose", "plane"]))

		with self.assertRaises(frappe.ValidationError) as caught:
			procedure.validate_marks_ready([self._mark()], template)

		self.assertIn("Dose", str(caught.exception))
		self.assertIn("Plane", str(caught.exception))

	def test_passes_when_every_required_field_is_filled(self):
		template = frappe._dict(custom_derma_required_fields=json.dumps(["dose"]))

		procedure.validate_marks_ready([self._mark(dose=2)], template)

	def test_one_unfilled_mark_of_several_is_enough_to_throw(self):
		template = frappe._dict(custom_derma_required_fields=json.dumps(["dose"]))

		with self.assertRaises(frappe.ValidationError):
			procedure.validate_marks_ready([self._mark(dose=2), self._mark()], template)

	def test_product_tracking_demands_a_lot_number(self):
		template = frappe._dict(custom_derma_product_tracking_required=1)

		with self.assertRaises(frappe.ValidationError) as caught:
			procedure.validate_marks_ready([self._mark(product_name="Botox 100")], template)

		self.assertIn("Lot", str(caught.exception))

	def test_photo_evidence_is_demanded_when_the_flag_is_on(self):
		template = frappe._dict(custom_derma_before_after_photo_required=1)

		with self.assertRaises(frappe.ValidationError) as caught:
			procedure.validate_marks_ready([self._mark()], template)

		self.assertIn("Photo", str(caught.exception))

	def test_a_required_variable_is_read_off_the_mark_through_its_alias(self):
		"""`product` is a template's word for the mark's own `product_name`."""
		template = frappe._dict(custom_derma_required_fields=json.dumps(["product"]))

		procedure.validate_marks_ready([self._mark(product_name="Botox 100")], template)
