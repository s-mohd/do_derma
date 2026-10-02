# Derma chart: materials batch as a real object

Status: agreed 2026-10-02.
Branch: `feat/derma-materials-batch`, cut from `feat/derma-chart-redesign`.
Origin: the 2026-09-12 redesign direction (materials keep every editor capability; the batch
becomes an object carrying lot, remaining stock and expiry; an expired lot blocks, short
stock only warns; the expiring-soon window is a Derma Settings value, default 30 days).

## Goal

A clinician sees, on each materials line, which lot they are using, how much of it is left
in this procedure's warehouse, and when it expires. Readiness agrees with the line: an
expired lot blocks completion, a short or soon-expiring lot warns, and the reason is stated
on the line that causes it.

## Decisions

| Topic | Decision |
|---|---|
| Expired lot or batch | Blocks completion (unchanged) |
| Expiring soon | Readiness **warning**, never blocks. Window from Derma Settings, default 30, `0` disables |
| Short stock | Readiness **warning** (was blocking) |
| Short stock measured against | The chosen batch in the procedure's warehouse; an item that is not batch-tracked compares against the item's stock in that warehouse |
| Batch missing on a batch-tracked item | Blocks with no override (unchanged) |
| Dose rows on marks (free-text lot) | Keep lot/expiry checks; expiring-soon warning applies; short stock warns at item level |
| Batch picker | Stays a native `<select>`, clearer option labels |

## Rules (server)

Owner: `do_derma/readiness/inventory.py`.

| Condition | Result | Message |
|---|---|---|
| Expired | blocking | "Product is expired." (unchanged) |
| Expires within `expiring_soon_days` | warning | "Expires in {n} days ({date})." / "Expires today ({date})." |
| Line quantity > available in scope | warning | Batch: "This lot has {available} left; the line uses {needed}." Item: "{available} left in stock; the line uses {needed}." |
| Stock unknown | warning | unchanged |

- `_blocking_messages` loses the "Insufficient available stock." line. The shortage becomes a
  notice beside `_balance_notices`.
- Day arithmetic uses `frappe.utils.date_diff(expiry, today)`: `0` means expires today, `≤
  window` warns, `< 0` is expired.
- `_stock_available_qty(item_code)` (all warehouses) is replaced, for consumable rows, by the
  batch facts below. Dose rows keep an item-level comparison, scoped to the procedure's
  warehouse when one is known.

### Settings

- `Derma Settings` gains `expiring_soon_days` (Int, default 30, label "Expiring soon (days)",
  description "Warn when a lot expires within this many days. 0 turns the warning off."),
  added to `derma_settings.json` next to the readiness fields.
- `do_derma/settings.py::get_readiness_settings()` returns `expiring_soon_days`; a site
  without the field gets 30.

### One owner for batch facts

New `do_derma/consumables/batches.py`:

```python
def get_batch_facts(item_code, batch_no, warehouse, line_qty, window_days, today=None) -> dict:
	# {name, expiry_date, available_qty, line_qty, is_expired, days_to_expiry,
	#  is_expiring_soon, is_short}
```

- `available_qty` comes from ERPNext `get_batch_qty(batch_no=…, warehouse=…)` for a batch, or
  the item's `Bin.actual_qty` in that warehouse otherwise. It is `None` when unknown.
- `is_short` is true only when `available_qty` is known and `line_qty` exceeds it.
- The warehouse is `consumables.items.get_warehouse(owner_doctype, owner_name)`, the same one
  the editor's batch list uses.
- Readiness and the chart payload both call this function.

### Payload

Each consumable row in the procedure payload (`consumables/procedures.py::get_carriers`)
gains `batch` (the facts dict, or `None` when the row has no batch and the item is not
batch-tracked; for a non-batch item the dict carries `available_qty`/`is_short` only) and
`readiness_message` / `readiness_tone` (`"danger" | "caution" | ""`) for that line.

## Editor (`components/consumables/ConsumablesEditor.vue`)

- **Picker:** the native `<select>` stays. Option labels read
  `{batch} · {qty} left · exp {date in user format}`, soonest expiry first (as today).
- **Chosen batch:** the cell shows lot name (bold), a stock pill "{n} left" (`caution` when
  `is_short`), and an expiry pill: date (`neutral`), "in {n} days" (`caution`), "expired
  {date}" (`danger`). Editable rows keep the select beside it as a compact "Change" control;
  read-only rows show the object only.
- **Item without batches:** only the stock pill.
- **Reason on the line:** `readiness_message` renders under the line in its tone.
- Everything else stays: Changed flag, Restore, Reset to template, unit locking, per-line
  errors, loading and saving states.
- Pills use the shared `.chart-pill` tones; no new colours.

## Behaviour change

Sessions that cannot be completed today because of short stock become completable, with a
warning. Under Block enforcement only expired lots, missing batches and missing
product/dose still block.

## Out of scope

- How stock is posted or consumed
- ERPNext batch selection rules (expired and empty batches stay hidden from the picker)
- The completion dialog flow
- Turning free-text dose lots into linked batches

## Testing

Python (`do_derma/tests/test_readiness.py`, `test_consumables.py`):
- an expired product blocks (existing test unchanged)
- short stock warns and does not block (rewrite of the blocking assertion)
- expiring soon: day 30 warns, day 31 does not, today warns, window 0 disables
- a batch with 3 left and a line of 5 warns although the item has plenty in other batches
- warehouse scope: stock in another warehouse does not count
- `get_readiness_settings()` returns `expiring_soon_days`, defaulting to 30
- the payload carries `batch` and `readiness_message` for a consumable row
- full suite diffed against `main`'s baseline

Browser (a batch receipted inside `bench console` and rolled back afterwards):
- fresh, expiring soon, expired and short lines render the right pills and message, light
  and dark
- the hero's warning count and the Review list reflect the new warnings
- a session with only short stock completes under Block enforcement
