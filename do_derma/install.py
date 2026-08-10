"""Single after_migrate entry point. Safe to re-run on any site."""

import frappe

from do_derma.assessment import ensure_derma_settings_defaults
from do_derma.printing.inject import ensure_assessment_block_in_print_formats
from do_derma.schema import ensure_derma_schema


def after_migrate() -> None:
	# Schema first: the injected print block is inert until the SOAP fields exist.
	ensure_derma_schema()
	try:
		ensure_derma_settings_defaults()
	except Exception:
		frappe.log_error(title="Derma Settings defaults", message=frappe.get_traceback())
	try:
		ensure_assessment_block_in_print_formats()
	except Exception:
		frappe.log_error(title="Derma print formats", message=frappe.get_traceback())
