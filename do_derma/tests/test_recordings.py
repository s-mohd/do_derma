from __future__ import annotations

import os
import shutil
import tempfile
import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from do_derma import recordings, voice
from do_derma.tests.test_ai_ops import wav_bytes
from do_derma.tests.test_api import DermaTestHelpers


class TestRecordings(DermaTestHelpers, IntegrationTestCase):
	"""Recordings go to the hospital's storage folder when one is set, else to a private File."""

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("Administrator")
		self.encounter = self._make_encounter(self._make_patient())
		self.folder = tempfile.mkdtemp(prefix="derma-recordings-")
		self.addCleanup(shutil.rmtree, self.folder, True)

	def _settings(self, **values):
		return patch.object(voice, "_setting", side_effect=lambda name, default=None: values.get(name, default))

	def test_storage_folder_keeps_the_recording_by_patient_and_date(self):
		with self._settings(recording_storage_path=self.folder):
			out = recordings.store_recording(self.encounter, wav_bytes(1))
		self.assertEqual(out["stored_in"], "storage")
		expected = os.path.join(self.folder, recordings.safe_name(self.encounter.patient), frappe.utils.nowdate())
		self.assertEqual(os.path.dirname(out["location"]), expected)
		with open(out["location"], "rb") as handle:
			self.assertEqual(handle.read(4), b"RIFF")
		self.assertTrue(frappe.db.exists("Comment", {"reference_name": self.encounter.name, "content": ["like", f"%{out['location']}%"]}))
		self.assertFalse(frappe.db.exists("File", {"attached_to_name": self.encounter.name, "file_name": ["like", "consultation-%"]}))

	def test_without_a_folder_the_recording_is_a_private_file(self):
		with self._settings():
			out = recordings.store_recording(self.encounter, wav_bytes(1))
		self.assertEqual(out["stored_in"], "files")
		self.assertTrue(out["location"].startswith("/private/files/consultation-"))

	def test_only_wav_audio_and_absolute_folders_are_accepted(self):
		with self._settings(recording_storage_path=self.folder), self.assertRaises(frappe.ValidationError):
			recordings.store_recording(self.encounter, b"not audio")
		with self.assertRaises(frappe.ValidationError):
			recordings.validate_storage_root("relative/recordings")

	def test_purge_deletes_only_old_recordings_in_files_and_folder(self):
		with self._settings(recording_storage_path=self.folder):
			old_path = recordings.store_recording(self.encounter, wav_bytes(1))["location"]
			fresh_path = recordings.store_recording(self.encounter, wav_bytes(1))["location"]
		os.utime(old_path, (time.time() - 40 * 86400,) * 2)
		old = frappe.get_doc({"doctype": "File", "file_name": "consultation-1.wav", "content": b"RIFF", "attached_to_doctype": "Patient Encounter", "attached_to_name": self.encounter.name, "is_private": 1}).insert(ignore_permissions=True)
		frappe.db.set_value("File", old.name, "creation", "2020-01-01 00:00:00", update_modified=False)
		fresh = frappe.get_doc({"doctype": "File", "file_name": "consultation-2.wav", "content": b"RIFF", "attached_to_doctype": "Patient Encounter", "attached_to_name": self.encounter.name, "is_private": 1}).insert(ignore_permissions=True)
		with self._settings(recording_storage_path=self.folder, audio_retention_days=30):
			self.assertEqual(recordings.purge_old_audio(), 2)
		self.assertFalse(os.path.exists(old_path))
		self.assertTrue(os.path.exists(fresh_path))
		self.assertFalse(frappe.db.exists("File", old.name))
		self.assertTrue(frappe.db.exists("File", fresh.name))
