from frappe.model.document import Document


class DermaSettings(Document):
	def validate(self):
		if self.get("recording_storage_path"):
			from do_derma.recordings import validate_storage_root

			self.recording_storage_path = self.recording_storage_path.strip()
			validate_storage_root(self.recording_storage_path)
