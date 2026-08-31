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
ENFORCEMENT_WARN = "Warn"
ENFORCEMENT_BLOCK = "Block"
ENFORCEMENT_MODES = (ENFORCEMENT_WARN, ENFORCEMENT_BLOCK)
# Today's behaviour: blockers are advisory and an open ToDo clears a follow-up one.
DEFAULT_ENFORCEMENT = ENFORCEMENT_WARN
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
	downgrade = settings.get(TODO_DOWNGRADE_FIELD) if settings.meta.has_field(TODO_DOWNGRADE_FIELD) else None
	return {
		"enforcement": mode if mode in ENFORCEMENT_MODES else DEFAULT_ENFORCEMENT,
		# A single stores nothing for a field until something writes it, and an unwritten
		# flag must read as today's behaviour rather than as off.
		"todo_downgrades_blockers": DEFAULT_TODO_DOWNGRADE if downgrade is None else bool(cint(downgrade)),
		"is_configurable": True,
	}


def ensure_readiness_defaults() -> None:
	"""Write the completion defaults a site upgrading into these fields has never stored,
	so the desk form shows the mode the server applies. Never overwrites a clinic's edit."""
	if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
		return

	meta = frappe.get_meta(SETTINGS_DOCTYPE)
	for fieldname, default in ((ENFORCEMENT_FIELD, DEFAULT_ENFORCEMENT), (TODO_DOWNGRADE_FIELD, 1)):
		if not meta.has_field(fieldname):
			continue
		if frappe.db.get_single_value(SETTINGS_DOCTYPE, fieldname) is None:
			frappe.db.set_single_value(SETTINGS_DOCTYPE, fieldname, default)
	frappe.clear_cache(doctype=SETTINGS_DOCTYPE)


def get_feature_toggles() -> dict[str, bool]:
	"""Every toggle, defaulting off — an unreadable singleton hides the controls."""
	settings = get_settings_doc()
	if not settings:
		return dict.fromkeys(FEATURE_TOGGLES, False)
	return {name: bool(cint(settings.get(name))) for name in FEATURE_TOGGLES}
