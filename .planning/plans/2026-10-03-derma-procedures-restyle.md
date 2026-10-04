# Procedures Tab Restyle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the derma chart's Procedures tab look like the other chart tabs: compact toolbar, pill counts and attention chips, six quiet columns, click-to-edit price, borderless actions.

**Architecture:** Everything happens in place in `ProcedurePanel.vue` (template, `<script setup>`, `<style scoped>`), plus deleting a few stray rules from `derma_chart.bundle.css`. Behaviour and handlers stay; two filter values are added to back the attention chips. Tests are Python source-reading tests in `test_chart_theme.py`, the pattern the chart already uses, followed by browser checks.

**Tech Stack:** Vue 3 SFC (built by `bench build`), Frappe desk, Python `unittest` via `bench run-tests`.

**Spec:** `.planning/specs/2026-10-03-derma-procedures-restyle.md`

## Global Constraints

- Branch `feat/derma-procedures-restyle` (already created, spec committed in 24e7675).
- Component styles read `--chart-*` tokens only; no hex colours (`test_component_styles_carry_no_hex`).
- `.chart-pill` with `data-tone` neutral | accent | ok | info | caution | danger; `button.chart-pill[aria-pressed="true"]` is the selected look.
- Keep every existing `data-test="procedure-*"` hook (19 today). New hooks may be added.
- Green means OK: the note dot uses `var(--chart-ok)`, never the accent.
- Do not split `ProcedurePanel.vue` (sanctioned large file, CLAUDE.md).
- Teleports only target `#chart-section-actions` with `defer`.
- Repo Python is tab-indented. Lint changed Python with `pipx run ruff check` / `pipx run ruff format`.
- Commit messages: conventional type prefix, ending with
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

**Spec deviation (deliberate):** the price editor is laid out **in the cell's own flow** (it expands under the amount and makes that row taller), not absolutely positioned. `.procedure-table-wrapper` has `overflow-x: auto`, which clips absolutely positioned children, so a floating popover on the last rows would be cut off.

## Commands

Run from `/Users/hameed/Developer/bench-v16`:

- Theme tests: `bench --site dermaone.localhost run-tests --module do_derma.tests.test_chart_theme 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)"`
  (`--test <name>` only works with a bare method name; a run that prints no `Ran` line ran nothing.)
- Build: `bench build --app do_derma`
- Browser login: `bench browse dermaone.localhost --user Administrator` (prints a port-8002 URL with a sid). Open the chart with
  `frappe.route_options = {patient: "PAT-2017-10285", encounter: "HLC-ENC-2026-18379"}; frappe.set_route("derma-chart")`.

## Review Focus

1. **The price button opens and immediately closes.** `openOverrideList` installs a document click handler that closes on any click outside `.override-picker`; the trigger must sit inside that wrapper. Pinned in Task 4 (`test_price_edits_open_from_the_price_cell` asserts the trigger is inside the picker).
2. **An active attention chip disappears when its count drops to zero** (for example, the last missing note gets written while that filter is on), leaving rows hidden behind a filter with no visible chip. Chips render while `count > 0 || isAttentionActive(key)`. Pinned in Task 2.
3. **A chip's count differs from the rows it shows.** Counts and filters must share one predicate. Pinned in Task 1.
4. **Insurance and read-only rows offer price editing.** Only `isEditable(row) && !rowIsInsurance(row)` rows get the picker. Pinned in Task 4.
5. **The price editor on the last row is clipped** by the wrapper's overflow. In-flow layout (above); checked in the browser in Task 7.

---

## File Structure

| File | Change |
|---|---|
| `do_derma/public/js/chart/components/ProcedurePanel.vue` | Template, script and scoped style rewritten piece by piece (Tasks 1–6) |
| `do_derma/public/js/chart/derma_chart.bundle.css` | Delete the stray `.history-search`, `.panel-actions` and uppercase `.procedure-table th` rules (Task 6) |
| `do_derma/tests/test_chart_theme.py` | New `TestProcedurePanelRestyle` class plus helpers; one existing assertion moves (Task 3) |

---

### Task 1: Filter values behind the attention chips

**Files:**
- Modify: `do_derma/public/js/chart/components/ProcedurePanel.vue` (`rowMatchesLabFilter` ~line 690, `rowMatchesBillingFilter` ~line 701, `historyStats` ~line 884, Filters panel selects ~lines 130–158)
- Test: `do_derma/tests/test_chart_theme.py`

**Interfaces:**
- Produces: `rowNeedsBillingReview(row) -> boolean`; billing filter value `"review"`; lab filter value `"follow_up"`; test helpers `PROCEDURE_PANEL`, `get_panel_parts()`, `get_element(markup, opening)`.

- [ ] **Step 1: Add the helpers and failing test** at the end of `test_chart_theme.py`:

```python
PROCEDURE_PANEL = CHART_DIR / "components" / "ProcedurePanel.vue"


def get_panel_parts() -> tuple[str, str, str]:
	"""Template, script and scoped style of the procedure panel."""
	template, rest = PROCEDURE_PANEL.read_text().split("<script setup>", 1)
	script, style = rest.split("<style scoped>", 1)
	return template, script, style


def get_element(markup: str, opening: str) -> str:
	"""Markup from `opening` through its matching closing tag."""
	start = markup.index(opening)
	tag = re.match(r"<([\w-]+)", opening).group(1)
	depth = 0
	for match in re.finditer(rf"<(/?){tag}\b[^>]*?(/?)>", markup[start:]):
		if match.group(2):
			continue
		depth += -1 if match.group(1) else 1
		if depth == 0:
			return markup[start : start + match.end()]
	raise AssertionError(f"{opening} is never closed")


class TestProcedurePanelRestyle(TestCase):
	"""The Procedures tab wears the chart's shared vocabulary (spec 2026-10-03)."""

	def test_attention_filters_reuse_the_counted_predicates(self):
		template, script, _ = get_panel_parts()
		self.assertIn('if (billingFilter.value === "review") return rowNeedsBillingReview(row)', script)
		self.assertIn('if (labFilter.value === "follow_up") return rowNeedsLabFollowUp(row)', script)
		self.assertIn("if (rowNeedsBillingReview(row)) stats.billingReview += 1", script)
		self.assertIn('<option value="review">', template)
		self.assertIn('<option value="follow_up">', template)
```

- [ ] **Step 2: Run the theme tests, confirm the new test fails** (AssertionError on the first `assertIn`).

- [ ] **Step 3: Implement.** In the script, next to `rowNeedsLabFollowUp`:

```js
function rowNeedsBillingReview(row) {
  return hasAnyOverride(row) || rowIsInsurance(row)
}
```

In `rowMatchesLabFilter`, after the `"all"` line:

```js
  if (labFilter.value === "follow_up") return rowNeedsLabFollowUp(row)
```

In `rowMatchesBillingFilter`, after the `"all"` line:

```js
  if (billingFilter.value === "review") return rowNeedsBillingReview(row)
```

In `historyStats`, replace `if (hasAnyOverride(row) || rowIsInsurance(row)) stats.billingReview += 1` with:

```js
    if (rowNeedsBillingReview(row)) stats.billingReview += 1
```

In the template's Lab select, after `<option value="all">`: `<option value="follow_up">{{ __("Follow-up") }}</option>`. In the Billing select, after `<option value="all">`: `<option value="review">{{ __("Needs review") }}</option>`.

- [ ] **Step 4: Run the theme tests, confirm they pass.**

- [ ] **Step 5: Commit**

```bash
git add do_derma/tests/test_chart_theme.py do_derma/public/js/chart/components/ProcedurePanel.vue
git commit -m "feat(procedures): billing review and lab follow-up filters share the counts' predicates"
```

---

### Task 2: Compact toolbar, pill counts, attention chips, Load in the footer

**Files:**
- Modify: `ProcedurePanel.vue` (template lines ~3–182 and the footer ~509–514; script near `historyStats`; scoped style toolbar/summary rules)
- Test: `test_chart_theme.py`

**Interfaces:**
- Consumes: `rowNeedsBillingReview`, filter values from Task 1; `historyStats` keys `missingNotes`, `billingReview`, `labFollowUp`.
- Produces: `statusCounts` (computed `{ [status]: number }`), `ATTENTION_FILTERS`, `attentionChips` (computed `[{ key, count, label }]`), `isAttentionActive(key)`, `toggleAttention(key)`; hooks `data-test="procedure-sort"`, `procedure-attention-note|billing|lab`.

- [ ] **Step 1: Write the failing tests** inside `TestProcedurePanelRestyle`:

```python
	def test_counter_tiles_give_way_to_pill_counts_and_attention_chips(self):
		template, script, style = get_panel_parts()
		self.assertNotIn("summary-tile", template + style)
		self.assertIn("statusCounts[pill.key]", template)
		self.assertIn('v-for="chip in attentionChips"', template)
		for key, filter_name, value in (
			("note", "noteFilter", "missing_note"),
			("billing", "billingFilter", "review"),
			("lab", "labFilter", "follow_up"),
		):
			self.assertRegex(script, rf'{key}: \{{ filter: {filter_name}, value: "{value}"')
		self.assertIn("chip.count > 0 || isAttentionActive(chip.key)", script)

	def test_batch_size_lives_in_the_footer(self):
		template, _, _ = get_panel_parts()
		footer = get_element(template, '<div class="procedure-load-more-row"')
		self.assertIn('v-model.number="rowBatchSize"', footer)
		self.assertEqual(template.count('v-model.number="rowBatchSize"'), 1)
```

- [ ] **Step 2: Run, confirm both fail.**

- [ ] **Step 3: Replace the toolbar's sort label and Load selector.** Replace the `<label class="history-filter-control compact-sort">…</label>` block with:

```html
      <select v-model="sortKey" class="procedure-sort" data-test="procedure-sort" :aria-label="__('Sort')">
        <option value="newest">{{ __("Newest first") }}</option>
        <option value="oldest">{{ __("Oldest first") }}</option>
        <option value="tooth">{{ __("Area") }}</option>
        <option value="procedure">{{ __("Procedure A-Z") }}</option>
        <option value="price_desc">{{ __("Price high-low") }}</option>
        <option value="doctor">{{ __("Doctor") }}</option>
        <option value="status">{{ __("Status") }}</option>
      </select>
```

Change the Filters button's class to `class="ghost small filter-toggle-btn"` and its count to `<span v-if="activeSecondaryFilterCount" class="filter-count">{{ activeSecondaryFilterCount }}</span>`. Delete the `<label class="history-load-selector">…</label>` from `.panel-actions` (the Teleport and the two pills stay).

- [ ] **Step 4: Replace the pills row and delete the tiles.** Replace `<div class="status-filter-row">…</div>` with:

```html
    <div class="status-filter-row">
      <button
        class="chart-pill"
        :aria-pressed="activeStatus === 'all' ? 'true' : 'false'"
        type="button"
        @click="setFilter('all')"
      >
        {{ __("All") }}
        <span v-if="allRows.length" class="pill-count">{{ allRows.length }}</span>
      </button>
      <button
        v-for="pill in statusPills"
        :key="pill.key"
        class="chart-pill"
        :aria-pressed="activeStatus === pill.key ? 'true' : 'false'"
        type="button"
        @click="setFilter(pill.key)"
      >
        {{ pill.label }}
        <span v-if="statusCounts[pill.key]" class="pill-count">{{ statusCounts[pill.key] }}</span>
      </button>
      <div class="attention-chips" aria-live="polite">
        <button
          v-for="chip in attentionChips"
          :key="chip.key"
          type="button"
          class="chart-pill"
          data-tone="caution"
          :data-test="`procedure-attention-${chip.key}`"
          :aria-pressed="isAttentionActive(chip.key) ? 'true' : 'false'"
          @click="toggleAttention(chip.key)"
        >
          {{ chip.label }}
        </button>
      </div>
    </div>
```

Delete the whole `<div class="procedure-history-summary" aria-live="polite">…</div>` block.

- [ ] **Step 5: Move Load into the footer.** Replace the footer block with:

```html
      <div class="procedure-load-more-row" v-if="totalFilteredRows > 0">
        <span class="text-muted">{{ displayedRows }} / {{ totalFilteredRows }} procedures</span>
        <div class="load-controls">
          <button v-if="hasMoreRows" class="ghost small" type="button" @click="loadMoreRows">
            {{ __("Load more") }}
          </button>
          <label class="history-load-selector">
            <span>{{ __("Load") }}</span>
            <select v-model.number="rowBatchSize">
              <option v-for="size in ROW_BATCH_OPTIONS" :key="size" :value="size">{{ size }}</option>
            </select>
          </label>
        </div>
      </div>
```

- [ ] **Step 6: Add the script** directly after `historyStats`:

```js
const ATTENTION_FILTERS = {
  note: { filter: noteFilter, value: "missing_note", stat: "missingNotes", label: __("{0} missing notes") },
  billing: { filter: billingFilter, value: "review", stat: "billingReview", label: __("{0} billing review") },
  lab: { filter: labFilter, value: "follow_up", stat: "labFollowUp", label: __("{0} lab follow-up") },
}

const statusCounts = computed(() => {
  const counts = {}
  for (const row of allRows.value) {
    const status = row?.status || "Draft"
    counts[status] = (counts[status] || 0) + 1
  }
  return counts
})

function isAttentionActive(key) {
  const { filter, value } = ATTENTION_FILTERS[key]
  return filter.value === value
}

// An active chip stays visible at zero so its filter can still be cleared from here.
const attentionChips = computed(() =>
  Object.entries(ATTENTION_FILTERS)
    .filter(([key]) => key !== "lab" || props.enableLabCases)
    .map(([key, config]) => ({ key, count: historyStats.value[config.stat], label: config.label }))
    .filter((chip) => chip.count > 0 || isAttentionActive(chip.key))
    .map((chip) => ({ ...chip, label: chip.label.replace("{0}", chip.count) }))
)

function toggleAttention(key) {
  const { filter, value } = ATTENTION_FILTERS[key]
  filter.value = isAttentionActive(key) ? "all" : value
  loadedRowsCount.value = rowBatchSize.value
}
```

- [ ] **Step 7: Scoped styles.** Delete every rule whose selector names `.compact-sort`, `.procedure-history-summary` or `.summary-tile` (including the copy inside the `@media` block at the end), plus the old `.filter-toggle-btn` rules (base, `.active`, `strong`) and the existing `.status-filter-row` rule (replaced below; never leave two rules for one selector). Rewrite `.history-search` and `.history-filter-control` to `min-height: 34px` and add:

```css
.dental-chart-page .procedure-sort {
  min-height: 34px;
  padding: 0 28px 0 10px;
  border: 1px solid var(--chart-border);
  border-radius: 8px;
  background-color: var(--chart-surface);
  color: var(--chart-text);
  font-size: 13px;
}

.dental-chart-page .filter-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dental-chart-page .filter-toggle-btn.active {
  background: var(--chart-accent-soft);
  color: var(--chart-accent-text);
}

.dental-chart-page .filter-count,
.dental-chart-page .pill-count {
  font-weight: 700;
  opacity: 0.75;
}

.dental-chart-page .status-filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.dental-chart-page .attention-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-left: auto;
}

.dental-chart-page .load-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}
```

Keep the existing `.history-load-selector` rules but change their selector prefix from `.panel-actions .history-load-selector` to `.procedure-load-more-row .history-load-selector`.

- [ ] **Step 8: Run the theme tests, confirm all pass.** Then `bench build --app do_derma` and look at the tab once: one toolbar line; `All 5 · Draft 5` pills; `1 missing notes` chip; clicking the chip leaves one row, clicking again restores five.

- [ ] **Step 9: Commit**

```bash
git add do_derma/tests/test_chart_theme.py do_derma/public/js/chart/components/ProcedurePanel.vue
git commit -m "feat(procedures): pill counts and attention chips replace the counter tiles"
```

---

### Task 3: Notes fold into a borderless actions cluster

**Files:**
- Modify: `ProcedurePanel.vue` (Notes `<th>`/`<td>` ~lines 208, 409–445; `row-actions` ~447–485; colgroup; scoped `.note-*` and `.icon-btn` rules)
- Test: `test_chart_theme.py` (new tests; move the `.note-presence-indicator` assertion in `test_accent_and_ok_green_stay_apart`)

**Interfaces:**
- Consumes: `isEditable(row)`, `getRowNoteRawValue(row)`, `openProcedureNoteDialog(row)`.
- Produces: `noteLabel(row) -> string`; hook `data-test="procedure-note"`; class `.note-dot`.

- [ ] **Step 1: Write failing tests** and move the old assertion. In `test_accent_and_ok_green_stay_apart` replace
`self.assertRegex(procedures, r"\.note-presence-indicator\.present i \{[^}]*var\(--chart-ok\)")` with
`self.assertRegex(procedures, r"\.note-dot \{[^}]*var\(--chart-ok\)")`. Add to `TestProcedurePanelRestyle`:

```python
	def test_notes_live_in_the_actions_cluster(self):
		template, _, style = get_panel_parts()
		self.assertNotIn("note-presence-indicator", template + style)
		self.assertNotRegex(template, r"<th>[^<]*Notes")
		actions = get_element(template, '<td class="row-actions"')
		self.assertIn('data-test="procedure-note"', actions)

	def test_delete_turns_red_only_on_hover(self):
		_, _, style = get_panel_parts()
		self.assertNotRegex(style, r"\.icon-btn\.danger \{")
		self.assertRegex(style, r"\.icon-btn\.danger:hover:not\(:disabled\)[^{]*\{[^}]*var\(--chart-danger-text\)")
```

- [ ] **Step 2: Run, confirm the three affected tests fail.**

- [ ] **Step 3: Template.** Delete `<th>Notes</th>`, `<col class="col-notes" />` and the whole Notes `<td>` (the `isEditable` / `v-else` note templates). Change both `colspan="8"` to `colspan="7"`. Make this the first button inside `<td class="row-actions">`:

```html
                <button
                  v-if="isEditable(row) || getRowNoteRawValue(row)"
                  class="icon-btn"
                  type="button"
                  data-test="procedure-note"
                  :title="noteLabel(row)"
                  :aria-label="noteLabel(row)"
                  @click.stop="openProcedureNoteDialog(row)"
                >
                  <i :class="isEditable(row) ? 'fa-regular fa-note-sticky' : 'fa-regular fa-eye'"></i>
                  <span v-if="getRowNoteRawValue(row)" class="note-dot"></span>
                </button>
```

(The annotate button keeps `fa-pen-to-square`; the note uses `fa-note-sticky` so the two icons differ.)

- [ ] **Step 4: Script**, next to `annotateLabel`:

```js
function noteLabel(row) {
  if (!isEditable(row)) return __("View note")
  return getRowNoteRawValue(row) ? __("Edit note") : __("Add note")
}
```

- [ ] **Step 5: Scoped styles.** Delete `.col-notes`, `.note-cell`, `.note-dialog-btn`, `.note-readonly-cell`, `.note-view-btn` and all `.note-presence-indicator` rules. Replace the `.icon-btn` rules (base, `+ .icon-btn`, `:hover`, `.danger`) with:

```css
.dental-chart-page .procedure-table .icon-btn {
  position: relative;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--chart-muted);
  font-size: 13px;
}

.dental-chart-page .procedure-table .icon-btn:hover:not(:disabled),
.dental-chart-page .procedure-table .icon-btn:focus-visible {
  background: var(--chart-surface-muted);
  color: var(--chart-text);
}

.dental-chart-page .procedure-table .icon-btn.danger:hover:not(:disabled),
.dental-chart-page .procedure-table .icon-btn.danger:focus-visible {
  background: var(--chart-danger-soft);
  color: var(--chart-danger-text);
}

.dental-chart-page .procedure-table .icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.dental-chart-page .procedure-table .note-dot {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--chart-ok);
}
```

Keep `.icon-badge` as it is. Rebalance the colgroup widths so they sum to 100%: status 9%, procedure 21%, tooth 7%, details 27%, price 10%, doctor 13%, actions 13%.

- [ ] **Step 6: Run the theme tests, confirm all pass.**

- [ ] **Step 7: Commit**

```bash
git add do_derma/tests/test_chart_theme.py do_derma/public/js/chart/components/ProcedurePanel.vue
git commit -m "feat(procedures): notes join a borderless actions cluster; delete reddens on hover only"
```

---

### Task 4: Price cell with click-to-edit

**Files:**
- Modify: `ProcedurePanel.vue` (Details `<td>` ~lines 345–401; Price `<td>` ~403–408; scoped `.override-*`, `.price-*`, `.no-charge-*` rules)
- Test: `test_chart_theme.py`

**Interfaces:**
- Consumes (unchanged): `overrideListOpenRow`, `openOverrideList`, `closeOverrideList`, `updatePriceManual`, `setOverrideFromPriceList`, `markNoCharge`, `clearPriceOverride`, `getPriceListOptions`, `isRowSaving`, `computedPrice`, `displayPriceList`, `formatCurrency`, `isNoCharge`, `hasAnyOverride`.
- Produces: hook `data-test="procedure-price"`; classes `.price-cell`, `.price-trigger`, `.override-popover`.

- [ ] **Step 1: Write the failing test:**

```python
	def test_price_edits_open_from_the_price_cell(self):
		template, _, _ = get_panel_parts()
		price = get_element(template, '<td class="price-cell"')
		details = get_element(template, '<div class="details-cell"')
		picker = get_element(price, '<div v-if="isEditable(row) && !rowIsInsurance(row)" class="override-picker"')
		popover = get_element(picker, '<div v-if="overrideListOpenRow === row.name" class="override-popover"')
		self.assertLess(picker.index('data-test="procedure-price"'), picker.index("override-popover"))
		for part in ('class="inline-input"', "no-charge-btn", "override-option"):
			self.assertIn(part, popover)
			self.assertNotIn(part, details)
		self.assertIn('data-test="procedure-row-saving"', price)
		self.assertNotIn("override-label", details)
		self.assertNotIn("no-charge-label", details)
```

- [ ] **Step 2: Run, confirm it fails** (`ValueError: substring not found` for `<td class="price-cell"`).

- [ ] **Step 3: Details cell.** Change the artifact chip's chain so nothing about price stays in Details: delete the `v-else-if="isNoCharge(row)"` span and the `v-else-if="hasAnyOverride(row)"` span, and delete the whole `<div v-if="isEditable(row) && !rowIsInsurance(row)" class="override-picker compact" …>…</div>` block.

- [ ] **Step 4: Price cell.** Replace the Price `<td>` with:

```html
              <td class="price-cell">
                <div v-if="isEditable(row) && !rowIsInsurance(row)" class="override-picker" @keydown.escape="closeOverrideList">
                  <button
                    type="button"
                    class="price-trigger"
                    data-test="procedure-price"
                    :aria-expanded="overrideListOpenRow === row.name ? 'true' : 'false'"
                    :title="__('Change price')"
                    @click.stop="overrideListOpenRow === row.name ? closeOverrideList() : openOverrideList(row)"
                  >
                    {{ formatCurrency(computedPrice(row)) || "—" }}
                  </button>
                  <div v-if="overrideListOpenRow === row.name" class="override-popover">
                    <input
                      type="number"
                      class="inline-input"
                      :placeholder="__('Override')"
                      :value="edits[row.name]?.price ?? row.price_override ?? ''"
                      @change="updatePriceManual(row, $event.target.value); closeOverrideList()"
                    />
                    <button
                      v-for="pl in getPriceListOptions(row)"
                      :key="pl"
                      type="button"
                      class="override-option"
                      @mousedown.prevent="setOverrideFromPriceList(row, pl)"
                    >
                      {{ pl }}
                    </button>
                    <div class="override-popover-footer">
                      <button
                        type="button"
                        class="ghost small no-charge-btn"
                        :title="__('Mark as no charge')"
                        @click.stop="closeOverrideList(); markNoCharge(row)"
                      >
                        {{ __("No charge") }}
                      </button>
                      <button
                        v-if="hasAnyOverride(row)"
                        type="button"
                        class="ghost small reset-btn"
                        :title="__('Clear override')"
                        @click.stop="closeOverrideList(); clearPriceOverride(row)"
                      >
                        {{ __("Reset") }}
                      </button>
                    </div>
                  </div>
                </div>
                <span v-else class="price-amount">{{ formatCurrency(computedPrice(row)) || "—" }}</span>
                <span class="price-meta">{{ displayPriceList(row) }}</span>
                <span v-if="isNoCharge(row)" class="chart-pill" data-tone="neutral">{{ __("No charge") }}</span>
                <span v-else-if="hasAnyOverride(row)" class="chart-pill" data-tone="caution">{{ __("Override") }}</span>
                <span
                  v-if="isRowSaving(row)"
                  class="chart-spinner"
                  role="status"
                  data-test="procedure-row-saving"
                  :aria-label="__('Saving the price')"
                ></span>
              </td>
```

- [ ] **Step 5: Scoped styles.** Delete `.override-picker.compact`, `.override-picker .inline-input`, `.override-dropdown`, `.no-charge-btn` / `.no-charge-btn.active` / `.no-charge-label`, `.override-label`, `.price-readonly`, `.price-list-meta`, `.price-source`, `.price-edit` rules. Replace `.override-picker` and add:

```css
.dental-chart-page .procedure-table .price-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.dental-chart-page .procedure-table .override-picker {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  width: 100%;
}

.dental-chart-page .procedure-table .price-trigger,
.dental-chart-page .procedure-table .price-amount {
  padding: 0;
  border: 0;
  border-bottom: 1px dashed transparent;
  background: transparent;
  color: var(--chart-text);
  font-weight: 600;
}

.dental-chart-page .procedure-table .price-trigger {
  border-bottom-color: var(--chart-border-strong);
  cursor: pointer;
}

.dental-chart-page .procedure-table .price-trigger:hover,
.dental-chart-page .procedure-table .price-trigger[aria-expanded="true"] {
  border-bottom-color: var(--chart-accent);
}

/* In flow, not absolute: the wrapper's overflow-x would clip a floating popover on the last rows. */
.dental-chart-page .procedure-table .override-popover {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  padding: 8px;
  border: 1px solid var(--chart-border);
  border-radius: 10px;
  background: var(--chart-surface);
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.06);
}

.dental-chart-page .procedure-table .override-popover-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-top: 4px;
}
```

Keep `.inline-input`, `.override-option`, `.override-option:hover` and `.price-meta`. The `.price-cell` rule is on the `<td>`; if `display: flex` on a table cell breaks the row's alignment in the browser, move the flex onto an inner `<div class="price-stack">` wrapping the cell's content and update the test's `get_element` opening accordingly.

- [ ] **Step 6: Run the theme tests, confirm all pass.** Build and check in the browser: clicking the price opens the editor and it stays open; Escape and an outside click close it; picking a price list saves and closes.

- [ ] **Step 7: Commit**

```bash
git add do_derma/tests/test_chart_theme.py do_derma/public/js/chart/components/ProcedurePanel.vue
git commit -m "feat(procedures): price edits open from the price cell"
```

---

### Task 5: Six columns, chart-pill chips, quiet header and date rows

**Files:**
- Modify: `ProcedurePanel.vue` (colgroup, `<thead>`, date row, status `<td>`, procedure `<td>`, area `<td>`, details chips, `labCaseStatusClass`; scoped header, date-row, `.detail-chip`, `.consent-badge`, `.pill-*` rules)
- Modify: `derma_chart.bundle.css` (the `.procedure-table th { … text-transform: uppercase; }` block)
- Test: `test_chart_theme.py`

**Interfaces:**
- Consumes: `normalizeTooth`, `formatToothLabel`, `statusTone`.
- Produces: `getProcedureMeta(row) -> string`, `labCaseTone(status) -> string` (replaces `labCaseStatusClass`).

- [ ] **Step 1: Write failing tests:**

```python
	def test_table_has_six_labelled_columns(self):
		template, _, _ = get_panel_parts()
		self.assertEqual(template.count("<col "), 6)
		headers = re.findall(r"<th>(.*?)</th>", template)
		self.assertEqual(len(headers), 6)
		for header in headers:
			self.assertRegex(header, r'^\{\{ __\("[\w ]+"\) \}\}$')
		self.assertEqual(template.count('colspan="6"'), 2)

	def test_row_chips_are_chart_pills(self):
		template, script, style = get_panel_parts()
		self.assertNotIn('class="detail-chip', template)
		self.assertNotIn("consent-badge", template + style)
		self.assertNotIn("labCaseStatusClass", template + script)
		status = get_element(template, '<td class="status-cell"')
		self.assertIn('data-tone="ok"', status)
		self.assertIn('data-tone="danger"', status)
```

- [ ] **Step 2: Run, confirm both fail.**

- [ ] **Step 3: Header and colgroup.**

```html
        <colgroup>
          <col class="col-status" />
          <col class="col-procedure" />
          <col class="col-details" />
          <col class="col-price" />
          <col class="col-doctor" />
          <col class="col-actions" />
        </colgroup>
        <thead>
          <tr>
            <th>{{ __("Status") }}</th>
            <th>{{ __("Procedure") }}</th>
            <th>{{ __("Details") }}</th>
            <th>{{ __("Price") }}</th>
            <th>{{ __("Doctor") }}</th>
            <th>{{ __("Actions") }}</th>
          </tr>
        </thead>
```

Change both `colspan="7"` to `colspan="6"`. Delete the `<td class="tooth-cell">` cell.

- [ ] **Step 4: Status and procedure cells.**

```html
              <td class="status-cell">
                <span class="chart-pill" :data-tone="statusTone(row.status)">
                  {{ row.status || "Draft" }}
                </span>
                <button
                  v-if="row.consents?.length"
                  type="button"
                  class="chart-pill"
                  data-tone="ok"
                  data-test="procedure-consent-badge"
                  @click.stop="emit('open-consents', row)"
                >
                  {{ consentBadgeLabel(row.consents) }}
                </button>
                <button
                  v-else-if="row.consent_required && row.docstatus !== 2"
                  type="button"
                  class="chart-pill"
                  data-tone="danger"
                  data-test="procedure-consent-needed"
                  :disabled="readOnly"
                  @click.stop="emit('new-consent', row)"
                >
                  {{ __("Consent needed") }}
                </button>
              </td>
              <td class="procedure-cell">
                <button
                  v-if="getProcedureName(row)"
                  type="button"
                  class="procedure-open-link"
                  :title="__('Open Clinical Procedure')"
                  @click.stop="openProcedure(row)"
                >
                  {{ row.display_name || row.procedure_template || "-" }}
                </button>
                <span v-else>{{ row.display_name || row.procedure_template || "-" }}</span>
                <span v-if="getProcedureMeta(row)" class="procedure-meta">{{ getProcedureMeta(row) }}</span>
              </td>
```

Script, next to `formatToothLabel`:

```js
function getProcedureMeta(row) {
  const area = normalizeTooth(row?.tooth) ? formatToothLabel(row.tooth) : ""
  return [row?.procedure_code, area].filter(Boolean).join(" · ")
}
```

- [ ] **Step 5: Details chips.** In the details cell, swap each chip's class for `chart-pill` with a tone, keeping every other attribute, icon and `data-test`:

| Chip | New class / tone |
|---|---|
| `derma-detail-chip` (details text) | `class="chart-pill detail-text" data-tone="accent"` |
| surfaces button (`procedure-edit-surfaces`) | `class="chart-pill"` (keep `:class="{ muted: … }"` removed; the label already says "Details") |
| "No details" span | `class="chart-pill detail-empty"` |
| lab case (`procedure-open-lab-case`) | `class="chart-pill" :data-tone="labCaseTone(row.lab_case_status)"` |
| create lab (`procedure-create-lab-case`) | `class="chart-pill" data-tone="caution"` |
| insurance | `class="chart-pill" data-tone="info"` |
| materials (`procedure-toggle-consumables`) | `class="chart-pill"` |
| variables (`procedure-edit-variables`) | `class="chart-pill"` |
| artifacts | `class="chart-pill" data-tone="info"` |

Replace `labCaseStatusClass` in the script with:

```js
function labCaseTone(status) {
  const key = (status || "").toString().toLowerCase()
  if (["delivered", "closed"].includes(key)) return "ok"
  if (["cancelled"].includes(key)) return "danger"
  if (["ready for delivery", "quality checked", "received in clinic", "sent", "in production", "received by lab", "shipped"].includes(key)) return "caution"
  return "neutral"
}
```

- [ ] **Step 6: Scoped styles.** Delete every `.detail-chip*`, `.derma-detail-chip`, `.derma-artifact-chip`, `.lab-suggested`, `.insurance-locked-label`, `.consent-badge*`, `.pill-draft|pending|in-progress|submitted|completed|cancelled`, `.tooth-cell`, `.col-tooth`, `.procedure-code` rule. Set the colgroup widths to status 11%, procedure 23%, details 28%, price 14%, doctor 13%, actions 11%, and lower `.procedure-table`'s `min-width` from 860px to 760px (update its comment to "Below six columns' worth…"). Replace the `th` and date-row rules and add:

```css
.dental-chart-page .procedure-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 8px 12px;
  border-bottom: 1px solid var(--chart-border);
  background: var(--chart-surface-muted);
  color: var(--chart-muted);
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-align: left;
  text-transform: uppercase;
}

.dental-chart-page .procedure-date-row td {
  padding: 10px 12px 6px;
  border-bottom: 1px solid var(--chart-border);
  background: var(--chart-surface);
  color: var(--chart-muted);
  font-size: 12px;
  font-weight: 600;
}

.dental-chart-page .procedure-table .status-cell,
.dental-chart-page .procedure-table .procedure-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.dental-chart-page .procedure-table .procedure-meta {
  color: var(--chart-muted);
  font-size: 12px;
}

.dental-chart-page .procedure-table .details-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-width: 0;
}

.dental-chart-page .procedure-table .detail-text {
  max-width: 100%;
  overflow: hidden;
}

.dental-chart-page .procedure-table .detail-text span {
  overflow: hidden;
  text-overflow: ellipsis;
}

.dental-chart-page .procedure-table .detail-empty {
  color: var(--chart-muted);
}
```

(Same table-cell caveat as Task 4: if `display: flex` on `.status-cell`/`.procedure-cell` `<td>`s misaligns rows, wrap the content in an inner `<div>` and put the flex there.)

In `derma_chart.bundle.css` delete the `.procedure-table th { color: var(--derma-text-secondary-alt); … text-transform: uppercase; }` block (keep the shared `.procedure-table th, .procedure-table td` padding block).

- [ ] **Step 7: Run the theme tests, confirm all pass**, including `test_every_procedure_status_has_a_tone` and `test_component_styles_carry_no_hex`.

- [ ] **Step 8: Commit**

```bash
git add do_derma/tests/test_chart_theme.py do_derma/public/js/chart/components/ProcedurePanel.vue do_derma/public/js/chart/derma_chart.bundle.css
git commit -m "feat(procedures): six quiet columns with chart-pill chips"
```

---

### Task 6: Dead-style sweep with a guard

**Files:**
- Modify: `ProcedurePanel.vue` (scoped style), `derma_chart.bundle.css`
- Test: `test_chart_theme.py`

- [ ] **Step 1: Write the guard test:**

```python
	def test_every_scoped_class_has_a_user(self):
		markup, style = PROCEDURE_PANEL.read_text().split("<style scoped>", 1)
		style = re.sub(r"/\*.*?\*/", "", style, flags=re.S)
		rendered_by_desk = {
			"dental-chart-page",
			"modal-dialog",
			"modal-content",
			"modal-header",
			"modal-footer",
			"frappe-control",
			"ql-editor",
		}
		classes = set(re.findall(r"\.([a-zA-Z][\w-]*)", style)) - rendered_by_desk
		unused = {name for name in classes if not re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", markup)}
		self.assertEqual(unused, set())
```

- [ ] **Step 2: Run it.** It lists every class still styled but no longer rendered (expect leftovers such as `proc-tabs`, `session-badge`, `price-source`, `surface-cell`, `lab-case-cell`, `invoice-btn.complete`'s neighbours…).

- [ ] **Step 3: Delete each listed rule**, including copies inside the trailing `@media` block. Only add a name to `rendered_by_desk` if Frappe itself renders that class into the note dialog; otherwise delete the rule.

- [ ] **Step 4: Bundle CSS.** Confirm no other chart source uses them, then delete the `.history-search`, `.history-search input` and `.panel-actions` blocks from `derma_chart.bundle.css`:

```bash
grep -rn "history-search\|panel-actions" do_derma/public/js/chart --include=*.vue --include=*.jsx --include=*.js | grep -v bundle.js | grep -v ProcedurePanel
```

Expected: no output. If anything shows up, keep that rule.

- [ ] **Step 5: Run the theme tests, confirm all pass.**

- [ ] **Step 6: Commit**

```bash
git add do_derma/tests/test_chart_theme.py do_derma/public/js/chart/components/ProcedurePanel.vue do_derma/public/js/chart/derma_chart.bundle.css
git commit -m "refactor(procedures): drop styles the restyle left without users"
```

---

### Task 7: Verify in the browser and against the suite

- [ ] **Step 1: Build:** `bench build --app do_derma`.
- [ ] **Step 2: Layout at 1280, 1600, 1920 in light, then dark** (desk theme toggle) on HLC-ENC-2026-18379. Screenshot each to `$CLAUDE_JOB_DIR/tmp`. Check: one toolbar line at 1600+; no horizontal page overflow; table scrolls inside its wrapper at 1280 only if needed; no hard-coded light patches under dark.
- [ ] **Step 3: Live actions, each reverted:**
  - type an override price on a draft row → saved (spinner, then the amount and `Override` pill); Reset → pill gone
  - pick a price list in the editor → saves and closes
  - No charge → reason prompt → `No charge` pill; Reset
  - open the editor on the **last** row → fully visible, not clipped
  - note: add a note on the row without one → dot appears and the `missing notes` chip disappears; while that chip's filter is on, the chip stays (count 0) and clicking it restores rows
  - annotate opens the studio; materials chip toggles the consumables row (spans the full width)
  - delete on a throwaway procedure (create one with New Procedure first) → gone
  - status pills and attention chips narrow the rows; Clear restores everything
- [ ] **Step 4: Read-only:** open a submitted encounter. Price shows as text with no button, the note icon shows only on rows with a note (eye icon), no delete, the `Read only` pill shows.
- [ ] **Step 5: Suite.** `bench --site dermaone.localhost run-tests --app do_derma 2>&1 | grep -E "^(Ran |OK|FAILED)|^\s*(FAIL|ERROR)"`. Compare the failing names with the known baseline (the six names in the test-quirks memory); there must be no new names.
- [ ] **Step 6: Lint** `pipx run ruff check do_derma/tests/test_chart_theme.py` and `pipx run ruff format --check do_derma/tests/test_chart_theme.py`; fix and commit (`style(tests): format the procedures restyle tests`) if needed.
- [ ] **Step 7: Report** with before/after screenshots, the suite diff, and anything left open.
