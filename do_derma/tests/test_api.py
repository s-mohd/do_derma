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
		return (
			frappe.get_doc(
				{
					"doctype": "Patient",
					"first_name": f"Derma{token}",
					"sex": "Male",
					"mobile": f"+1555{digits}",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _get_or_create_appointment_type(self):
		existing = frappe.db.get_value("Appointment Type", {}, "name")
		if existing:
			return existing
		token = frappe.generate_hash(length=8)
		return (
			frappe.get_doc(
				{
					"doctype": "Appointment Type",
					"appointment_type": f"Derma-{token}",
					"allow_booking_for": "Practitioner",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _get_or_create_practitioner(self):
		existing = frappe.db.get_value("Healthcare Practitioner", {"status": "Active"}, "name")
		if existing:
			return existing
		token = frappe.generate_hash(length=8)
		return (
			frappe.get_doc(
				{
					"doctype": "Healthcare Practitioner",
					"first_name": f"Derma{token}",
					"status": "Active",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

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

	def _make_procedure_template_with_category(self, category_title):
		"""A template and category of this test's own.

		`_get_or_create_procedure_template` returns whatever row the site happens
		to hold first, and `create_derma_chart_procedure` lets the template's own
		category win over the payload's - so a test that cares about the category
		must not share a template with the rest of the suite.
		"""
		token = frappe.generate_hash(length=8)
		category = None
		if frappe.db.exists("DocType", "Derma Procedure Category"):
			category = (
				frappe.get_doc(
					{
						"doctype": "Derma Procedure Category",
						"title": f"{category_title} {token}" if category_title else None,
						"workflow": "Aesthetic",
						"marker_behavior": "numbered_dot",
					}
				)
				.insert(ignore_permissions=True)
				.name
			)

		doc = frappe.get_doc(
			{
				"doctype": "Clinical Procedure Template",
				"template": f"Derma{token}",
				"item_code": f"Derma{token}",
				"description": f"Derma{token} - category fixture.",
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
			}
		)
		doc.set("is_billable", 0)
		doc.insert(ignore_permissions=True)
		if category and api._has_field("Clinical Procedure Template", "custom_derma_category"):
			frappe.db.set_value("Clinical Procedure Template", doc.name, "custom_derma_category", category)
		return doc.name

	def _save_mark(self, patient, **extra):
		return api.save_chart_mark(
			json.dumps({"patient": patient, "x_percent": 10, "y_percent": 20, **extra})
		)

	def _make_body_template(self, **extra):
		token = frappe.generate_hash(length=8)
		return (
			frappe.get_doc(
				{
					"doctype": "Derma Body Template",
					"title": f"Derma {token}",
					"gender": "Female",
					"view_key": f"derma_{token}",
					**extra,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _make_body_template_part(self, body_template, part_name, **extra):
		return (
			frappe.get_doc(
				{
					"doctype": "Derma Body Template Part",
					"body_template": body_template,
					"part_name": part_name,
					"shape_json": json.dumps([[0, 0], [10, 0], [10, 10], [0, 10]]),
					**extra,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _make_user_with_role(self, role):
		email = f"derma-{role.lower().replace(' ', '-')}-{frappe.generate_hash(length=6)}@example.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": role,
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		user.add_roles(role)
		return email

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
		result = api.save_chart_mark(json.dumps({"patient": patient, "x_percent": 10, "y_percent": 20}))
		self.assertEqual(result["patient"], patient)

	def test_body_template_parts_are_gated(self):
		"""Area definitions are read before anything is drawn, so this is the first
		endpoint an unroled user reaches on the way into the studio."""
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.get_derma_body_template_parts("does-not-matter")

	def test_config_overview_is_gated(self):
		"""It lists how the clinic is configured, and the config page keeps roles: [],
		so this check is the only thing standing in front of it."""
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.get_derma_config_overview()

	def test_template_variable_writes_are_gated(self):
		"""It rewrites what every clinician is asked to record for a procedure, and the
		config page keeps roles: [], so this check is the only thing in front of it."""
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.save_derma_template_variables("does-not-matter", [])

	def test_template_variable_reads_are_gated(self):
		"""The builder's reader returns how the clinic is configured, one template at a time."""
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.get_derma_template_variables("does-not-matter")

	def test_inventory_readiness_is_gated(self):
		"""The readiness engines live outside api.py now, so this wrapper's gate is the
		only thing between an unroled user and one patient's product and lot numbers."""
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.get_inventory_readiness(patient="does-not-matter")

	def test_followup_intelligence_is_gated(self):
		"""It reads every mark's status and diagnosis for one patient."""
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.get_followup_intelligence("does-not-matter")

	def test_annotation_summary_is_gated(self):
		"""It reads another patient's drawings if it is not, and it is reachable from any desk
		form, so it is the easiest of these to call unnoticed."""
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.get_derma_annotation_summary("Patient Encounter", "does-not-matter")


class TestAnnotationSummary(DermaTestHelpers, IntegrationTestCase):
	def test_lists_an_encounter_annotation_without_the_scene(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		saved = api.save_derma_annotation(
			{
				"patient": patient,
				"encounter": encounter.name,
				"file_data": PIXEL_PNG,
				"json_text": json.dumps({"elements": [TEMPLATE_ELEMENT]}),
			}
		)

		rows = api.get_derma_annotation_summary("Patient Encounter", encounter.name)

		self.assertEqual([row["name"] for row in rows], [saved["name"]])
		self.assertNotIn("json", rows[0])
		self.assertTrue(rows[0]["label"])

	def test_labels_an_annotation_by_its_body_template(self):
		"""The label is stored on save; without it in the read every clinician-facing
		surface falls back to the docname hash."""
		if not api._has_field("Health Annotation", "custom_derma_body_template_title"):
			self.skipTest("custom_derma_body_template_title is not installed on this site")
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		api.save_derma_annotation(
			{
				"patient": patient,
				"encounter": encounter.name,
				"body_template_title": "Face & Scalp",
				"file_data": PIXEL_PNG,
				"json_text": json.dumps({"elements": [TEMPLATE_ELEMENT]}),
			}
		)

		rows = api.get_derma_annotation_summary("Patient Encounter", encounter.name)

		self.assertEqual(rows[0]["label"], "Face & Scalp")

	def test_chart_context_carries_the_annotation_label(self):
		if not api._has_field("Health Annotation", "custom_derma_body_template_title"):
			self.skipTest("custom_derma_body_template_title is not installed on this site")
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		api.save_derma_annotation(
			{
				"patient": patient,
				"encounter": encounter.name,
				"body_template_title": "Legs (Female)",
				"file_data": PIXEL_PNG,
				"json_text": json.dumps({"elements": [TEMPLATE_ELEMENT]}),
			}
		)

		context = api._load_derma_annotation_context(encounter=encounter.name, patient=patient)

		self.assertEqual(
			context["encounter_annotations"][0].get("custom_derma_body_template_title"),
			"Legs (Female)",
		)

	def test_returns_empty_for_an_unknown_document(self):
		self.assertEqual(api.get_derma_annotation_summary("Patient Encounter", "HLC-ENC-does-not-exist"), [])

	def test_rejects_a_doctype_that_cannot_hold_annotations(self):
		patient = self._make_patient()
		with self.assertRaises(frappe.ValidationError):
			api.get_derma_annotation_summary("Patient", patient)


class TestSaveChartMark(DermaTestHelpers, IntegrationTestCase):
	def test_round_trips_position_and_patient(self):
		patient = self._make_patient()
		saved = api.save_chart_mark(json.dumps({"patient": patient, "x_percent": 33.5, "y_percent": 67.25}))
		self.assertTrue(saved.get("name"))
		stored = frappe.get_doc("Derma Chart Mark", saved["name"])
		self.assertEqual(stored.patient, patient)
		self.assertEqual(stored.x_percent, 33.5)
		self.assertEqual(stored.y_percent, 67.25)


class TestDiscardChartMarks(DermaTestHelpers, IntegrationTestCase):
	"""Marks reach the server as they are drawn, so discarding the drawing has to undo
	them. It may only undo the ones nothing else has claimed."""

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		self.patient = self._make_patient()
		self.encounter = self._make_encounter(self.patient)
		self.procedure = self._make_clinical_procedure(self.patient)

	def _make_mark(self):
		return api.save_chart_mark(
			json.dumps(
				{
					"patient": self.patient,
					"encounter": self.encounter.name,
					"clinical_procedure": self.procedure.name,
					"x_percent": 40,
					"y_percent": 60,
				}
			)
		)["name"]

	def test_deletes_a_mark_placed_on_a_draft_procedure(self):
		"""delete_chart_mark refuses these - every procedure-anchored mark is linked to
		its own procedure by construction, which is not the same as being documented."""
		mark = self._make_mark()

		result = api.discard_chart_marks([mark])

		self.assertEqual(result["deleted"], [mark])
		self.assertEqual(result["kept"], [])
		self.assertFalse(frappe.db.exists("Derma Chart Mark", mark))

	def test_keeps_a_mark_that_belongs_to_a_saved_annotation(self):
		mark = self._make_mark()
		annotation = api.save_derma_annotation(
			{
				"patient": self.patient,
				"encounter": self.encounter.name,
				"file_data": PIXEL_PNG,
				"json_text": json.dumps({"elements": [TEMPLATE_ELEMENT]}),
			}
		)
		frappe.db.set_value("Derma Chart Mark", mark, "annotation", annotation["name"])

		result = api.discard_chart_marks([mark])

		self.assertEqual(result["kept"], [mark])
		self.assertTrue(frappe.db.exists("Derma Chart Mark", mark))

	def test_keeps_a_mark_on_a_submitted_procedure(self):
		mark = self._make_mark()
		# Submitting through healthcare needs stock and consumables; the docstatus is the
		# only part of that this rule reads.
		frappe.db.set_value("Clinical Procedure", self.procedure.name, "docstatus", 1)

		result = api.discard_chart_marks([mark])

		self.assertEqual(result["kept"], [mark])
		self.assertTrue(frappe.db.exists("Derma Chart Mark", mark))

	def test_ignores_a_mark_that_is_already_gone(self):
		result = api.discard_chart_marks(json.dumps(["DCM-does-not-exist"]))

		self.assertEqual(result, {"deleted": [], "kept": []})

	def test_is_gated(self):
		mark = self._make_mark()
		frappe.set_user(self._make_limited_user())

		with self.assertRaises(frappe.PermissionError):
			api.discard_chart_marks([mark])


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
			self._annotation_payload(
				patient=patient, encounter=encounter.name, clinical_procedure=procedure.name
			)
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

	def test_resaving_an_older_annotation_returns_that_annotation(self):
		"""A procedure can hold several drawings; resuming an older one must hand
		back that drawing, or the studio's next save overwrites the wrong one."""
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		first = api.save_derma_annotation(
			self._annotation_payload(
				patient=patient, encounter=encounter.name, clinical_procedure=procedure.name
			)
		)
		second = api.save_derma_annotation(
			self._annotation_payload(
				patient=patient, encounter=encounter.name, clinical_procedure=procedure.name
			)
		)
		self.assertNotEqual(second["name"], first["name"])

		resumed = api.save_derma_annotation(
			self._annotation_payload(
				patient=patient,
				encounter=encounter.name,
				clinical_procedure=procedure.name,
				annotation_name=first["name"],
			)
		)

		self.assertEqual(resumed["name"], first["name"])

	def test_promoted_mark_survives_resave(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		annotation = api.save_derma_annotation(
			self._annotation_payload(
				patient=patient, encounter=encounter.name, clinical_procedure=procedure.name
			)
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

	def test_resave_does_not_duplicate_a_drawn_mark(self):
		"""A drawn mark (area or freehand) is saved the moment it is committed, so the annotation
		save must only re-link it. The element carries the same id both times, which is the key
		the fan-out matches on."""
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		element_id = "freehand-element-1"
		mark = api.save_chart_mark(
			{
				"patient": patient,
				"encounter": encounter.name,
				"x_percent": 40,
				"y_percent": 55,
				"annotation_json": json.dumps({"element_id": element_id, "shape": "freehand"}),
			}
		)
		stroke = {
			"id": element_id,
			"type": "freedraw",
			"customData": {"kind": "derma_mark", "derma_chart_mark": mark["name"], "shape": "freehand"},
		}
		payload = self._annotation_payload(
			patient=patient,
			encounter=encounter.name,
			json_text=json.dumps({"elements": [TEMPLATE_ELEMENT, stroke]}),
		)

		first = api.save_derma_annotation(payload)
		api.save_derma_annotation({**payload, "annotation_name": first["name"]})

		marks = frappe.get_all("Derma Chart Mark", filters={"encounter": encounter.name}, pluck="name")
		self.assertEqual(marks, [mark["name"]])
		self.assertEqual(frappe.db.get_value("Derma Chart Mark", mark["name"], "annotation"), first["name"])

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


class TestAnnotationStorage(DermaTestHelpers, IntegrationTestCase):
	"""The client stops persisting the body template's base64 payload (~35 KB per record),
	because the load path rebuilds it from the template URL. Two properties must hold on the
	server side of that contract."""

	def _stripped_scene(self, extra_elements=()):
		"""What the browser now sends: the template element without its dataURL, no files map."""
		return json.dumps({"elements": [TEMPLATE_ELEMENT, *extra_elements], "files": {}})

	def test_marks_still_backlink_when_the_scene_carries_no_image_payload(self):
		"""_sync_chart_marks_for_annotation returns early without a template element, so a strip
		that removed the element - rather than just its payload - would silently stop every mark
		being linked to its annotation, with no error anywhere."""
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		mark = api.save_chart_mark(
			{"patient": patient, "encounter": encounter.name, "x_percent": 20, "y_percent": 30}
		)
		stamped = {
			"id": "stamped-element",
			"type": "ellipse",
			"customData": {"kind": "derma_mark", "derma_chart_mark": mark["name"]},
		}

		saved = api.save_derma_annotation(
			{
				"patient": patient,
				"encounter": encounter.name,
				"file_data": PIXEL_PNG,
				"json_text": self._stripped_scene([stamped]),
			}
		)

		self.assertEqual(frappe.db.get_value("Derma Chart Mark", mark["name"], "annotation"), saved["name"])

	def test_stored_scene_keeps_the_template_element(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)

		saved = api.save_derma_annotation(
			{
				"patient": patient,
				"encounter": encounter.name,
				"file_data": PIXEL_PNG,
				"json_text": self._stripped_scene(),
				"body_template_title": "Face Map",
			}
		)

		scene = json.loads(frappe.db.get_value("Health Annotation", saved["name"], "json"))
		kinds = [(element.get("customData") or {}).get("kind") for element in scene["elements"]]
		self.assertIn("derma_template", kinds)
		self.assertNotIn("dataURL", json.dumps(scene["elements"]))
		# The reload path needs a URL to rebuild the background from.
		self.assertTrue(scene.get("derma_template") is not None or kinds.count("derma_template"))


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


class TestCompleteDermaSessionBlockers(DermaTestHelpers, IntegrationTestCase):
	"""The gate that used to live only in the browser. Warn is today's behaviour; Block
	refuses a session with live blockers unless a reason is recorded."""

	def setUp(self):
		self.patient = self._make_patient()
		self.encounter = self._make_encounter(self.patient)

	def _complete(self, enforcement, **kwargs):
		settings = {
			"enforcement": enforcement,
			"todo_downgrades_blockers": True,
			"is_configurable": True,
		}
		with patch("do_derma.readiness.session.get_readiness_settings", return_value=settings):
			return api.complete_derma_session(encounter=self.encounter.name, patient=self.patient, **kwargs)

	def _blocking_mark(self):
		return self._save_mark(self.patient, encounter=self.encounter.name, status="Worse")

	def test_warn_mode_completes_and_still_reports_the_blockers(self):
		self._blocking_mark()

		result = self._complete("Warn")

		self.assertTrue(result["encounter_submitted"])
		self.assertTrue(result["readiness"]["blockers"])

	def test_block_mode_refuses_a_session_with_blockers_and_no_reason(self):
		self._blocking_mark()

		with self.assertRaises(frappe.ValidationError):
			self._complete("Block")

		self.assertEqual(frappe.db.get_value("Patient Encounter", self.encounter.name, "docstatus"), 0)

	def test_a_refused_session_submits_no_procedure(self):
		self._blocking_mark()

		with patch.object(api, "_complete_derma_procedures_for_session") as complete_procedures:
			with self.assertRaises(frappe.ValidationError):
				self._complete("Block")

		complete_procedures.assert_not_called()

	def test_a_blank_reason_is_no_reason(self):
		self._blocking_mark()

		with self.assertRaises(frappe.ValidationError):
			self._complete("Block", override_reason="   ")

	def test_block_mode_with_a_reason_completes_and_records_it(self):
		self._blocking_mark()

		result = self._complete("Block", override_reason="Patient leaving the country tomorrow.")

		self.assertTrue(result["encounter_submitted"])
		self.assertEqual(
			frappe.db.get_value("Patient Encounter", self.encounter.name, api.COMPLETION_OVERRIDE_FIELD),
			"Patient leaving the country tomorrow.",
		)

	def test_the_override_comment_names_the_user_and_the_blockers(self):
		self._blocking_mark()

		blockers = self._complete("Block", override_reason="Reviewed with the consultant.")["readiness"][
			"blockers"
		]

		comment = frappe.db.get_value(
			"Comment",
			{"reference_doctype": "Patient Encounter", "reference_name": self.encounter.name},
			"content",
		)
		self.assertIn(frappe.session.user, comment)
		self.assertIn("Reviewed with the consultant.", comment)
		for blocker in blockers:
			self.assertIn(blocker["title"], comment)

	def test_a_site_without_the_field_still_records_the_reason_in_the_comment(self):
		"""The encounter field is the queryable copy; the Comment is the one that always
		survives, so a site whose schema has not converged loses nothing."""
		self._blocking_mark()

		real_has_field = api._has_field

		def without_the_override_field(doctype, fieldname):
			return False if fieldname == api.COMPLETION_OVERRIDE_FIELD else real_has_field(doctype, fieldname)

		with patch.object(api, "_has_field", side_effect=without_the_override_field):
			self._complete("Block", override_reason="Consultant reviewed by phone.")

		comment = frappe.db.get_value(
			"Comment",
			{"reference_doctype": "Patient Encounter", "reference_name": self.encounter.name},
			"content",
		)
		self.assertIn("Consultant reviewed by phone.", comment)

	def test_block_mode_completes_a_session_with_no_blockers(self):
		result = self._complete("Block")

		self.assertTrue(result["encounter_submitted"])
		self.assertEqual(result["readiness"]["blockers"], [])


class TestCreateChartProcedure(DermaTestHelpers, IntegrationTestCase):
	"""The Procedures tab's New Procedure button is this endpoint's first caller, so the
	contract it now depends on is pinned here rather than assumed."""

	def test_creates_a_procedure_from_a_template_alone(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		template = self._get_or_create_procedure_template()

		result = api.create_derma_chart_procedure(
			{
				"patient": patient,
				"encounter": encounter.name,
				"procedure_template": template,
				"notes": "Created from the Procedures tab.",
			}
		)

		procedure = result["clinical_procedure"]
		self.assertEqual(procedure["patient"], patient)
		self.assertEqual(procedure["procedure_template"], template)
		self.assertEqual(procedure["status"], "Draft")

	def test_requires_an_encounter(self):
		"""The button is disabled without one; the server must not rely on that."""
		patient = self._make_patient()
		with self.assertRaises(frappe.ValidationError):
			api.create_derma_chart_procedure(
				{"patient": patient, "procedure_template": self._get_or_create_procedure_template()}
			)

	def test_requires_a_procedure_template(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		with self.assertRaises(frappe.ValidationError):
			api.create_derma_chart_procedure({"patient": patient, "encounter": encounter.name})

	def test_a_clinic_named_category_does_not_break_the_treatment_entry(self):
		"""Derma Procedure Category is clinic-defined; Derma Treatment Entry.procedure_type is a
		fixed Select. Writing the category straight through threw and lost the whole procedure."""
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		template = self._make_procedure_template_with_category("A Category No Select Offers")

		result = api.create_derma_chart_procedure(
			{
				"patient": patient,
				"encounter": encounter.name,
				"procedure_template": template,
				"product_name": "Botulinum",
			}
		)

		self.assertTrue(result["clinical_procedure"]["name"])
		self.assertEqual(result["treatment_entry"]["procedure_type"], "Other")

	def test_a_recognised_category_is_kept(self):
		"""The mapping's single owner - all three treatment-entry writers go through it."""
		self.assertEqual(api._treatment_procedure_type("Biopsy"), "Biopsy")
		self.assertEqual(api._treatment_procedure_type("Botox"), "Botox")
		self.assertEqual(api._treatment_procedure_type("A Category No Select Offers"), "Other")
		self.assertEqual(api._treatment_procedure_type(None), "Other")


class TestCarryForwardMarks(DermaTestHelpers, IntegrationTestCase):
	"""Copy marks from last visit. The copy must be a new mark on the new encounter with
	none of the source's links carried across, or the previous visit's procedure, finding
	and annotation would be re-used by a visit they do not belong to."""

	def _make_mark(self, patient, encounter, **values):
		payload = {"patient": patient, "encounter": encounter, "x_percent": 40, "y_percent": 60}
		payload.update(values)
		return api.save_chart_mark(json.dumps(payload))

	def test_copies_a_mark_onto_the_current_encounter(self):
		patient = self._make_patient()
		previous = self._make_encounter(patient)
		current = self._make_encounter(patient)
		source = self._make_mark(patient, previous.name, product_name="Botulinum")

		result = api.carry_forward_marks(
			[source["name"]], patient=patient, encounter=current.name, status="Monitoring"
		)

		self.assertEqual(len(result["marks"]), 1)
		copy = frappe.get_doc("Derma Chart Mark", result["marks"][0]["name"])
		self.assertNotEqual(copy.name, source["name"])
		self.assertEqual(copy.encounter, current.name)
		self.assertEqual(copy.product_name, "Botulinum")
		self.assertEqual(copy.status, "Monitoring")

	def test_copy_carries_no_link_from_the_source_visit(self):
		patient = self._make_patient()
		previous = self._make_encounter(patient)
		current = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		source = self._make_mark(patient, previous.name, clinical_procedure=procedure.name)
		self.assertEqual(
			frappe.db.get_value("Derma Chart Mark", source["name"], "clinical_procedure"), procedure.name
		)

		result = api.carry_forward_marks([source["name"]], patient=patient, encounter=current.name)

		copy = frappe.get_doc("Derma Chart Mark", result["marks"][0]["name"])
		self.assertFalse(copy.clinical_procedure)
		self.assertFalse(copy.finding)
		self.assertFalse(copy.treatment_entry)
		self.assertFalse(copy.annotation)

	def test_skips_a_mark_already_on_this_encounter(self):
		"""Re-running the copy must not fan a visit's own marks out into duplicates."""
		patient = self._make_patient()
		current = self._make_encounter(patient)
		source = self._make_mark(patient, current.name)

		result = api.carry_forward_marks([source["name"]], patient=patient, encounter=current.name)

		self.assertEqual(result["marks"], [])

	def test_refuses_a_mark_belonging_to_another_patient(self):
		patient = self._make_patient()
		other = self._make_patient()
		current = self._make_encounter(patient)
		foreign = self._make_mark(other, self._make_encounter(other).name)

		with self.assertRaises(frappe.ValidationError):
			api.carry_forward_marks([foreign["name"]], patient=patient, encounter=current.name)

	def test_is_gated(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.carry_forward_marks(["does-not-matter"], patient="does-not-matter")


class TestProcedureFieldUpdates(DermaTestHelpers, IntegrationTestCase):
	"""The chart's note dialog and price-override controls both ride on
	update_clinical_procedure_fields; the derma billing fields are custom
	fields created by ensure_derma_schema."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from do_derma.schema import ensure_derma_schema

		ensure_derma_schema()

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")

	def test_notes_and_price_override_round_trip(self):
		# The core `notes` field is set_only_once (healthcare), so the note
		# dialog writes custom_derma_notes instead.
		procedure = self._make_clinical_procedure(self._make_patient())
		api.update_clinical_procedure_fields(
			procedure.name,
			updates=json.dumps(
				{
					"custom_derma_notes": "Post-care advice given.",
					"custom_derma_price_override": 120.5,
					"custom_derma_no_charge": 1,
					"custom_derma_price_list": None,
					"custom_derma_price_override_reason": "Loyalty discount",
				}
			),
		)
		doc = frappe.get_doc("Clinical Procedure", procedure.name)
		self.assertEqual(doc.custom_derma_notes, "Post-care advice given.")
		self.assertEqual(doc.custom_derma_price_override, 120.5)
		self.assertEqual(doc.custom_derma_no_charge, 1)
		self.assertEqual(doc.custom_derma_price_override_reason, "Loyalty discount")

	def test_note_edit_survives_a_second_save(self):
		"""set_only_once on the core notes field is exactly what broke Save Note."""
		procedure = self._make_clinical_procedure(self._make_patient())
		api.update_clinical_procedure_fields(
			procedure.name, updates=json.dumps({"custom_derma_notes": "First note"})
		)
		api.update_clinical_procedure_fields(
			procedure.name, updates=json.dumps({"custom_derma_notes": "Amended note"})
		)
		self.assertEqual(
			frappe.db.get_value("Clinical Procedure", procedure.name, "custom_derma_notes"),
			"Amended note",
		)

	def test_is_gated(self):
		frappe.set_user(self._make_limited_user())
		with self.assertRaises(frappe.PermissionError):
			api.update_clinical_procedure_fields("does-not-matter", updates="{}")


class TestDermaNoteTemplate(IntegrationTestCase):
	"""The procedure note dialog's template picker reads this doctype."""

	def test_note_template_round_trips(self):
		name = "Test Note Template"
		if frappe.db.exists("Derma Note Template", name):
			frappe.delete_doc("Derma Note Template", name, force=True)
		doc = frappe.get_doc(
			{
				"doctype": "Derma Note Template",
				"title": name,
				"note": "Area cleaned and prepped. Aftercare leaflet handed over.",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Derma Note Template", doc.name, force=True)
		self.assertEqual(
			frappe.db.get_value("Derma Note Template", name, "note"),
			"Area cleaned and prepped. Aftercare leaflet handed over.",
		)
		self.assertFalse(frappe.db.get_value("Derma Note Template", name, "disabled"))


class DermaPhotoHelpers(DermaTestHelpers):
	def _make_photo_set(self, **payload):
		return api.create_photo_set(
			{
				"patient": self.patient,
				"encounter": self.encounter.name,
				"photos": [{"image": "/files/derma-a.png"}],
				**payload,
			}
		)

	def _photo_types(self, photo_set):
		return [photo.get("photo_type") for photo in photo_set["photos"]]


class TestPhotoStageDerivation(DermaPhotoHelpers, IntegrationTestCase):
	"""Capture asks the clinician nothing, so the server decides the stage from the
	state of the visit."""

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		self.patient = self._make_patient()
		self.encounter = self._make_encounter(self.patient)

	def test_a_photo_taken_outside_a_procedure_is_a_visit_photo(self):
		photo_set = self._make_photo_set()

		self.assertEqual(self._photo_types(photo_set), ["Visit"])
		self.assertEqual(photo_set["set_type"], "Visit")

	def test_a_photo_taken_before_the_procedure_starts_is_a_before_photo(self):
		procedure = self._make_clinical_procedure(self.patient)

		photo_set = self._make_photo_set(clinical_procedure=procedure.name)

		self.assertEqual(self._photo_types(photo_set), ["Before"])
		self.assertEqual(photo_set["set_type"], "Before/After")

	def test_a_photo_taken_once_the_procedure_runs_is_an_after_photo(self):
		procedure = self._make_clinical_procedure(self.patient)
		frappe.db.set_value("Clinical Procedure", procedure.name, "status", "In Progress")

		photo_set = self._make_photo_set(clinical_procedure=procedure.name)

		self.assertEqual(self._photo_types(photo_set), ["After"])

	def test_a_photo_taken_after_the_procedure_completes_is_an_after_photo(self):
		procedure = self._make_clinical_procedure(self.patient)
		frappe.db.set_value("Clinical Procedure", procedure.name, "status", "Completed")

		photo_set = self._make_photo_set(clinical_procedure=procedure.name)

		self.assertEqual(self._photo_types(photo_set), ["After"])

	def test_an_explicit_stage_is_left_alone(self):
		"""The desk form and older callers still name the stage themselves."""
		photo_set = self._make_photo_set(photos=[{"image": "/files/derma-a.png", "photo_type": "Dermoscopy"}])

		self.assertEqual(self._photo_types(photo_set), ["Dermoscopy"])

	def test_derivation_leaves_the_links_intact(self):
		procedure = self._make_clinical_procedure(self.patient)
		mark = self._save_mark(self.patient, encounter=self.encounter.name)

		photo_set = self._make_photo_set(clinical_procedure=procedure.name, chart_mark=mark["name"])

		self.assertEqual(photo_set["clinical_procedure"], procedure.name)
		self.assertEqual(photo_set["encounter"], self.encounter.name)
		self.assertEqual(
			frappe.db.get_value("Derma Chart Mark", mark["name"], "photo_set"), photo_set["name"]
		)


class TestUpdatePhotoStage(DermaPhotoHelpers, IntegrationTestCase):
	"""A derived stage is a guess, so the clinician can correct it - on this visit only."""

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		self.patient = self._make_patient()
		self.encounter = self._make_encounter(self.patient)

	def test_retags_a_photo_on_the_current_encounter(self):
		photo_set = self._make_photo_set()
		photo = photo_set["photos"][0]["name"]

		result = api.update_photo_stage(photo, "Before")

		self.assertEqual(self._photo_types(result), ["Before"])
		self.assertEqual(frappe.db.get_value("Derma Photo", photo, "photo_type"), "Before")

	def test_refuses_a_photo_from_an_earlier_encounter(self):
		photo_set = self._make_photo_set()
		photo = photo_set["photos"][0]["name"]
		self._make_encounter(self.patient)

		with self.assertRaises(frappe.ValidationError):
			api.update_photo_stage(photo, "After")

		self.assertEqual(frappe.db.get_value("Derma Photo", photo, "photo_type"), "Visit")

	def test_refuses_a_stage_the_doctype_does_not_offer(self):
		photo_set = self._make_photo_set()
		photo = photo_set["photos"][0]["name"]

		with self.assertRaises(frappe.ValidationError):
			api.update_photo_stage(photo, "Sideways")

	def test_refuses_a_photo_that_does_not_exist(self):
		with self.assertRaises(frappe.ValidationError):
			api.update_photo_stage("DP-does-not-exist", "Before")

	def test_is_gated(self):
		photo_set = self._make_photo_set()
		photo = photo_set["photos"][0]["name"]
		frappe.set_user(self._make_limited_user())

		with self.assertRaises(frappe.PermissionError):
			api.update_photo_stage(photo, "Before")

	def test_refuses_a_reader_who_cannot_write_photo_sets(self):
		"""A Nursing User reads the chart; the gate lets them in and the doctype stops them."""
		photo_set = self._make_photo_set()
		photo = photo_set["photos"][0]["name"]
		frappe.set_user(self._make_user_with_role("Nursing User"))

		with self.assertRaises(frappe.PermissionError):
			api.update_photo_stage(photo, "Before")

	def test_refuses_a_photo_set_with_no_visit(self):
		photo_set = self._make_photo_set()
		photo = photo_set["photos"][0]["name"]
		frappe.db.set_value("Derma Photo Set", photo_set["name"], "encounter", None)

		with self.assertRaises(frappe.ValidationError):
			api.update_photo_stage(photo, "Before")


class TestDeletePhoto(DermaPhotoHelpers, IntegrationTestCase):
	"""A mis-shot photo is removed from the visit that took it, and never from an
	earlier one."""

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		self.patient = self._make_patient()
		self.encounter = self._make_encounter(self.patient)

	def test_removes_one_photo_and_keeps_the_set(self):
		photo_set = self._make_photo_set(
			photos=[{"image": "/files/derma-a.png"}, {"image": "/files/derma-b.png"}]
		)
		photo = photo_set["photos"][0]["name"]

		result = api.delete_photo(photo)

		self.assertEqual(result["photo_set"], photo_set["name"])
		self.assertFalse(result["set_deleted"])
		self.assertTrue(frappe.db.exists("Derma Photo Set", photo_set["name"]))
		self.assertFalse(frappe.db.exists("Derma Photo", photo))

	def test_removes_the_set_once_its_last_photo_goes(self):
		photo_set = self._make_photo_set()
		photo = photo_set["photos"][0]["name"]

		result = api.delete_photo(photo)

		self.assertTrue(result["set_deleted"])
		self.assertFalse(frappe.db.exists("Derma Photo Set", photo_set["name"]))

	def test_refuses_a_photo_from_an_earlier_encounter(self):
		photo_set = self._make_photo_set()
		photo = photo_set["photos"][0]["name"]
		self._make_encounter(self.patient)

		with self.assertRaises(frappe.ValidationError):
			api.delete_photo(photo)

		self.assertTrue(frappe.db.exists("Derma Photo", photo))

	def test_releases_what_pointed_at_the_set_it_deletes(self):
		mark = self._save_mark(self.patient, encounter=self.encounter.name)
		photo_set = self._make_photo_set(chart_mark=mark["name"])
		photo = photo_set["photos"][0]["name"]

		api.delete_photo(photo)

		self.assertFalse(frappe.db.exists("Derma Photo Set", photo_set["name"]))
		self.assertIsNone(frappe.db.get_value("Derma Chart Mark", mark["name"], "photo_set"))

	def test_ignores_a_photo_that_is_already_gone(self):
		"""Discarding follows discard_chart_marks: a second click is not an error."""
		result = api.delete_photo("DP-does-not-exist")

		self.assertEqual(result, {"photo_set": "", "set_deleted": False})

	def test_is_gated(self):
		photo_set = self._make_photo_set()
		photo = photo_set["photos"][0]["name"]
		frappe.set_user(self._make_limited_user())

		with self.assertRaises(frappe.PermissionError):
			api.delete_photo(photo)

	def test_refuses_a_reader_who_cannot_write_photo_sets(self):
		photo_set = self._make_photo_set()
		photo = photo_set["photos"][0]["name"]
		frappe.set_user(self._make_user_with_role("Nursing User"))

		with self.assertRaises(frappe.PermissionError):
			api.delete_photo(photo)
