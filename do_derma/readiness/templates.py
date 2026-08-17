"""The `Clinical Procedure Template` rows behind a set of marks, fetched once per engine."""

from __future__ import annotations

from typing import Any

import frappe

from do_derma import api


def templates_for_marks(marks: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
	names = [mark.get("procedure_template") for mark in marks if mark.get("procedure_template")]
	if not names:
		return {}
	rows = frappe.get_all(
		"Clinical Procedure Template",
		filters={"name": ["in", names]},
		fields=api._select_existing_fields("Clinical Procedure Template", fields),
	)
	return {row.get("name"): row for row in rows}
