from __future__ import annotations

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate, nowtime

import do_derma.api as api


class DermaTestHelpers:
    def _make_patient(self):
        token = frappe.generate_hash(length=8)
        digits = "".join(str(ord(ch) % 10) for ch in token)[:7]
        return frappe.get_doc(
            {
                "doctype": "Patient",
                "first_name": f"Derma{token}",
                "sex": "Male",
                "mobile": f"+1555{digits}",
            }
        ).insert(ignore_permissions=True).name

    def _get_or_create_appointment_type(self):
        existing = frappe.db.get_value("Appointment Type", {}, "name")
        if existing:
            return existing
        token = frappe.generate_hash(length=8)
        return frappe.get_doc(
            {
                "doctype": "Appointment Type",
                "appointment_type": f"Derma-{token}",
                "allow_booking_for": "Practitioner",
            }
        ).insert(ignore_permissions=True).name

    def _get_or_create_practitioner(self):
        existing = frappe.db.get_value("Healthcare Practitioner", {"status": "Active"}, "name")
        if existing:
            return existing
        token = frappe.generate_hash(length=8)
        return frappe.get_doc(
            {
                "doctype": "Healthcare Practitioner",
                "first_name": f"Derma{token}",
                "status": "Active",
            }
        ).insert(ignore_permissions=True).name

    def _make_encounter(self, patient, docstatus=0):
        doc = frappe.get_doc(
            {
                "doctype": "Patient Encounter",
                "patient": patient,
                "appointment_type": self._get_or_create_appointment_type(),
                "encounter_date": nowdate(),
                "encounter_time": nowtime(),
                "practitioner": self._get_or_create_practitioner(),
                "status": "Open",
            }
        ).insert(ignore_permissions=True)
        if docstatus == 1:
            doc.submit()
        return doc

    def _make_limited_user(self):
        email = f"derma-no-access-{frappe.generate_hash(length=6)}@example.com"
        if not frappe.db.exists("User", email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": "NoClinicalAccess",
                    "send_welcome_email": 0,
                }
            ).insert(ignore_permissions=True)
        return email


class TestClinicalAccessGate(DermaTestHelpers, IntegrationTestCase):
    """Regression coverage for the access-control gate added to every whitelisted
    endpoint in api.py - previously any authenticated user, regardless of role,
    could call these via ignore_permissions=True writes with no check at all."""

    def setUp(self):
        self.addCleanup(frappe.set_user, "Administrator")

    def test_user_without_clinical_role_is_blocked(self):
        frappe.set_user(self._make_limited_user())
        with self.assertRaises(frappe.PermissionError):
            api.save_chart_mark(json.dumps({"patient": "does-not-matter", "x_percent": 1, "y_percent": 1}))

    def test_system_manager_passes_the_gate(self):
        frappe.set_user("Administrator")
        patient = self._make_patient()
        result = api.save_chart_mark(
            json.dumps({"patient": patient, "x_percent": 10, "y_percent": 20})
        )
        self.assertEqual(result["patient"], patient)


class TestSaveChartMark(DermaTestHelpers, IntegrationTestCase):
    def test_round_trips_position_and_patient(self):
        patient = self._make_patient()
        saved = api.save_chart_mark(
            json.dumps({"patient": patient, "x_percent": 33.5, "y_percent": 67.25})
        )
        self.assertTrue(saved.get("name"))
        stored = frappe.get_doc("Derma Chart Mark", saved["name"])
        self.assertEqual(stored.patient, patient)
        self.assertEqual(stored.x_percent, 33.5)
        self.assertEqual(stored.y_percent, 67.25)


class TestCompleteDermaSession(DermaTestHelpers, IntegrationTestCase):
    def test_submits_draft_encounter_with_no_appointment(self):
        patient = self._make_patient()
        encounter = self._make_encounter(patient)
        self.assertEqual(encounter.docstatus, 0)

        result = api.complete_derma_session(encounter=encounter.name, patient=patient)

        self.assertTrue(result["encounter_submitted"])
        self.assertEqual(frappe.db.get_value("Patient Encounter", encounter.name, "docstatus"), 1)

    def test_does_not_resubmit_an_already_submitted_encounter(self):
        patient = self._make_patient()
        encounter = self._make_encounter(patient, docstatus=1)

        result = api.complete_derma_session(encounter=encounter.name, patient=patient)

        self.assertFalse(result["encounter_submitted"])
