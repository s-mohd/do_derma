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


class FakeSettings:
	"""A Derma Settings singleton carrying only the fields a site has."""

	def __init__(self, values):
		self._values = values
		self.meta = self

	def has_field(self, fieldname):
		return fieldname in self._values

	def get(self, fieldname):
		return self._values.get(fieldname)


class TestReadinessSettings(SettingsTestBase):
	"""The defaults reproduce today's behaviour, so a site missing the fields is never
	stricter than one that has them."""

	def test_a_site_without_the_fields_warns_and_downgrades(self):
		with patch.object(settings, "get_settings_doc", return_value=FakeSettings({})):
			readiness = settings.get_readiness_settings()

		self.assertEqual(readiness["enforcement"], "Warn")
		self.assertTrue(readiness["todo_downgrades_blockers"])
		self.assertFalse(readiness["is_configurable"])

	def test_this_site_reports_a_mode_it_can_act_on(self):
		"""Whatever schema the site has, the three keys are always answered."""
		readiness = settings.get_readiness_settings()

		self.assertIn(readiness["enforcement"], settings.ENFORCEMENT_MODES)
		self.assertIsInstance(readiness["todo_downgrades_blockers"], bool)
		self.assertIsInstance(readiness["is_configurable"], bool)

	def test_an_unreadable_singleton_falls_back_to_warn(self):
		with patch.object(settings, "get_settings_doc", return_value=None):
			readiness = settings.get_readiness_settings()

		self.assertEqual(readiness["enforcement"], "Warn")
		self.assertTrue(readiness["todo_downgrades_blockers"])
		self.assertFalse(readiness["is_configurable"])

	def test_a_configured_site_reports_its_own_mode(self):
		doc = FakeSettings({"blocker_enforcement": "Block", "todo_downgrades_blockers": 0})
		with patch.object(settings, "get_settings_doc", return_value=doc):
			readiness = settings.get_readiness_settings()

		self.assertEqual(readiness["enforcement"], "Block")
		self.assertFalse(readiness["todo_downgrades_blockers"])
		self.assertTrue(readiness["is_configurable"])

	def test_an_unknown_mode_falls_back_to_warn(self):
		doc = FakeSettings({"blocker_enforcement": "Nag", "todo_downgrades_blockers": 1})
		with patch.object(settings, "get_settings_doc", return_value=doc):
			self.assertEqual(settings.get_readiness_settings()["enforcement"], "Warn")

	def test_the_downgrade_defaults_on_without_its_field(self):
		doc = FakeSettings({"blocker_enforcement": "Block"})
		with patch.object(settings, "get_settings_doc", return_value=doc):
			readiness = settings.get_readiness_settings()

		self.assertTrue(readiness["todo_downgrades_blockers"])
		self.assertTrue(readiness["is_configurable"])


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
