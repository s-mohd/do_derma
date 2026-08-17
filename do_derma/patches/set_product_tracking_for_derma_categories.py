from __future__ import annotations

import frappe

from do_derma import api

# The categories `readiness.inventory` forced product tracking for by name, before the
# template's own flag became the only trigger. Matched exactly, the way the retired rule
# matched. Seed data for this migration only - nothing reads it afterwards.
RETIRED_TRACKED_CATEGORIES = ("Botox", "Filler")


def execute():
	"""Write the category-name rule's contribution onto each template's own product
	tracking flag, so no clinic loses a lot-number rule when the name rule retires.

	The retired rule read the mark's category before the template's, so a template a
	charted mark named a retiring category for is migrated too.

	Re-runnable: a template already carrying the flag is skipped, and the write does not
	move `modified`.
	"""
	if not (
		api._has_field("Clinical Procedure Template", "custom_derma_product_tracking_required")
		and api._has_field("Clinical Procedure Template", "custom_derma_category")
	):
		return

	for name in _templates_the_category_rule_covered() | _templates_a_mark_named_a_category_for():
		if frappe.db.get_value("Clinical Procedure Template", name, "custom_derma_product_tracking_required"):
			continue
		frappe.db.set_value(
			"Clinical Procedure Template",
			name,
			"custom_derma_product_tracking_required",
			1,
			update_modified=False,
		)


def _templates_the_category_rule_covered() -> set[str]:
	rows = frappe.get_all(
		"Clinical Procedure Template",
		filters={"custom_derma_category": ["is", "set"]},
		fields=["name", "custom_derma_category"],
		limit_page_length=0,
	)
	return {row["name"] for row in rows if _is_retired_category(row.get("custom_derma_category"))}


def _templates_a_mark_named_a_category_for() -> set[str]:
	"""A mark's own category outranked its template's, so a mark can be tracked today
	while the template it points at is in another category entirely."""
	if not api._has_field("Derma Chart Mark", "category"):
		return set()

	rows = frappe.get_all(
		"Derma Chart Mark",
		filters={"category": ["is", "set"], "procedure_template": ["is", "set"]},
		fields=["procedure_template", "category"],
		limit_page_length=0,
	)
	return {row["procedure_template"] for row in rows if _is_retired_category(row.get("category"))}


def _is_retired_category(category: str | None) -> bool:
	"""Exact-case, because the rule this migrates was an exact-case Python `in`. Matching
	in the query instead would widen it to whatever the database collation folds."""
	return (category or "") in RETIRED_TRACKED_CATEGORIES
