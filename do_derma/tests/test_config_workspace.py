from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma.patches.ensure_derma_body_template_editor_page import (
	execute as ensure_body_template_editor_page,
)
from do_derma.patches.ensure_derma_config_page import execute as ensure_config_page
from do_derma.tests.test_api import DermaTestHelpers


class TestConfigOverview(DermaTestHelpers, IntegrationTestCase):
	"""The config workspace lists what an administrator has to fix, so it shows
	disabled rows the chart deliberately hides."""

	def _template_row(self, overview, template):
		return next(row for row in overview["body_templates"] if row["name"] == template)

	def test_lists_a_disabled_body_template(self):
		template = self._make_body_template(disabled=1)

		overview = api.get_derma_config_overview()

		self.assertEqual(self._template_row(overview, template)["disabled"], 1)

	def test_counts_active_and_retired_areas_separately(self):
		template = self._make_body_template()
		self._make_body_template_part(template, "Left Cheek")
		self._make_body_template_part(template, "Right Cheek")
		self._make_body_template_part(template, "Chin", disabled=1)

		row = self._template_row(api.get_derma_config_overview(), template)

		self.assertEqual(row["area_count"], 2)
		self.assertEqual(row["retired_area_count"], 1)

	def test_a_template_with_no_areas_counts_zero(self):
		template = self._make_body_template()

		row = self._template_row(api.get_derma_config_overview(), template)

		self.assertEqual((row["area_count"], row["retired_area_count"]), (0, 0))

	def test_a_broken_sub_query_degrades_to_an_empty_list(self):
		with patch.object(api, "get_config_body_templates", side_effect=Exception("boom")):
			overview = api.get_derma_config_overview()

		self.assertEqual(overview["body_templates"], [])
		self.assertIn("body templates", overview["errors"])


class TestPagePatches(IntegrationTestCase):
	"""Both pages are source-backed, so these patches only matter on sites without
	developer mode - where a re-run must be free."""

	def test_re_running_leaves_an_unchanged_row_alone(self):
		for patch_execute, page in (
			(ensure_config_page, "derma-config"),
			(ensure_body_template_editor_page, "derma-body-template-editor"),
		):
			with self.subTest(page=page):
				patch_execute()
				before = frappe.db.get_value("Page", page, "modified")
				patch_execute()
				self.assertEqual(frappe.db.get_value("Page", page, "modified"), before)

	def test_it_recreates_a_deleted_row(self):
		if frappe.conf.developer_mode:
			# Deleting and re-inserting a source-backed Page rewrites its JSON on disk here,
			# and the patch only exists for sites where that never happens.
			self.skipTest("developer_mode writes the Page row back to the app source")
		frappe.delete_doc("Page", "derma-config", force=True, ignore_permissions=True)

		ensure_config_page()

		self.assertEqual(frappe.db.get_value("Page", "derma-config", "title"), "Derma Configuration")
