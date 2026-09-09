from frappe.model.document import Document


class DermaAIUsage(Document):
	"""Append-only ledger row; written by do_derma.voice.record_usage, never edited."""
