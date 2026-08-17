from frappe.model.document import Document

from do_derma.consumables import defaults, snapshot


class DermaChartMark(Document):
	def validate(self):
		self.sync_default_consumables()

	def sync_default_consumables(self) -> None:
		"""Freeze the template's consumables onto the mark, once per template it names.

		A later edit to the template never reaches back: the copy runs when the mark is
		created and again only when the mark is pointed at a different template.
		"""
		if not defaults.has_consumable_doctypes():
			return
		if self.is_new():
			if not self.procedure_template:
				return
		elif not self.has_value_changed("procedure_template"):
			return

		rows = defaults.get_template_consumables(self.procedure_template)
		self.default_consumables_json = snapshot.dump(rows)
		if self.is_new():
			# Whatever the caller already put on the mark is theirs; the defaults join it.
			for row in rows:
				self.append("consumables", row)
			return
		self.set("consumables", rows)
