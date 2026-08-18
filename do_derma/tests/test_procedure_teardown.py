from __future__ import annotations

import json

import frappe
from frappe.tests import IntegrationTestCase

import do_derma.api as api
from do_derma.teardown import scene
from do_derma.tests.test_api import PIXEL_PNG, TEMPLATE_ELEMENT, DermaTestHelpers


def stamp(mark_name, element_id, **custom):
	"""An element the chart rendered for a mark, the way EmbeddedExcalidraw tags it."""
	return {
		"id": element_id,
		"type": "ellipse",
		"customData": {
			"kind": "derma_mark",
			"generated_by": "render_chart_marks",
			"derma_chart_mark": mark_name,
			"mark_name": mark_name,
			**custom,
		},
	}


def stroke(element_id, **element):
	"""Something a practitioner drew: no customData, so it is never a derived layer."""
	return {"id": element_id, "type": "freedraw", **element}


class TestSceneMath(IntegrationTestCase):
	"""The scene arithmetic on its own - no site fixtures, so the hard part stays cheap to pin."""

	def test_every_element_of_a_stamp_goes_together(self):
		elements = [stamp("DCM-1", "a"), stamp("DCM-1", "b"), stamp("DCM-2", "c")]

		owned = scene.get_owned_ids(elements, {"DCM-1"}, set())

		self.assertEqual(owned, {"a", "b"})

	def test_a_history_copy_goes_with_its_mark(self):
		elements = [stamp("history:DCM-1", "a")]

		self.assertEqual(scene.get_owned_ids(elements, {"DCM-1"}, set()), {"a"})

	def test_a_drawn_mark_is_found_by_the_id_it_recorded(self):
		"""An area or freehand mark names no mark on the canvas; the mark names the element."""
		elements = [stroke("a"), stroke("b")]

		self.assertEqual(scene.get_owned_ids(elements, set(), {"a"}), {"a"})

	def test_bound_text_goes_with_its_container(self):
		elements = [stamp("DCM-1", "a"), {"id": "label", "type": "text", "containerId": "a"}]

		self.assertEqual(scene.get_owned_ids(elements, {"DCM-1"}, set()), {"a", "label"})

	def test_a_survivor_keeps_no_binding_to_a_removed_element(self):
		elements = [
			stamp("DCM-1", "a"),
			stroke("b", boundElements=[{"id": "a", "type": "arrow"}, {"id": "c", "type": "text"}]),
		]

		kept = scene.remove_elements(elements, {"a"})

		self.assertEqual([element["id"] for element in kept], ["b"])
		self.assertEqual(kept[0]["boundElements"], [{"id": "c", "type": "text"}])

	def test_the_badge_layer_goes_whole(self):
		"""Badges are numbered over the surviving marks, and the studio renumbers them on load."""
		elements = [stamp("DCM-1", "a"), {"id": "badge", "customData": {"kind": "derma_badge"}}]

		self.assertEqual(scene.get_owned_ids(elements, set(), set()), {"badge"})

	def test_a_scene_of_derived_layers_has_no_substance(self):
		elements = [
			TEMPLATE_ELEMENT,
			{"id": "part", "customData": {"kind": "derma_template_part"}},
			{"id": "badge", "customData": {"kind": "derma_badge"}},
			stamp("DCM-1", "a"),
		]

		self.assertFalse(scene.has_substance(elements))

	def test_one_stroke_is_substance(self):
		self.assertTrue(scene.has_substance([TEMPLATE_ELEMENT, stroke("a")]))


class TeardownHelpers(DermaTestHelpers):
	def _make_mark(self, patient, encounter, **values):
		payload = {"patient": patient, "encounter": encounter, "x_percent": 10, "y_percent": 20}
		payload.update(values)
		return api.save_chart_mark(json.dumps(payload))["name"]

	def _make_treatment_entry(self, patient, encounter, **values):
		return (
			frappe.get_doc(
				{
					"doctype": "Derma Treatment Entry",
					"patient": patient,
					"encounter": encounter,
					"workflow": "Medical",
					"procedure_type": "Other",
					**values,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _make_finding(self, patient, encounter):
		return (
			frappe.get_doc(
				{
					"doctype": "Derma Finding",
					"patient": patient,
					"encounter": encounter,
					"x_percent": 30,
					"y_percent": 40,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _make_photo_set(self, patient, **values):
		doc = frappe.get_doc({"doctype": "Derma Photo Set", "patient": patient, **values})
		doc.append(
			"photos",
			{
				"image": "/files/derma-teardown-test.png",
				"finding": values.get("finding"),
				"treatment_entry": values.get("treatment_entry"),
			},
		)
		return doc.insert(ignore_permissions=True).name


class TestProcedureTeardown(TeardownHelpers, IntegrationTestCase):
	"""Deleting a procedure takes the records it owns; a mark without its procedure is of no use."""

	def test_its_marks_are_deleted(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		mark = self._make_mark(patient, encounter.name, clinical_procedure=procedure.name)

		api.delete_clinical_procedure_entry("Clinical Procedure", procedure.name)

		self.assertFalse(frappe.db.exists("Clinical Procedure", procedure.name))
		self.assertFalse(frappe.db.exists("Derma Chart Mark", mark))

	def test_a_marks_consumable_rows_go_with_it(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		mark = self._make_mark(patient, encounter.name, clinical_procedure=procedure.name)

		api.delete_clinical_procedure_entry("Clinical Procedure", procedure.name)

		self.assertEqual(
			frappe.db.count("Clinical Procedure Item", {"parenttype": "Derma Chart Mark", "parent": mark}),
			0,
		)

	def test_its_treatment_entries_are_deleted(self):
		"""One entry the procedure names, one only a mark of its own names."""
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		linked = self._make_treatment_entry(patient, encounter.name, clinical_procedure=procedure.name)
		through_mark = self._make_treatment_entry(patient, encounter.name)
		self._make_mark(
			patient, encounter.name, clinical_procedure=procedure.name, treatment_entry=through_mark
		)

		api.delete_clinical_procedure_entry("Clinical Procedure", procedure.name)

		self.assertFalse(frappe.db.exists("Derma Treatment Entry", linked))
		self.assertFalse(frappe.db.exists("Derma Treatment Entry", through_mark))

	def test_a_finding_its_mark_pointed_at_is_deleted(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		finding = self._make_finding(patient, encounter.name)
		self._make_mark(patient, encounter.name, clinical_procedure=procedure.name, finding=finding)

		api.delete_clinical_procedure_entry("Clinical Procedure", procedure.name)

		self.assertFalse(frappe.db.exists("Derma Finding", finding))

	def test_a_finding_another_visits_mark_still_uses_is_kept(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		kept_procedure = self._make_clinical_procedure(patient)
		finding = self._make_finding(patient, encounter.name)
		self._make_mark(patient, encounter.name, clinical_procedure=procedure.name, finding=finding)
		survivor = self._make_mark(
			patient, encounter.name, clinical_procedure=kept_procedure.name, finding=finding
		)

		api.delete_clinical_procedure_entry("Clinical Procedure", procedure.name)

		self.assertTrue(frappe.db.exists("Derma Finding", finding))
		self.assertEqual(frappe.db.get_value("Derma Chart Mark", survivor, "finding"), finding)

	def test_another_procedures_mark_is_left_alone(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		deleted = self._make_clinical_procedure(patient)
		kept = self._make_clinical_procedure(patient)
		self._make_mark(patient, encounter.name, clinical_procedure=deleted.name)
		survivor = self._make_mark(patient, encounter.name, clinical_procedure=kept.name)

		api.delete_clinical_procedure_entry("Clinical Procedure", deleted.name)

		self.assertEqual(frappe.db.get_value("Derma Chart Mark", survivor, "clinical_procedure"), kept.name)

	def test_a_photo_set_survives_unlinked(self):
		"""Photos are clinical evidence: they outlive the procedure instead of blocking it."""
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		finding = self._make_finding(patient, encounter.name)
		entry = self._make_treatment_entry(patient, encounter.name, clinical_procedure=procedure.name)
		photo_set = self._make_photo_set(
			patient, clinical_procedure=procedure.name, finding=finding, treatment_entry=entry
		)
		self._make_mark(patient, encounter.name, clinical_procedure=procedure.name, finding=finding)

		api.delete_clinical_procedure_entry("Clinical Procedure", procedure.name)

		doc = frappe.get_doc("Derma Photo Set", photo_set)
		self.assertFalse(doc.clinical_procedure)
		self.assertFalse(doc.finding)
		self.assertFalse(doc.treatment_entry)
		self.assertFalse(doc.photos[0].finding)
		self.assertFalse(doc.photos[0].treatment_entry)

	def test_a_desk_delete_cascades_the_same_way(self):
		"""The hook owns this, not the endpoint - the desk and bulk delete go through delete_doc."""
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		mark = self._make_mark(patient, encounter.name, clinical_procedure=procedure.name)

		frappe.delete_doc("Clinical Procedure", procedure.name, ignore_permissions=True)

		self.assertFalse(frappe.db.exists("Derma Chart Mark", mark))


class TestAnnotationTeardown(TeardownHelpers, IntegrationTestCase):
	"""A drawing is one scene shared by many marks, so it is pruned rather than dropped."""

	def setUp(self):
		if not api._has_field("Clinical Procedure", "custom_annotations"):
			self.skipTest("do_health custom_annotations table is absent on this site")

	def _save_annotation(self, patient, encounter, elements, **values):
		return api.save_derma_annotation(
			{
				"patient": patient,
				"encounter": encounter,
				"file_data": PIXEL_PNG,
				"json_text": json.dumps({"elements": [TEMPLATE_ELEMENT, *elements]}),
				**values,
			}
		)["name"]

	def _elements(self, annotation):
		scene_json = api._parse_json(frappe.db.get_value("Health Annotation", annotation, "json"), {})
		return [element.get("id") for element in scene.get_elements(scene_json)]

	def test_a_shared_drawing_keeps_the_surviving_marks_element(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		deleted = self._make_clinical_procedure(patient)
		kept = self._make_clinical_procedure(patient)
		doomed_mark = self._make_mark(patient, encounter.name, clinical_procedure=deleted.name)
		survivor = self._make_mark(patient, encounter.name, clinical_procedure=kept.name)
		annotation = self._save_annotation(
			patient,
			encounter.name,
			[stamp(doomed_mark, "doomed"), stamp(survivor, "survivor"), stroke("drawn")],
		)

		api.delete_clinical_procedure_entry("Clinical Procedure", deleted.name)

		self.assertTrue(frappe.db.exists("Health Annotation", annotation))
		self.assertNotIn("doomed", self._elements(annotation))
		self.assertIn("survivor", self._elements(annotation))
		self.assertIn(TEMPLATE_ELEMENT["id"], self._elements(annotation))

	def test_a_drawing_left_with_nothing_is_deleted(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		mark = self._make_mark(patient, encounter.name, clinical_procedure=procedure.name)
		annotation = self._save_annotation(
			patient, encounter.name, [stamp(mark, "doomed")], clinical_procedure=procedure.name
		)

		api.delete_clinical_procedure_entry("Clinical Procedure", procedure.name)

		self.assertFalse(frappe.db.exists("Health Annotation", annotation))
		self.assertEqual(frappe.db.count("Health Annotation Table", {"annotation": annotation}), 0)

	def test_a_drawing_a_surviving_mark_still_names_is_kept(self):
		"""Deleting it would be refused by the link check and would abort the whole delete."""
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		deleted = self._make_clinical_procedure(patient)
		kept = self._make_clinical_procedure(patient)
		doomed_mark = self._make_mark(patient, encounter.name, clinical_procedure=deleted.name)
		survivor = self._make_mark(patient, encounter.name, clinical_procedure=kept.name)
		annotation = self._save_annotation(
			patient, encounter.name, [stamp(doomed_mark, "doomed"), stamp(survivor, "survivor")]
		)

		api.delete_clinical_procedure_entry("Clinical Procedure", deleted.name)

		self.assertTrue(frappe.db.exists("Health Annotation", annotation))
		self.assertEqual(frappe.db.get_value("Derma Chart Mark", survivor, "annotation"), annotation)

	def test_a_pruned_drawing_loses_the_preview_it_no_longer_matches(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		deleted = self._make_clinical_procedure(patient)
		kept = self._make_clinical_procedure(patient)
		doomed_mark = self._make_mark(patient, encounter.name, clinical_procedure=deleted.name)
		survivor = self._make_mark(patient, encounter.name, clinical_procedure=kept.name)
		annotation = self._save_annotation(
			patient, encounter.name, [stamp(doomed_mark, "doomed"), stamp(survivor, "survivor")]
		)
		self.assertTrue(frappe.db.get_value("Health Annotation", annotation, "image"))

		api.delete_clinical_procedure_entry("Clinical Procedure", deleted.name)

		self.assertFalse(frappe.db.get_value("Health Annotation", annotation, "image"))
		self.assertEqual(frappe.db.count("File", {"attached_to_name": annotation}), 0)

	def test_an_untouched_drawing_is_left_alone(self):
		patient = self._make_patient()
		encounter = self._make_encounter(patient)
		procedure = self._make_clinical_procedure(patient)
		self._make_mark(patient, encounter.name, clinical_procedure=procedure.name)
		other = self._save_annotation(patient, encounter.name, [stroke("drawn")])
		before = frappe.db.get_value("Health Annotation", other, ["json", "image"])

		api.delete_clinical_procedure_entry("Clinical Procedure", procedure.name)

		self.assertEqual(frappe.db.get_value("Health Annotation", other, ["json", "image"]), before)
