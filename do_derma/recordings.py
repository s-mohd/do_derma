from __future__ import annotations

import os
import re
import time

import frappe
from frappe import _
from frappe.utils import add_days, cint, cstr, now_datetime, nowdate
from frappe.utils.file_manager import save_file

from do_derma import voice

FILE_PREFIX = "consultation-"


def get_storage_root() -> str:
	return cstr(voice._setting("recording_storage_path")).strip()


def validate_storage_root(root: str) -> None:
	"""The folder must be absolute and writable by the server, or recordings would be lost."""
	if not os.path.isabs(root):
		frappe.throw(_("Recording Storage Folder must be an absolute path, e.g. /mnt/recordings."))
	try:
		os.makedirs(root, exist_ok=True)
	except OSError as exc:
		frappe.throw(_("Recording Storage Folder cannot be created: {0}").format(exc))
	if not os.access(root, os.W_OK):
		frappe.throw(_("The server cannot write to the Recording Storage Folder {0}.").format(root))


@frappe.whitelist()
def save_recording(encounter: str) -> dict[str, str]:
	"""POST multipart ``audio`` (WAV). The server decides where the recording is kept."""
	voice.require_enabled()
	encounter_doc = frappe.get_doc("Patient Encounter", encounter)
	if not frappe.has_permission("Patient Encounter", "write", encounter_doc):
		frappe.throw(_("Not permitted to write this encounter."), frappe.PermissionError)
	upload = frappe.request.files.get("audio") if frappe.request else None
	if upload is None:
		frappe.throw(_("No audio file provided."))
	data = upload.read()
	if len(data) > voice.MAX_AUDIO_BYTES:
		frappe.throw(_("Audio too large (max 100 MB)."))
	return store_recording(encounter_doc, data)


def store_recording(encounter_doc, data: bytes) -> dict[str, str]:
	"""With a Recording Storage Folder: <folder>/<patient>/<YYYY-MM-DD>/, noted on the encounter.
	Without one: a private File on the encounter."""
	if data[:4] != b"RIFF":
		frappe.throw(_("Only WAV recordings can be stored."))
	stamp = now_datetime()
	file_name = f"{FILE_PREFIX}{safe_name(encounter_doc.name)}-{stamp:%H%M%S%f}.wav"
	root = get_storage_root()
	if not root:
		file_doc = save_file(file_name, data, "Patient Encounter", encounter_doc.name, is_private=1, decode=False)
		return {"stored_in": "files", "location": file_doc.file_url}
	validate_storage_root(root)
	folder = os.path.join(root, safe_name(encounter_doc.patient), f"{stamp:%Y-%m-%d}")
	os.makedirs(folder, exist_ok=True)
	path = os.path.join(folder, file_name)
	with open(path, "wb") as handle:
		handle.write(data)
	encounter_doc.add_comment("Info", _("Consultation recording stored at {0}").format(path))
	return {"stored_in": "storage", "location": path}


def safe_name(value) -> str:
	"""Patient and encounter names become folder / file names; keep them path-safe."""
	return re.sub(r"[^\w.-]+", "_", cstr(value)).strip("._") or "unknown"


def purge_old_audio() -> int:
	"""Daily job: delete recordings older than Derma Settings.audio_retention_days (0 = keep)."""
	days = cint(voice._setting("audio_retention_days", 0))
	if days <= 0:
		return 0
	files = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Patient Encounter", "file_name": ["like", f"{FILE_PREFIX}%.wav"], "creation": ["<", add_days(nowdate(), -days)]},
		pluck="name",
	)
	for name in files:
		frappe.delete_doc("File", name, ignore_permissions=True, delete_permanently=True)
	return len(files) + purge_storage(days)


def purge_storage(days: int) -> int:
	root = get_storage_root()
	if not root or not os.path.isdir(root):
		return 0
	cutoff = time.time() - days * 86400
	removed = 0
	for folder, _subfolders, names in os.walk(root):
		for name in names:
			path = os.path.join(folder, name)
			if name.startswith(FILE_PREFIX) and name.endswith(".wav") and os.path.getmtime(path) < cutoff:
				os.remove(path)
				removed += 1
	return removed
