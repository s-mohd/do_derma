"""Derma Settings reads. One owner for how the singleton is fetched and degraded."""

import frappe
from frappe import _
from frappe.utils import cint

SETTINGS_DOCTYPE = "Derma Settings"

# Controls whose integration is unfinished. Off means the control does not render;
# the handler behind it is left in place.
FEATURE_TOGGLES = (
	"enable_whatsapp_consent",
	"enable_lab_cases",
	"enable_billing_sync",
)


def get_settings_doc():
	"""The singleton, or None on a site that lacks it or cannot read it."""
	if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
		return None
	try:
		return frappe.get_cached_doc(SETTINGS_DOCTYPE)
	except Exception:
		frappe.log_error(title=_("Derma Settings unreadable"), message=frappe.get_traceback())
		return None


def get_feature_toggles() -> dict[str, bool]:
	"""Every toggle, defaulting off — an unreadable singleton hides the controls."""
	settings = get_settings_doc()
	if not settings:
		return dict.fromkeys(FEATURE_TOGGLES, False)
	return {name: bool(cint(settings.get(name))) for name in FEATURE_TOGGLES}
