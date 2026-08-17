"""Single after_migrate entry point. Safe to re-run on any site."""

import frappe

from do_derma.assessment import ensure_derma_settings_defaults
from do_derma.printing.inject import ensure_assessment_block_in_print_formats
from do_derma.schema import ensure_derma_schema
from do_derma.settings import ensure_readiness_defaults


def after_migrate() -> None:
	# Schema first: the injected print block is inert until the SOAP fields exist.
	ensure_derma_schema()
	# Readiness first: saving the singleton writes 0 for every Check it has never stored,
	# which would hide an unset downgrade flag from the seeder and make the site stricter.
	try:
		ensure_readiness_defaults()
	except Exception:
		frappe.log_error(title="Derma readiness defaults", message=frappe.get_traceback())
	try:
		ensure_derma_settings_defaults()
	except Exception:
		frappe.log_error(title="Derma Settings defaults", message=frappe.get_traceback())
	try:
		ensure_assessment_block_in_print_formats()
	except Exception:
		frappe.log_error(title="Derma print formats", message=frappe.get_traceback())
