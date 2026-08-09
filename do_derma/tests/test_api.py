from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate, nowtime

import do_derma.api as api

PIXEL_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
TEMPLATE_ELEMENT = {
    "id": "derma-template-element",
    "type": "image",
    "x": 0,
    "y": 0,
    "width": 100,
    "height": 100,
    "customData": {"kind": "derma_template"},
}


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

    def _get_or_create_procedure_template(self):
        existing = frappe.db.get_value("Clinical Procedure Template", {}, "name")
        if existing:
            return existing
        token = frappe.generate_hash(length=8)
        doc = frappe.get_doc(
            {
                "doctype": "Clinical Procedure Template",
                "template": f"Derma{token}",
                # healthcare's after_insert calls create_item_from_template(), which reads
                # doc.item_code straight into a new Item.
                "item_code": f"Derma{token}",
                "item_group": frappe.db.get_value("Item Group", {}, "name"),
            }
        )
        doc.set("is_billable", 0)
        return doc.insert(ignore_permissions=True).name

    def _make_clinical_procedure(self, patient):
        return frappe.get_doc(
            {
                "doctype": "Clinical Procedure",
                "patient": patient,
                "procedure_template": self._get_or_create_procedure_template(),
                "practitioner": self._get_or_create_practitioner(),
                "company": frappe.defaults.get_defaults().get("company")
                or frappe.db.get_value("Company", {}, "name"),
                "status": "Draft",
            }
        ).insert(ignore_permissions=True)

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


class TestChartContextErrors(DermaTestHelpers, IntegrationTestCase):
    """A section whose query raises must degrade to its fallback and be named in
    context_errors - by label only, never by exception text."""

    def test_healthy_chart_reports_no_degraded_sections(self):
        patient = self._make_patient()

        chart = api.get_patient_derma_chart(patient_id=patient)

        self.assertEqual(chart["context_errors"], [])

    def test_context_errors_carries_labels_only(self):
        patient = self._make_patient()
        secret = "SELECT secret_column FROM tabPatient"

        def explode():
            raise ValueError(secret)

        with patch.object(api, "_get_categories", side_effect=explode):
            chart = api.get_patient_derma_chart(patient_id=patient)

        self.assertIn("categories", chart["context_errors"])
        self.assertEqual(chart["categories"], [])
        self.assertNotIn(secret, json.dumps(chart))

    def test_one_broken_section_leaves_the_others_intact(self):
        patient = self._make_patient()

        with patch.object(api, "_get_body_templates", side_effect=ValueError("boom")):
            chart = api.get_patient_derma_chart(patient_id=patient)

        self.assertEqual(chart["context_errors"], ["body templates"])
        self.assertEqual(chart["patient_id"], patient)
        self.assertIsInstance(chart["procedures"], list)


class TestAnnotationAnchoring(DermaTestHelpers, IntegrationTestCase):
    """save_derma_annotation anchors to whichever parent the caller names, updates in
    place when handed an annotation_name, and never deletes a mark already promoted to
    a Clinical Procedure."""

    def setUp(self):
        if not api._has_field("Clinical Procedure", "custom_annotations"):
            self.skipTest("do_health custom_annotations table is absent on this site")

    def _annotation_payload(self, **overrides):
        payload = {
            "file_data": PIXEL_PNG,
            "json_text": json.dumps({"elements": [TEMPLATE_ELEMENT]}),
        }
        payload.update(overrides)
        return payload

    def _child_annotations(self, doctype, docname):
        return frappe.get_all(
            "Health Annotation Table",
            filters={"parenttype": doctype, "parent": docname},
            pluck="annotation",
        )

    def test_annotation_anchors_to_procedure(self):
        patient = self._make_patient()
        encounter = self._make_encounter(patient)
        procedure = self._make_clinical_procedure(patient)

        saved = api.save_derma_annotation(
            self._annotation_payload(
                patient=patient,
                encounter=encounter.name,
                clinical_procedure=procedure.name,
            )
        )

        self.assertTrue(saved and saved.get("name"))
        self.assertIn(saved["name"], self._child_annotations("Clinical Procedure", procedure.name))
        self.assertEqual(self._child_annotations("Patient Encounter", encounter.name), [])
        counts = api._get_annotation_counts_for_procedures([procedure.name])
        self.assertEqual(counts.get(procedure.name), 1)

    def test_annotation_anchors_to_encounter_by_default(self):
        patient = self._make_patient()
        encounter = self._make_encounter(patient)

        saved = api.save_derma_annotation(self._annotation_payload(patient=patient, encounter=encounter.name))

        self.assertIn(saved["name"], self._child_annotations("Patient Encounter", encounter.name))

    def test_resume_updates_in_place(self):
        patient = self._make_patient()
        encounter = self._make_encounter(patient)
        procedure = self._make_clinical_procedure(patient)
        first = api.save_derma_annotation(
            self._annotation_payload(patient=patient, encounter=encounter.name, clinical_procedure=procedure.name)
        )

        second = api.save_derma_annotation(
            self._annotation_payload(
                patient=patient,
                encounter=encounter.name,
                clinical_procedure=procedure.name,
                annotation_name=first["name"],
            )
        )

        self.assertEqual(second["name"], first["name"])
        self.assertEqual(self._child_annotations("Clinical Procedure", procedure.name), [first["name"]])

    def test_promoted_mark_survives_resave(self):
        patient = self._make_patient()
        encounter = self._make_encounter(patient)
        procedure = self._make_clinical_procedure(patient)
        annotation = api.save_derma_annotation(
            self._annotation_payload(patient=patient, encounter=encounter.name, clinical_procedure=procedure.name)
        )
        promoted = self._make_orphan_mark(patient, annotation["name"], clinical_procedure=procedure.name)
        unpromoted = self._make_orphan_mark(patient, annotation["name"])

        api.save_derma_annotation(
            self._annotation_payload(
                patient=patient,
                encounter=encounter.name,
                clinical_procedure=procedure.name,
                annotation_name=annotation["name"],
            )
        )

        self.assertTrue(frappe.db.exists("Derma Chart Mark", promoted))
        self.assertFalse(frappe.db.exists("Derma Chart Mark", unpromoted))

    def _make_orphan_mark(self, patient, annotation, clinical_procedure=None):
        """A mark whose element_id is absent from the scene, so the sync's deletion loop
        considers it - the promoted one must still survive."""
        mark = frappe.get_doc(
            {
                "doctype": "Derma Chart Mark",
                "patient": patient,
                "annotation": annotation,
                "clinical_procedure": clinical_procedure,
                "annotation_json": json.dumps({"element_id": frappe.generate_hash(length=8)}),
                "x_percent": 10,
                "y_percent": 10,
            }
        ).insert(ignore_permissions=True)
        return mark.name


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
