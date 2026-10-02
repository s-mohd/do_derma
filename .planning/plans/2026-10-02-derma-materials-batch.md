# Materials Batch as a Real Object Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each materials line shows its lot, what is left in the procedure's warehouse and its expiry. Readiness blocks on expired lots and warns on short or soon-expiring ones, and states the reason on the line.

**Architecture:** A new `do_derma/consumables/batches.py` is the one owner of batch facts (`get_batch_facts`) and of the per-line notices (`get_line_notices`). Readiness (`readiness/inventory.py`) and the consumables payload (`consumables/marks.py`, `consumables/procedures.py`) both call it, so the line, the hero's warning count and Review cannot disagree. A Derma Settings integer sets the expiring-soon window. The Vue editor renders the facts as pills.

**Tech Stack:** Frappe v16, ERPNext `get_batch_qty`, Python `IntegrationTestCase`, Vue 3.5 SFC, shared `.chart-pill` tones.

**Spec:** `.planning/specs/2026-10-02-derma-materials-batch.md`

## Global Constraints

- Branch `feat/derma-materials-batch` (cut from `feat/derma-chart-redesign`).
- Expired → blocking ("Product is expired.", unchanged). Expiring within window → warning. Short → warning. Missing batch on a batch-tracked item → blocking, no override (unchanged).
- Window: Derma Settings `expiring_soon_days`, Int, default **30**, `0` disables.
- Warnings, exact text: `"Expires in {0} days ({1})."`, `"Expires today ({0})."`, batch `"This lot has {0} left; the line uses {1}."`, item `"{0} left in stock; the line uses {1}."`. Wrap in `_()`, format with `.format()`.
- Short is computed only when the line's stock quantity is known (`is_stock_qty_known`) and available quantity is known.
- Warehouse comes only from `consumables.items.get_warehouse(owner_doctype, owner_name)`. `None` means all warehouses.
- No new colours: line pills use `.chart-pill` with `data-tone` neutral | caution | danger.
- Commits end `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Commands

- Run from `/Users/hameed/Developer/bench-v16`. `--test` takes a **bare method name**.
- Module: `bench --site dermaone.localhost run-tests --module do_derma.tests.<module> 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)\s|Error:"`
- After changing `derma_settings.json`: `bench --site dermaone.localhost migrate`.
- Build after Vue changes: scratchpad `rebuild.sh`. Suite: diff failing names against `main`'s 5.

## Review Focus

1. **A batch used up by an earlier line in the same session.** Two lines on one batch must sum before comparing. Readiness groups by item and lot, so the group's `stock_qty` is the sum. Pinned in Task 3 `test_two_lines_on_one_lot_are_compared_together`.
2. **A unit that does not convert.** No shortage claim, only "Stock balance is not available". Pinned by the existing test `test_a_unit_the_item_does_not_convert_is_uncheckable_rather_than_blocking`, kept green in Task 3.
3. **A read-only, submitted procedure whose batch has since run out or expired.** The line still shows its lot, expiry and the expired pill. Pinned in Task 4 `test_payload_describes_an_expired_batch_with_no_stock`.
4. **A site that never saved the new field.** The window reads 30, not 0 (which would silently disable the warning). Pinned in Task 1 `test_an_unwritten_window_reads_as_thirty`.
5. **A session with only short stock under Block enforcement** completes. Pinned in Task 3 `test_short_stock_alone_does_not_block_completion`.

---

## File structure

| File | Change |
|---|---|
| `do_derma/do_derma/doctype/derma_settings/derma_settings.json` | `expiring_soon_days` field |
| `do_derma/settings.py` | `EXPIRING_SOON_FIELD`, default, returned by `get_readiness_settings`, seeded by `ensure_readiness_defaults` |
| `do_derma/consumables/batches.py` | **New.** `get_available_qty`, `get_batch_facts`, `get_line_notices`, `annotate_rows` |
| `do_derma/readiness/inventory.py` | Warehouse on groups; facts-based status; short becomes a warning; expiring-soon warning |
| `do_derma/readiness/session.py` | Pass the window to `inventory.build` |
| `do_derma/consumables/marks.py`, `do_derma/consumables/procedures.py` | `annotate_rows` in `hydrate` and `get_payload` |
| `do_derma/public/js/chart/components/consumables/ConsumablesEditor.vue` | Batch object pills, line notice, option labels |
| `do_derma/tests/test_settings.py`, `test_consumables.py` | Tests |

---

### Task 1: The expiring-soon window setting

**Files:** `derma_settings.json`; `settings.py`; `tests/test_settings.py`

**Interfaces:** Produces `settings.EXPIRING_SOON_FIELD = "expiring_soon_days"`, `settings.DEFAULT_EXPIRING_SOON_DAYS = 30`, and `get_readiness_settings()["expiring_soon_days"] -> int`.

- [ ] **Step 1: Failing tests** (append to `TestReadinessSettings`, tabs):

```python
	def test_the_window_defaults_to_thirty_without_its_field(self):
		doc = FakeSettings({"blocker_enforcement": "Warn"})
		with patch.object(settings, "get_settings_doc", return_value=doc):
			self.assertEqual(settings.get_readiness_settings()["expiring_soon_days"], 30)

	def test_an_unwritten_window_reads_as_thirty(self):
		doc = FakeSettings({"blocker_enforcement": "Warn", "expiring_soon_days": None})
		with patch.object(settings, "get_settings_doc", return_value=doc):
			self.assertEqual(settings.get_readiness_settings()["expiring_soon_days"], 30)

	def test_a_clinic_window_of_zero_turns_the_warning_off(self):
		doc = FakeSettings({"blocker_enforcement": "Warn", "expiring_soon_days": 0})
		with patch.object(settings, "get_settings_doc", return_value=doc):
			self.assertEqual(settings.get_readiness_settings()["expiring_soon_days"], 0)

	def test_a_site_without_the_settings_doc_still_has_a_window(self):
		with patch.object(settings, "get_settings_doc", return_value=None):
			self.assertEqual(settings.get_readiness_settings()["expiring_soon_days"], 30)
```

Run `test_settings`: all four fail with `KeyError: 'expiring_soon_days'`.

- [ ] **Step 2: Implement**

`settings.py`, next to the other field constants:

```python
EXPIRING_SOON_FIELD = "expiring_soon_days"
DEFAULT_EXPIRING_SOON_DAYS = 30
```

Add this helper above `get_readiness_settings`:

```python
def get_expiring_soon_days(settings) -> int:
	"""Days before expiry that a lot starts to warn; an unwritten field reads as the default."""
	if not settings or not settings.meta.has_field(EXPIRING_SOON_FIELD):
		return DEFAULT_EXPIRING_SOON_DAYS
	value = settings.get(EXPIRING_SOON_FIELD)
	return DEFAULT_EXPIRING_SOON_DAYS if value is None else max(cint(value), 0)
```

In `get_readiness_settings`, add `"expiring_soon_days": get_expiring_soon_days(settings),` to **both** returned dicts. In `ensure_readiness_defaults`, extend the tuple to `((ENFORCEMENT_FIELD, DEFAULT_ENFORCEMENT), (TODO_DOWNGRADE_FIELD, 1), (EXPIRING_SOON_FIELD, DEFAULT_EXPIRING_SOON_DAYS))`.

`derma_settings.json`: in `field_order` insert `"expiring_soon_days"` after `"todo_downgrades_blockers"`. Add to `fields` after the downgrade field:

```json
  {
   "default": "30",
   "description": "Warn when a lot expires within this many days. 0 turns the warning off.",
   "fieldname": "expiring_soon_days",
   "fieldtype": "Int",
   "label": "Expiring Soon (Days)",
   "non_negative": 1
  },
```

Bump the doctype's `"modified"` timestamp to now (format `2026-10-02 12:00:00.000000`) so migrate picks it up.

- [ ] **Step 3: Migrate and GREEN**

Run `bench --site dermaone.localhost migrate`, then `test_settings`: all pass.

- [ ] **Step 4: Commit**

```bash
git add do_derma/do_derma/doctype/derma_settings/derma_settings.json do_derma/settings.py do_derma/tests/test_settings.py
git commit -m "feat(settings): expiring-soon window for materials lots

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Batch facts and line notices

**Files:** Create `do_derma/consumables/batches.py`; test `tests/test_consumables.py` (new class)

**Interfaces:** Produces:
- `get_available_qty(item_code: str, batch_no: str | None, warehouse: str | None) -> float | None`
- `get_batch_facts(item_code, batch_no, warehouse, line_qty: float | None, window_days: int, expiry_date=None, today=None) -> dict` with keys `name, expiry_date, available_qty, line_qty, is_expired, days_to_expiry, is_expiring_soon, is_short`
- `get_line_notices(facts: dict) -> list[dict]`, each `{"message": str, "tone": "danger" | "caution"}`, expired first

- [ ] **Step 1: Failing tests** (append to `test_consumables.py`):

```python
from do_derma.consumables import batches


class TestBatchFacts(ConsumableHelpers, IntegrationTestCase):
	"""One owner for what a lot can tell the line and readiness."""

	def setUp(self):
		self.item = self._make_stock_item(has_batch_no=1)

	def facts(self, days, available=10, line_qty=1, window=30):
		batch = self._make_batch(self.item, expiry_date=add_days(nowdate(), days))
		with patch.object(batches, "get_available_qty", return_value=available):
			return batches.get_batch_facts(self.item, batch, None, line_qty, window)

	def test_day_thirty_is_expiring_soon_and_day_thirty_one_is_not(self):
		self.assertTrue(self.facts(30)["is_expiring_soon"])
		self.assertFalse(self.facts(31)["is_expiring_soon"])

	def test_today_is_expiring_soon_not_expired(self):
		facts = self.facts(0)
		self.assertTrue(facts["is_expiring_soon"])
		self.assertFalse(facts["is_expired"])

	def test_yesterday_is_expired_and_not_expiring_soon(self):
		facts = self.facts(-1)
		self.assertTrue(facts["is_expired"])
		self.assertFalse(facts["is_expiring_soon"])

	def test_a_window_of_zero_never_warns(self):
		self.assertFalse(self.facts(0, window=0)["is_expiring_soon"])

	def test_a_line_above_what_is_left_is_short(self):
		self.assertTrue(self.facts(90, available=3, line_qty=5)["is_short"])
		self.assertFalse(self.facts(90, available=5, line_qty=5)["is_short"])

	def test_unknown_stock_or_quantity_is_never_short(self):
		self.assertFalse(self.facts(90, available=None, line_qty=5)["is_short"])
		self.assertFalse(self.facts(90, available=3, line_qty=None)["is_short"])

	def test_a_free_text_expiry_counts_without_a_batch(self):
		with patch.object(batches, "get_available_qty", return_value=None):
			facts = batches.get_batch_facts(self.item, None, None, 1, 30, expiry_date=add_days(nowdate(), 5))
		self.assertEqual(facts["days_to_expiry"], 5)

	def test_notices_name_the_shortfall_and_the_expiry(self):
		notices = batches.get_line_notices(self.facts(12, available=3, line_qty=5))
		messages = [notice["message"] for notice in notices]
		self.assertIn("Expires in 12 days", messages[0])
		self.assertEqual(messages[1], "This lot has 3 left; the line uses 5.")
		self.assertEqual({notice["tone"] for notice in notices}, {"caution"})

	def test_an_expired_lot_is_a_danger_notice(self):
		notices = batches.get_line_notices(self.facts(-1))
		self.assertEqual(notices[0], {"message": "Product is expired.", "tone": "danger"})

	def test_stock_in_another_warehouse_does_not_count(self):
		batch = self._make_batch(self.item, expiry_date=add_days(nowdate(), 90))
		warehouse = frappe.db.get_value("Warehouse", {"is_group": 0}, "name")
		with patch("erpnext.stock.doctype.batch.batch.get_batch_qty", return_value=0) as get_batch_qty:
			self.assertEqual(batches.get_available_qty(self.item, batch, warehouse), 0)
		get_batch_qty.assert_called_once_with(batch_no=batch, warehouse=warehouse)
```

Run `test_consumables`: the new class errors with `ImportError` / `AttributeError`.

- [ ] **Step 2: Implement `do_derma/consumables/batches.py`**

```python
from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import date_diff, flt, formatdate, getdate, nowdate

from do_derma import api


def get_available_qty(item_code: str | None, batch_no: str | None, warehouse: str | None) -> float | None:
	"""What is left of the lot, or of the item when it has no batch, where the line consumes."""
	if not item_code:
		return None
	if batch_no:
		if not api._has_doctype("Batch"):
			return None
		from erpnext.stock.doctype.batch.batch import get_batch_qty

		if warehouse:
			return flt(get_batch_qty(batch_no=batch_no, warehouse=warehouse))
		return flt(sum(flt(row.get("qty")) for row in get_batch_qty(batch_no=batch_no) or []))
	if not api._has_doctype("Bin"):
		return None
	filters = {"item_code": item_code, **({"warehouse": warehouse} if warehouse else {})}
	rows = frappe.get_all("Bin", filters=filters, pluck="actual_qty")
	return flt(sum(flt(qty) for qty in rows)) if rows else None


def get_batch_facts(
	item_code: str | None,
	batch_no: str | None,
	warehouse: str | None,
	line_qty: float | None,
	window_days: int,
	expiry_date: Any = None,
	today: Any = None,
) -> dict[str, Any]:
	"""Lot, stock left and expiry for one line, judged against the expiring-soon window."""
	if batch_no and api._has_doctype("Batch"):
		expiry_date = frappe.db.get_value("Batch", batch_no, "expiry_date") or expiry_date
	days = date_diff(getdate(expiry_date), getdate(today or nowdate())) if expiry_date else None
	available = get_available_qty(item_code, batch_no, warehouse)
	return {
		"name": batch_no or "",
		"expiry_date": str(expiry_date) if expiry_date else "",
		"available_qty": available,
		"line_qty": line_qty,
		"is_expired": days is not None and days < 0,
		"days_to_expiry": days,
		"is_expiring_soon": days is not None and 0 <= days <= window_days and window_days > 0,
		"is_short": available is not None and line_qty is not None and flt(line_qty) > flt(available),
	}


def get_line_notices(facts: dict[str, Any]) -> list[dict[str, str]]:
	"""What the line says about its lot, the expired notice first."""
	notices = []
	expiry = formatdate(facts["expiry_date"]) if facts.get("expiry_date") else ""
	if facts.get("is_expired"):
		notices.append({"message": _("Product is expired."), "tone": "danger"})
	elif facts.get("is_expiring_soon"):
		days = facts["days_to_expiry"]
		message = _("Expires today ({0}).").format(expiry) if days == 0 else _("Expires in {0} days ({1}).").format(days, expiry)
		notices.append({"message": message, "tone": "caution"})
	if facts.get("is_short"):
		left, needed = _quantity(facts["available_qty"]), _quantity(facts["line_qty"])
		message = (
			_("This lot has {0} left; the line uses {1}.").format(left, needed)
			if facts.get("name")
			else _("{0} left in stock; the line uses {1}.").format(left, needed)
		)
		notices.append({"message": message, "tone": "caution"})
	return notices


def _quantity(value: Any) -> str:
	number = flt(value)
	return str(int(number)) if number == int(number) else f"{number:g}"
```

- [ ] **Step 3: GREEN**

Run `test_consumables`: the new class passes, and the rest of the module is unchanged.

- [ ] **Step 4: Commit**

```bash
git add do_derma/consumables/batches.py do_derma/tests/test_consumables.py
git commit -m "feat(consumables): one owner for a lot's stock, expiry and line notices

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Readiness uses the facts; short stock warns

**Files:** `readiness/inventory.py`; `readiness/session.py`; `tests/test_consumables.py`

**Interfaces:** Consumes Task 2. Changes `inventory.build(marks, procedures=None, expiring_soon_days=30)`.

- [ ] **Step 1: Rewrite and add tests**

In `test_consumables.py`, replace `test_a_quantity_greater_than_the_available_balance_blocks` with:

```python
	def test_a_quantity_greater_than_the_available_balance_warns(self):
		with patch.object(batches, "get_available_qty", return_value=1):
			rows = inventory.build([self._mark_with([self._line(self.item, qty=4)])])

		self.assertFalse(rows[0]["blocking"])
		self.assertEqual(rows[0]["status"], "warning")
		self.assertIn("1 left in stock; the line uses 4.", rows[0]["message"])
```

In `test_a_unit_the_item_does_not_convert_is_uncheckable_rather_than_blocking` and `test_nothing_raises_when_the_stock_doctypes_are_absent`, change the patch target from `patch.object(inventory, "_stock_available_qty", …)` to `patch.object(batches, "get_available_qty", …)`.

Add:

```python
	def test_a_short_lot_warns_though_other_lots_have_plenty(self):
		batched = self._make_stock_item(has_batch_no=1)
		lot = self._make_batch(batched, expiry_date=add_days(nowdate(), 90))
		with patch.object(batches, "get_available_qty", side_effect=lambda item, batch, warehouse: 3 if batch == lot else 100):
			rows = inventory.build([self._mark_with([self._line(batched, qty=5, batch_no=lot)])])

		self.assertFalse(rows[0]["blocking"])
		self.assertIn("This lot has 3 left; the line uses 5.", rows[0]["message"])

	def test_two_lines_on_one_lot_are_compared_together(self):
		batched = self._make_stock_item(has_batch_no=1)
		lot = self._make_batch(batched, expiry_date=add_days(nowdate(), 90))
		lines = [self._line(batched, qty=2, batch_no=lot), self._line(batched, qty=2, batch_no=lot)]
		with patch.object(batches, "get_available_qty", return_value=3):
			rows = inventory.build([self._mark_with(lines)])

		self.assertIn("the line uses 4", rows[0]["message"])

	def test_an_expiring_lot_warns_within_the_window(self):
		batched = self._make_stock_item(has_batch_no=1)
		lot = self._make_batch(batched, expiry_date=add_days(nowdate(), 10))
		with patch.object(batches, "get_available_qty", return_value=50):
			rows = inventory.build([self._mark_with([self._line(batched, batch_no=lot)])], expiring_soon_days=30)
			quiet = inventory.build([self._mark_with([self._line(batched, batch_no=lot)])], expiring_soon_days=0)

		self.assertEqual(rows[0]["status"], "warning")
		self.assertIn("Expires in 10 days", rows[0]["message"])
		self.assertEqual(quiet[0]["status"], "ready")

	def test_short_stock_alone_does_not_block_completion(self):
		from do_derma.readiness.session import is_completion_blocked

		with patch.object(batches, "get_available_qty", return_value=1):
			rows = inventory.build([self._mark_with([self._line(self.item, qty=4)])])

		self.assertFalse(is_completion_blocked({"blockers": [row for row in rows if row["blocking"]], "enforcement": "Block"}))
```

Run `test_consumables` and `test_readiness`. Expected: the rewritten test and the four new ones fail (blocking True, "Insufficient", `TypeError` on `expiring_soon_days`).

- [ ] **Step 2: Implement in `inventory.py`**

1. Import: `from do_derma.consumables import batches` and `from do_derma.consumables.items import get_warehouse`.
2. `build(marks, procedures=None, expiring_soon_days: int = 30)`: pass `expiring_soon_days` into `_resolve_row_status(row, expiring_soon_days)`.
3. `_new_group`: add `"warehouse": None,` to the dict.
4. `_record_contribution(row, carrier, contributor, carrier_field)`: after appending the name, add:

```python
	if row["warehouse"] is None and name:
		doctype = "Clinical Procedure" if carrier_field == PROCEDURE_CARRIERS else "Derma Chart Mark"
		row["warehouse"] = get_warehouse(doctype, name) or ""
```

5. Replace `_resolve_row_status` with:

```python
def _resolve_row_status(row: dict[str, Any], expiring_soon_days: int = 30) -> dict[str, Any]:
	"""The same row, saying what is missing and whether that blocks."""
	line_qty = flt(row.get("stock_qty")) if row.get("is_stock_qty_known") and row.get("stock_qty") else None
	facts = batches.get_batch_facts(
		row.get("product_item"),
		row.get("lot_no") if CONSUMABLE_CONTRIBUTOR in row["contributors"] else None,
		row.get("warehouse") or None,
		line_qty,
		expiring_soon_days,
		expiry_date=row.get("expiry_date") or None,
	)
	blockers = _blocking_messages(row)
	warnings = [notice["message"] for notice in batches.get_line_notices(facts) if notice["tone"] == "caution"]
	messages = blockers + warnings + _balance_notices(row, facts["available_qty"])
	return {
		**row,
		"available_qty": facts["available_qty"],
		"blocking": bool(blockers),
		"is_hard_blocking": _is_batch_missing(row),
		"status": "blocked" if blockers else ("warning" if messages else "ready"),
		"severity": "high" if blockers else ("medium" if messages else "low"),
		"message": " ".join(messages) if messages else _("Ready for product consumption review."),
	}
```

6. `_blocking_messages(row)`: drop the `available_qty` parameter and delete the `_is_balance_comparable(...)` / "Insufficient available stock." lines. Delete `_is_balance_comparable` and `_stock_available_qty` (now unused; grep confirms).
7. `readiness/session.py`: `inventory.build(marks, procedures, expiring_soon_days=settings["expiring_soon_days"])`. The `settings = get_readiness_settings()` line already exists above it.

- [ ] **Step 3: GREEN**

Run `test_consumables`, `test_readiness`, `test_settings`. All pass except the known intermittent baseline `test_an_inventory_row_with_no_product_name_still_names_its_item` (compare with `main` if it fails).

- [ ] **Step 4: Commit**

```bash
git add do_derma/readiness/inventory.py do_derma/readiness/session.py do_derma/tests/test_consumables.py
git commit -m "feat(readiness): short stock warns against the chosen lot; expiring lots warn

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Facts on each consumable row in the payload

**Files:** `consumables/batches.py` (add `annotate_rows`); `consumables/marks.py`; `consumables/procedures.py`; `tests/test_consumables.py`

**Interfaces:** Produces `batches.annotate_rows(rows, owner_doctype, owner_name, window_days) -> None`. Each row gains `batch` (facts dict, or `None` when the row has no item), `readiness_message: str` and `readiness_tone: "danger" | "caution" | ""`.

- [ ] **Step 1: Failing tests**

```python
class TestConsumablePayloadBatch(ConsumableHelpers, IntegrationTestCase):
	"""The editor reads the same facts readiness does."""

	def test_payload_describes_an_expired_batch_with_no_stock(self):
		batched = self._make_stock_item(has_batch_no=1)
		lot = self._make_batch(batched, expiry_date=add_days(nowdate(), -3))
		rows = [{"item_code": batched, "qty": 1, "conversion_factor": 1, "batch_no": lot}]
		with patch.object(batches, "get_available_qty", return_value=0):
			batches.annotate_rows(rows, "Clinical Procedure", None, 30)

		self.assertEqual(rows[0]["batch"]["name"], lot)
		self.assertTrue(rows[0]["batch"]["is_expired"])
		self.assertEqual(rows[0]["readiness_tone"], "danger")
		self.assertEqual(rows[0]["readiness_message"], "Product is expired. This lot has 0 left; the line uses 1.")

	def test_a_healthy_line_carries_facts_and_no_message(self):
		rows = [{"item_code": self._make_stock_item(), "qty": 1, "conversion_factor": 1}]
		with patch.object(batches, "get_available_qty", return_value=10):
			batches.annotate_rows(rows, "Clinical Procedure", None, 30)

		self.assertEqual(rows[0]["batch"]["available_qty"], 10)
		self.assertEqual((rows[0]["readiness_message"], rows[0]["readiness_tone"]), ("", ""))

```

Add to the existing `TestProcedureOwnedConsumables` class (it builds a real procedure in `setUp`):

```python
	def test_payload_lines_carry_batch_facts(self):
		api.save_consumables("Clinical Procedure", self.procedure.name, [{"item_code": self.item, "qty": 4}])

		line = self._payload_procedure()["consumables"][0]
		self.assertIn("batch", line)
		self.assertIn(line["readiness_tone"], {"", "caution", "danger"})

	def test_a_save_answers_with_batch_facts(self):
		result = api.save_consumables("Clinical Procedure", self.procedure.name, [{"item_code": self.item, "qty": 4}])

		self.assertIn("batch", result["consumables"][0])
```

Run `test_consumables`: expected `AttributeError: … annotate_rows` for the first class and `KeyError`/`AssertionError` on `batch` for the two payload tests.

- [ ] **Step 2: Implement**

Append to `batches.py`:

```python
def annotate_rows(rows: list[dict[str, Any]], owner_doctype: str, owner_name: str | None, window_days: int) -> None:
	"""Attach each line's lot facts and its worst notice, the shape the editor renders."""
	from do_derma.consumables.items import get_warehouse

	warehouse = get_warehouse(owner_doctype, owner_name)
	for row in rows or []:
		if not row.get("item_code"):
			row.update(batch=None, readiness_message="", readiness_tone="")
			continue
		factor = flt(row.get("conversion_factor"))
		line_qty = flt(row.get("qty")) * factor if factor else None
		facts = get_batch_facts(row["item_code"], row.get("batch_no") or None, warehouse, line_qty, window_days)
		notices = get_line_notices(facts)
		tones = {notice["tone"] for notice in notices}
		row["batch"] = facts
		row["readiness_message"] = " ".join(notice["message"] for notice in notices)
		row["readiness_tone"] = "danger" if "danger" in tones else ("caution" if tones else "")
```

`marks.py`: import `from do_derma.consumables import batches` and `from do_derma.settings import get_readiness_settings`. In `hydrate`, read `window = get_readiness_settings()["expiring_soon_days"]` once before the loop, and after setting `mark["consumables"]` call `batches.annotate_rows(mark["consumables"], "Derma Chart Mark", name, window)`. In `get_payload`, annotate `compared["consumables"]` with `("Derma Chart Mark", mark_doc.name, …)` before returning.

`procedures.py`: same in `hydrate` (`"Clinical Procedure", row["name"]`) and in `get_payload` (`"Clinical Procedure", procedure_doc.name`).

- [ ] **Step 3: GREEN**

Run `test_consumables`, `test_api`, `test_encounter_tabs`: no new failures.

- [ ] **Step 4: Commit**

```bash
git add do_derma/consumables do_derma/tests/test_consumables.py
git commit -m "feat(consumables): each materials line carries its lot facts and notice

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: The batch on the line (editor)

**Files:** `components/consumables/ConsumablesEditor.vue`

**Interfaces:** Consumes the row fields from Task 4.

- [ ] **Step 1: Option labels**

Replace `batchLabel`:

```js
function batchLabel(batch) {
  const expiry = batch.expiry_date ? ` · ${__("exp")} ${formatDate(batch.expiry_date)}` : ""
  return `${batch.name} · ${__("{0} left").replace("{0}", batch.qty)}${expiry}`
}

function formatDate(value) {
  return window.frappe?.datetime?.str_to_user?.(value) || value
}
```

- [ ] **Step 2: The batch object in the cell**

Inside the batch `<td>`, before the existing `<select>`, add:

```vue
            <div v-if="row.batch && (row.batch.name || row.batch.available_qty !== null)" class="consumable-batch" data-test="consumable-batch-facts">
              <b v-if="row.batch.name">{{ row.batch.name }}</b>
              <span
                v-if="row.batch.available_qty !== null"
                class="chart-pill"
                :data-tone="row.batch.is_short ? 'caution' : 'neutral'"
                data-test="consumable-batch-stock"
              >{{ __("{0} left").replace("{0}", row.batch.available_qty) }}</span>
              <span
                v-if="row.batch.expiry_date"
                class="chart-pill"
                :data-tone="expiryTone(row.batch)"
                data-test="consumable-batch-expiry"
              >{{ expiryLabel(row.batch) }}</span>
            </div>
```

Then give the existing `<select>` the class `consumable-select consumable-change`. Change its first option to `{{ row.batch_no ? __("Change lot") : __("Pick a batch") }}`, and change the read-only `<span v-else>{{ row.batch_no || "-" }}</span>` to `<span v-else-if="!row.batch?.name">{{ row.batch_no || "-" }}</span>`.

After the row's `</tr>`, before the error row, add the notice row:

```vue
        <tr v-if="row.readiness_message" class="consumable-notice-row">
          <td :colspan="readOnly ? 4 : 5">
            <span class="chart-pill" :data-tone="row.readiness_tone" data-test="consumable-notice">{{ row.readiness_message }}</span>
          </td>
        </tr>
```

Add the helpers:

```js
function expiryTone(batch) {
  if (batch.is_expired) return "danger"
  return batch.is_expiring_soon ? "caution" : "neutral"
}

function expiryLabel(batch) {
  if (batch.is_expired) return __("expired {0}").replace("{0}", formatDate(batch.expiry_date))
  if (batch.is_expiring_soon) {
    return batch.days_to_expiry === 0 ? __("expires today") : __("in {0} days").replace("{0}", batch.days_to_expiry)
  }
  return formatDate(batch.expiry_date)
}
```

Scoped styles:

```css
.consumable-batch {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.consumable-notice-row td {
  padding-top: 0;
  border-top: 0;
}

.consumable-notice-row .chart-pill {
  white-space: normal;
}
```

- [ ] **Step 3: Unsaved rows**

New or edited rows have no `batch` until the save answers with the payload, which Task 4 annotates. Check that `commitField` / save replaces rows from the response (it already swaps state from `get_payload`). If it only patches fields, leave `row.batch` as it was until the save returns.

- [ ] **Step 4: Build and browser-check**

Build, open the draft chart, Procedures → a procedure's Materials. Set four lines' `batch` facts by injecting into the component state (as in 2b/2c checks): fresh (`available_qty: 40`, expiry +200 days), expiring (`days_to_expiry: 12`, `is_expiring_soon`), expired (`is_expired`), short (`is_short`, 3 left of 5). For each, confirm the pills, tones and notice text in light and dark (`data-theme`). Then add a real material without injection and confirm the save response renders a `batch` object for it (the item's stock pill).

- [ ] **Step 5: Commit**

```bash
git add do_derma/public/js/chart/components/consumables/ConsumablesEditor.vue
git commit -m "feat(materials): the lot on each line, with stock, expiry and its notice

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Hero, Review and suite

- [ ] **Step 1:** With a session whose readiness carries one expiring-soon warning (inject `data.readiness` as in 2b), confirm the hero reads "1 warning(s)" in caution tone, no tab dot, and Review lists the item.
- [ ] **Step 2:** Run `do_derma.tests.test_chart_theme` (no hex or colour regressions from the editor) and the full suite; diff against `main`'s 5 baseline failures. Expected: none new.
- [ ] **Step 3:** If either step needed a fix, commit it as `fix(materials): …`.
