"""Single after_migrate entry point. Safe to re-run on any site."""

import frappe

from do_derma.assessment import ensure_derma_settings_defaults
from do_derma.schema import ensure_derma_schema


def after_migrate() -> None:
	ensure_derma_schema()
	try:
		ensure_derma_settings_defaults()
	except Exception:
		frappe.log_error(title="Derma Settings defaults", message=frappe.get_traceback())
