"""Excalidraw scene arithmetic. No frappe, no database."""

from __future__ import annotations

from typing import Any

TEMPLATE_KINDS = frozenset({"derma_template", "derma_template_image"})
# Layers the studio re-derives on every load, so none of them is work worth keeping.
# Mirrors DERIVED_KINDS and userSignature() in DermaAnnotationStudio.jsx.
DERIVED_KINDS = TEMPLATE_KINDS | frozenset({"derma_template_part", "derma_badge"})
BADGE_KIND = "derma_badge"
HISTORY_PREFIX = "history:"


def get_elements(scene: dict[str, Any] | None) -> list[dict[str, Any]]:
	elements = (scene or {}).get("elements")
	if not isinstance(elements, list):
		return []
	return [element for element in elements if isinstance(element, dict)]


def get_mark_name(element: dict[str, Any]) -> str | None:
	"""The Derma Chart Mark an element belongs to, with the history copy's prefix stripped."""
	custom = element.get("customData") or {}
	name = custom.get("derma_chart_mark") or custom.get("mark_name") or custom.get("source_mark_name")
	if not isinstance(name, str) or not name:
		return None
	return name[len(HISTORY_PREFIX) :] if name.startswith(HISTORY_PREFIX) else name


def get_owned_ids(elements: list[dict[str, Any]], mark_names: set[str], seed_ids: set[str]) -> set[str]:
	"""Every element id the given marks put on the canvas.

	A stamp is several elements naming their mark, a drawn mark is one element the mark itself
	names, and either can carry a label bound to it. The badge layer goes too: it is numbered
	over the surviving marks and the studio renumbers it on the next load.
	"""
	owned = {
		element.get("id")
		for element in elements
		if element.get("id") in seed_ids
		or get_mark_name(element) in mark_names
		or (element.get("customData") or {}).get("kind") == BADGE_KIND
	}
	owned |= {element.get("id") for element in elements if element.get("containerId") in owned}
	for element in elements:
		if element.get("id") not in owned:
			continue
		owned |= {bound.get("id") for bound in element.get("boundElements") or [] if isinstance(bound, dict)}
	return {element_id for element_id in owned if element_id}


def remove_elements(elements: list[dict[str, Any]], owned_ids: set[str]) -> list[dict[str, Any]]:
	"""The scene without those elements, and with no binding left pointing at one."""
	kept = []
	for element in elements:
		if element.get("id") in owned_ids:
			continue
		bound = element.get("boundElements")
		if isinstance(bound, list):
			element = {**element, "boundElements": _keep_bindings(bound, owned_ids)}
		kept.append(element)
	return kept


def has_substance(elements: list[dict[str, Any]]) -> bool:
	"""Whether anything a practitioner drew survives."""
	return any(is_drawn(element) for element in elements)


def is_drawn(element: dict[str, Any]) -> bool:
	if element.get("isDeleted"):
		return False
	custom = element.get("customData") or {}
	return not custom.get("generated_by") and custom.get("kind") not in DERIVED_KINDS


def _keep_bindings(bound: list[Any], owned_ids: set[str]) -> list[Any]:
	return [row for row in bound if not (isinstance(row, dict) and row.get("id") in owned_ids)]
