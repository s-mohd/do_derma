"""Derma Settings reads. One owner for how the singleton is fetched and degraded."""

from typing import Any

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


ENFORCEMENT_FIELD = "blocker_enforcement"
TODO_DOWNGRADE_FIELD = "todo_downgrades_blockers"
ENFORCEMENT_MODES = ("Warn", "Block")
# Today's behaviour: blockers are advisory and an open ToDo clears a follow-up one.
DEFAULT_ENFORCEMENT = "Warn"
DEFAULT_TODO_DOWNGRADE = True


def get_readiness_settings() -> dict[str, Any]:
	"""How session completion is gated, with `is_configurable` saying whether this site
	carries the fields at all. Every fallback is today's behaviour, never stricter."""
	settings = get_settings_doc()
	if not settings or not settings.meta.has_field(ENFORCEMENT_FIELD):
		return {
			"enforcement": DEFAULT_ENFORCEMENT,
			"todo_downgrades_blockers": DEFAULT_TODO_DOWNGRADE,
			"is_configurable": False,
		}

	mode = settings.get(ENFORCEMENT_FIELD)
	return {
		"enforcement": mode if mode in ENFORCEMENT_MODES else DEFAULT_ENFORCEMENT,
		"todo_downgrades_blockers": bool(cint(settings.get(TODO_DOWNGRADE_FIELD)))
		if settings.meta.has_field(TODO_DOWNGRADE_FIELD)
		else DEFAULT_TODO_DOWNGRADE,
		"is_configurable": True,
	}


def get_feature_toggles() -> dict[str, bool]:
	"""Every toggle, defaulting off — an unreadable singleton hides the controls."""
	settings = get_settings_doc()
	if not settings:
		return dict.fromkeys(FEATURE_TOGGLES, False)
	return {name: bool(cint(settings.get(name))) for name in FEATURE_TOGGLES}
