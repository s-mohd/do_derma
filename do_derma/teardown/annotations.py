"""The drawings a deleted mark leaves behind."""

from __future__ import annotations

import json

import frappe
from frappe.utils.file_manager import remove_all

from do_derma.teardown import scene

LINK_HOLDERS = ("Derma Chart Mark", "Derma Treatment Entry", "Derma Finding")


def prune(annotation: str, mark_names: set[str], element_ids: set[str]) -> bool:
	"""Cut those marks out of one shared drawing.

	True when nothing a practitioner drew is left, which is the caller's cue to discard the
	drawing once the records naming it are gone.
	"""
	from do_derma import api

	if not frappe.db.exists("Health Annotation", annotation):
		return False
	stored = frappe.db.get_value("Health Annotation", annotation, "json")
	parsed = api._parse_json(stored, {})
	elements = scene.get_elements(parsed if isinstance(parsed, dict) else {})
	kept = scene.remove_elements(elements, scene.get_owned_ids(elements, mark_names, element_ids))
	if len(kept) != len(elements):
		store(annotation, {**parsed, "elements": kept})
	return not scene.has_substance(kept)


def store(annotation: str, pruned: dict) -> None:
	"""Write the pruned scene back, and drop the snapshots that no longer describe it."""
	frappe.db.set_value("Health Annotation", annotation, "json", json.dumps(pruned))
	clear_preview(annotation)
	frappe.db.set_value("Health Annotation Table", {"annotation": annotation}, "annotation_data", "")


def clear_preview(annotation: str) -> None:
	"""The flattened PNG is an export of the scene as it was, and cannot be redrawn here.

	A missing thumbnail reads as one; a thumbnail showing deleted marks does not. The studio
	writes a fresh one on its next save.
	"""
	remove_all("Health Annotation", annotation, from_delete=True)
	frappe.db.set_value("Health Annotation", annotation, "image", None)


def discard(annotations: list[str]) -> None:
	"""Delete the drawings nothing points at any more, with the rows that anchored them."""
	for annotation in annotations:
		if has_live_links(annotation):
			continue
		frappe.db.delete("Health Annotation Table", {"annotation": annotation})
		frappe.delete_doc("Health Annotation", annotation, ignore_permissions=True)


def has_live_links(annotation: str) -> bool:
	return any(frappe.db.exists(doctype, {"annotation": annotation}) for doctype in LINK_HOLDERS)
