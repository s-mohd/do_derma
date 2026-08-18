"""The derma records a Clinical Procedure owns, and the order they can be deleted in."""

from __future__ import annotations

import frappe

from do_derma.teardown import annotations

MARK_FIELDS = ("name", "annotation", "annotation_json", "finding", "treatment_entry")


def delete_derma_records(procedure, method=None) -> None:
	"""Take this app's records with a Clinical Procedure on the way to the bin.

	A mark is of no use once the procedure it raised is gone, so it goes too, and takes the
	treatment entry, finding and drawing that only it accounted for. Frappe's link check runs
	after `on_trash`, so doing it here is also what lets the delete through.
	"""
	ProcedureTeardown(procedure.name).run()


class ProcedureTeardown:
	"""One procedure's derma records, read before anything is deleted."""

	def __init__(self, procedure: str) -> None:
		self.procedure = procedure
		self.marks = frappe.get_all(
			"Derma Chart Mark", filters={"clinical_procedure": procedure}, fields=list(MARK_FIELDS)
		)
		self.treatment_entries = self.get_treatment_entries()
		self.findings = sorted({mark.finding for mark in self.marks if mark.finding})
		self.annotations = self.get_annotations()

	@property
	def mark_names(self) -> set[str]:
		return {mark.name for mark in self.marks}

	@property
	def element_ids(self) -> set[str]:
		"""The canvas element each mark was drawn as."""
		from do_derma import api

		ids = set()
		for mark in self.marks:
			drawn = api._parse_json(mark.annotation_json, {})
			if isinstance(drawn, dict) and drawn.get("element_id"):
				ids.add(drawn["element_id"])
		return ids

	def get_treatment_entries(self) -> list[str]:
		"""Entries the procedure names, and entries only one of its marks names."""
		linked = frappe.get_all(
			"Derma Treatment Entry", filters={"clinical_procedure": self.procedure}, pluck="name"
		)
		return sorted({*linked, *(mark.treatment_entry for mark in self.marks if mark.treatment_entry)})

	def get_annotations(self) -> list[str]:
		"""Drawings these records were made on, plus the ones anchored on the procedure itself."""
		names = {mark.annotation for mark in self.marks if mark.annotation}
		names.update(
			frappe.get_all(
				"Health Annotation Table",
				filters={"parenttype": "Clinical Procedure", "parent": self.procedure},
				pluck="annotation",
			)
		)
		if self.treatment_entries:
			names.update(
				frappe.get_all(
					"Derma Treatment Entry",
					filters={"name": ["in", self.treatment_entries]},
					pluck="annotation",
				)
			)
		return sorted(name for name in names if name)

	def run(self) -> None:
		release_photo_links("clinical_procedure", [self.procedure])
		emptied = [name for name in self.annotations if self.prune(name)]
		delete_documents("Derma Chart Mark", sorted(self.mark_names))
		self.strip_treatment_entries()
		self.strip_findings()
		annotations.discard(emptied)

	def prune(self, annotation: str) -> bool:
		return annotations.prune(annotation, self.mark_names, self.element_ids)

	def strip_treatment_entries(self) -> None:
		"""Delete the entries, and unlink the one a mark of another procedure still uses."""
		doomed = self.get_unheld("treatment_entry", self.treatment_entries)
		release_photo_links("treatment_entry", doomed)
		delete_documents("Derma Treatment Entry", doomed)
		frappe.db.set_value(
			"Derma Treatment Entry", {"clinical_procedure": self.procedure}, "clinical_procedure", None
		)

	def strip_findings(self) -> None:
		doomed = self.get_unheld("finding", self.findings)
		release_photo_links("finding", doomed)
		delete_documents("Derma Finding", doomed)

	def get_unheld(self, field: str, names: list[str]) -> list[str]:
		"""Of these, the ones no mark points at now that the procedure's own marks are gone.

		A record another visit's mark still depends on is left standing rather than destroyed.
		"""
		if not names:
			return []
		held = set(frappe.get_all("Derma Chart Mark", filters={field: ["in", names]}, pluck=field))
		return [name for name in names if name not in held]


def release_photo_links(field: str, names: list[str]) -> None:
	"""Photos outlive what they were taken for, so they are unlinked rather than deleted."""
	from do_derma import api

	if not names:
		return
	for doctype in ("Derma Photo Set", "Derma Photo"):
		if api._has_field(doctype, field):
			frappe.db.set_value(doctype, {field: ["in", names]}, field, None)


def delete_documents(doctype: str, names: list[str]) -> None:
	for name in names:
		frappe.delete_doc(doctype, name, ignore_permissions=True)
