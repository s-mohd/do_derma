from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma import settings
from do_derma.tests.test_api import DermaTestHelpers


class SettingsTestBase(DermaTestHelpers, IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")

	def _set_toggle(self, fieldname, value):
		doc = frappe.get_doc(settings.SETTINGS_DOCTYPE)
		self.addCleanup(self._restore_toggle, fieldname, doc.get(fieldname))
		doc.set(fieldname, value)
		doc.save(ignore_permissions=True)
		frappe.clear_cache(doctype=settings.SETTINGS_DOCTYPE)

	def _restore_toggle(self, fieldname, value):
		doc = frappe.get_doc(settings.SETTINGS_DOCTYPE)
		doc.set(fieldname, value)
		doc.save(ignore_permissions=True)
		frappe.clear_cache(doctype=settings.SETTINGS_DOCTYPE)


class TestFeatureToggles(SettingsTestBase):
	"""The toggles gate controls whose integration is unfinished, so the safe
	answer to every question the reader cannot answer is off."""

	def test_every_toggle_is_reported(self):
		toggles = settings.get_feature_toggles()
		self.assertEqual(sorted(toggles), sorted(settings.FEATURE_TOGGLES))
		for value in toggles.values():
			self.assertIsInstance(value, bool)

	def test_toggles_default_off(self):
		for fieldname in settings.FEATURE_TOGGLES:
			self._set_toggle(fieldname, 0)
		self.assertEqual(settings.get_feature_toggles(), dict.fromkeys(settings.FEATURE_TOGGLES, False))

	def test_an_enabled_toggle_is_reported(self):
		self._set_toggle("enable_lab_cases", 1)
		toggles = settings.get_feature_toggles()
		self.assertTrue(toggles["enable_lab_cases"])
		self.assertFalse(toggles["enable_whatsapp_consent"])

	def test_an_unreadable_singleton_hides_everything(self):
		"""A site without Derma Settings must render no unfinished control."""
		with patch.object(settings, "get_settings_doc", return_value=None):
			self.assertEqual(
				settings.get_feature_toggles(),
				dict.fromkeys(settings.FEATURE_TOGGLES, False),
			)


class TestChartPayloadCarriesToggles(SettingsTestBase):
	def test_chart_payload_carries_every_toggle(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		payload = api.get_patient_derma_chart(patient_id=patient, encounter=encounter.name)
		self.assertEqual(sorted(payload["settings"]), sorted(settings.FEATURE_TOGGLES))

	def test_chart_payload_reflects_an_enabled_toggle(self):
		self._set_toggle("enable_billing_sync", 1)
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		payload = api.get_patient_derma_chart(patient_id=patient, encounter=encounter.name)
		self.assertTrue(payload["settings"]["enable_billing_sync"])
