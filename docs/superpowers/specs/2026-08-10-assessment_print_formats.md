# Print The Assessment, In The Mode It Was Written In

Date: 2026-08-10
Status: **Implemented & verified** (2026-08-10) — both phases shipped in one pass; see
[Reconciliation](#reconciliation--what-changed-vs-the-plan) and [Verification](#verification).

## Goal

A practitioner who documents a visit in SOAP can print or PDF that encounter and see the
note. Today they cannot: **both `Patient Encounter` print formats on this bench are
hand-written Jinja that render fields by name, so the five custom fields the revamp added are
invisible to them.** The revamp spec closed with this as its first item of follow-up work and
gated the pilot on it:

> printing is deferred by decision, so **the pilot must not print SOAP-documented encounters**
> until both formats gain a block keyed off `custom_derma_assessment_mode`. This is the first
> item of follow-up work, not an optional polish.
> — `2026-08-09-derma_chart_revamp.md`, Open Questions

Constraints carried over verbatim from that spec: the block is **"keyed off the stamped
mode"**, and it lands in **"both formats"** — not in a new do_derma-branded print format that
throws away the clinic's hand-built layout.

## Decisions

- **The print formats call one Jinja global, `derma_assessment_html(doc)`, instead of
  hard-coding fields.** Rationale: the Structured field list is clinic-configurable in
  `Derma Settings` (`assessment.get_structured_fieldnames`), so any field list written into
  HTML drifts the day a clinic edits the list. Trade-off accepted: the printed block cannot be
  restyled per format without editing Python. Rejected: hand-writing the `{% if %}` ladder into
  each format — that is exactly the copy that is already wrong on this bench (see Current
  State), and it duplicates the field list in a third place.

- **The injected block is delimited by markers and re-written on every migrate.** Rationale:
  `after_migrate` already exists (`do_derma/install.py`) and is the repo's answer to "a patch
  runs once and can never repair a drifted site" (`schema.py` docstring). Standard print
  formats are owned by `healthcare`, so a `healthcare` release that edits
  `encounter_print.json` silently reverts our DB row; re-injecting every migrate repairs that
  on the next migrate. Trade-off accepted: do_derma writes to a row another app owns. Rejected:
  a `patches.txt` entry (runs once, cannot repair) and a fixture (would export the whole
  clinic-authored format into this repo).

- **Printing falls back to the other mode rather than printing nothing.** An unstamped legacy
  encounter resolves its mode through `practitioner_default`, which can answer `SOAP` for an
  encounter whose content is entirely Structured. Rendering the resolved mode alone would print
  a blank block over real clinical content. Trade-off accepted: a rare encounter holding
  content in both modes prints both blocks. Rejected: keying strictly on the stamped value —
  every encounter written before the revamp is unstamped, which is most of the 5,000+ on this
  site.

- **Values are escaped in Python, not interpolated raw.** Frappe's print Jinja environment is
  a `SandboxedEnvironment` built with **no `autoescape`** (`frappe/utils/jinja.py:50-56`), so
  `{{ doc.custom_derma_soap_subjective }}` renders practitioner-typed text as live HTML. See
  Security.

- **A format whose tail we cannot prove is ours is skipped and logged, not rewritten.**
  Rationale: the legacy hand-injected block on this site has an opening marker and no closing
  one, so removing it means truncating to end-of-string. Doing that blindly would eat any
  clinic markup sitting after it. Trade-off accepted: such a format keeps its stale block until
  a human intervenes. Rejected: regex-matching the balanced `{% if %}…{% endif %}` — fragile
  against the whitespace-control variants already present in the live copy.

## Current State (verified)

### Two print formats, both hand-written, neither in this repo

`Patient Encounter` has exactly two on `dermaone.localhost`:

| Name | `standard` | `module` | Owner | `print_format_builder` |
|---|---|---|---|---|
| `Encounter Print` | `Yes` | Healthcare | `healthcare` app, `healthcare/healthcare/print_format/encounter_print/encounter_print.json` | `0` |
| `Encounter print (Dr Sadiq)` | `No` | Healthcare | site DB row only, `modified_by: drsadiq.abdulla@gmail.com` | `0` |

Both are `print_format_type: Jinja`, `custom_format: 1`, `disabled: 0`. **Neither exists in
`do_derma`.** `grep -rn "Print Format" --exclude-dir=node_modules .` over this repo returns
nothing — do_derma has never touched printing.

### A hand-injected block already exists on one site, and it is wrong

Both live formats on `dermaone.localhost` already end with a `<!-- do_derma:assessment -->`
block. It is **not reproducible** — it is in no repo, no patch and no fixture, and
`dermaone2.localhost` (the second site on this bench) has neither block:

```
dermaone.localhost   Encounter Print              derma: True   (7008 chars)
dermaone.localhost   Encounter print (Dr Sadiq)   derma: True   (7007 chars)
dermaone2.localhost  Encounter Print              derma: False
dermaone2.localhost  Encounter print (Dr Sadiq)   derma: False
```

Three defects in that hand-injected copy, all of which this work must fix:

1. **The Structured block is not keyed off the mode at all.** It renders whenever any structured
   value is non-empty (`{% set derma_structured_values = [...] | select | list %}`), so a
   SOAP-documented encounter that also carries legacy structured values prints both blocks.
   Only the SOAP block honours `custom_derma_assessment_mode`.
2. **Its structured field list is hard-coded** to seven fieldnames and is already out of sync
   with `assessment.DEFAULT_STRUCTURED_FIELDS`, which has nine — it omits `symptoms` and
   `diagnosis`, the two the encounter form itself shows.
3. **Every value is interpolated raw.** `{{ doc.custom_derma_soap_subjective }}` with no
   escaping, into an environment with autoescape off.

### Standard print formats survive migrate, until the owning app edits its file

Verified empirically on 2026-08-10: `bench --site dermaone.localhost migrate` ran to completion
and both formats still reported `derma: True` afterwards, `Encounter Print` unchanged at 7008
chars. Frappe re-imports a standard doc only when the source file's hash changes, so a DB-level
edit is durable **until `healthcare` ships a new `encounter_print.json`**, at which point it is
silently reverted. This is why the injector belongs in `after_migrate` and not in a patch.

### `assessment.py` already owns everything the renderer needs

`do_derma/assessment.py` (327 lines) exposes exactly the three calls this feature composes:

- `get_assessment_mode(encounter_doc)` (`:118`) — stamped mode wins, else practitioner default,
  else `Structured`.
- `get_layout(mode)` (`:114`) → `get_soap_layout()` (`:107`) / `get_structured_layout()` (`:96`).
  Both drop fields absent from the site's `Patient Encounter` meta, so the layout is already
  schema-defensive.
- `serialize_values(encounter_doc, layout)` (`:135`) — scalars straight through, child tables as
  a list of dicts restricted to the child's own fields.

`get_structured_fieldnames()` (`:88`) reads the clinic-configurable list from `Derma Settings`
and falls back to `DEFAULT_STRUCTURED_FIELDS` (nine fieldnames, `:32`). `soap_is_supported()`
(`:77`) is the guard for a site that has not migrated.

### The four SOAP fields are `Small Text`

`schema.py:38-64` — `custom_derma_soap_{subjective,objective,assessment,plan}` are all
`Small Text` with `depends_on: eval:doc.custom_derma_assessment_mode=='SOAP'`. Plain text with
newlines, not HTML. `custom_derma_assessment_mode` is a read-only `Select`
(`\nStructured\nSOAP`, `schema.py:16`).

Of the Structured defaults, `custom_differential_diagnosis` is the only **Table** field; the
rest are scalars. `symptoms` and `diagnosis` are owned by `healthcare`, the seven
`custom_*` ones by `do_health`.

### The Jinja hook is available and unused

`frappe/utils/jinja.py:245-256` — `get_jinja_hooks()` reads `frappe.get_hooks("jinja")` and
registers each `methods` entry under the function's own `__name__`. `do_derma/hooks.py` (60
lines) declares `app_include_js`, `app_include_css`, `doctype_js`, `fixtures` and
`after_migrate`; it has **no `jinja` key**.

`do_derma/install.py` is 14 lines: `ensure_derma_schema()` then a try/except-wrapped
`ensure_derma_settings_defaults()`.

### The Jinja environment does not autoescape

`frappe/utils/jinja.py:50-56` builds `FrappeSandboxedEnvironment(SandboxedEnvironment)` with
`DebugUndefined` and no `autoescape` argument; Jinja's default is `autoescape=False`. Confirmed
by grep: `autoescape` appears nowhere in `frappe/utils/jinja.py` or `frappe/www/printview.py`.

## Non-Goals

- **No new print format.** do_derma ships no `Print Format` doc of its own; the clinic's two
  hand-built layouts stay theirs. The revamp spec said "both formats gain a block".
- **No print-format builder support.** Formats with `print_format_builder: 1` are skipped —
  their content is `format_data` JSON, not `html`, and neither live format uses it.
- **No letterhead, margin, font or CSS changes.** The block inherits the host format's styling.
- **No PDF-generator work.** `pdf_generator` stays whatever each format has.
- **No backfill of `custom_derma_assessment_mode` onto the ~5,000 unstamped legacy encounters.**
  The other-mode fallback makes them print correctly without a data migration.
- **No chart or bundle changes.** `bench build --app do_derma` is **not** required; no Vue,
  React, CSS or `*.bundle.js` file is touched, and the `data-test` selector contract is
  untouched. No e2e spec is added — printview is outside the chart the suite drives.
- **No new whitelisted endpoint.** Nothing in `api.py` changes.
- **Annotations, photos, marks, prescriptions and consents are not printed.** This block is the
  assessment only. Printing a drawing is a separate feature.
- **`Clinical Procedure` print formats are untouched.**

## Design

One Jinja global renders the assessment from the same layout the chart uses; one idempotent
injector puts a call to it inside every hand-written `Patient Encounter` print format on the
site, delimited by markers so it can be rewritten forever without duplicating. `after_migrate`
runs the injector, so new sites converge and drifted sites repair.

New package `do_derma/printing/` — two files, no re-exports in `__init__.py`.

### 1. The renderer — `do_derma/printing/render.py` *(new)*

```python
MARK_SAFE_FIELDTYPES = {"Text Editor", "HTML Editor", "Markdown Editor"}

def derma_assessment_html(doc) -> Markup:
	"""Jinja global. The assessment block for one encounter, or empty."""
	try:
		encounter = doc if hasattr(doc, "get") else frappe.get_doc("Patient Encounter", doc)
		mode = assessment.get_assessment_mode(encounter)
		block = _render_mode(encounter, mode)
		# A legacy encounter resolves to a mode it holds no content in; never print blank
		# over real content.
		return block or _render_mode(encounter, _other_mode(mode))
	except Exception:
		frappe.log_error(title="Derma assessment print block", message=frappe.get_traceback())
		return Markup("")


def _render_mode(encounter, mode: str) -> Markup:
	rows = [
		(row, _format_value(row, value))
		for row, value in _values_in_layout_order(encounter, mode)
	]
	rendered = [(row, text) for row, text in rows if text]
	if not rendered:
		return Markup("")
	heading = _("Assessment (SOAP)") if mode == assessment.SOAP else _("Assessment")
	...
	return Markup(...)
```

`_format_value` is the only place that escapes, and it escapes by fieldtype:

| Fieldtype | Rendering |
|---|---|
| `Table`, `Table MultiSelect` | Child rows joined with `, `; per row, the `in_list_view` fields, falling back to the row's first non-empty value. Each value escaped. |
| `Check` | `Yes` / `No`, or dropped when `0` |
| `Date`, `Datetime`, `Time` | `frappe.utils.format_value` then escaped |
| `Small Text`, `Text`, `Long Text`, `Data`, `Select`, `Link`, everything else | `escape_html(str(value).strip())`, then `\n` → `<br>` |

`MARK_SAFE_FIELDTYPES` is listed for completeness — none of the current fields use it, and a
clinic that configures a `Text Editor` field into the Structured list gets its stored HTML
through unescaped, which is the same trust boundary the desk form already applies to it.

The broad `except` at the Jinja boundary is deliberate and is the one place this feature
degrades instead of failing loudly: a raise here 500s the printview for *every* encounter,
including ones with no derma content. Everything inside it is schema-defensive by construction
— `get_soap_layout()` returns `[]` when `soap_is_supported()` is false, and
`get_structured_layout()` drops fields missing from the site's meta — so the `except` catches
programming errors, not the absent-field case.

**Must survive the absence of:** `custom_derma_assessment_mode`, all four
`custom_derma_soap_*`, the `Derma Settings` singleton, and any of the nine structured
fieldnames. Each is already handled inside `assessment.py`; `render.py` adds no new schema
assumptions of its own.

### 2. The injector — `do_derma/printing/inject.py` *(new)*

```python
START = "<!-- do_derma:assessment:start -->"
END = "<!-- do_derma:assessment:end -->"
LEGACY = "<!-- do_derma:assessment"          # matches the hand-injected markers too

BLOCK = f"""{START}
{{{{ derma_assessment_html(doc) }}}}
{END}"""


def ensure_assessment_block_in_print_formats() -> dict[str, list[str]]:
	"""Put the assessment block in every hand-written Patient Encounter format."""
	result = {"updated": [], "unchanged": [], "skipped": []}
	for row in frappe.get_all("Print Format", filters=..., fields=[...]):
		...
	return result
```

Selection: `doc_type == "Patient Encounter"`, `disabled == 0`, `print_format_type == "Jinja"`,
`print_format_builder == 0`, and a non-empty `html`.

Per format, in order:

1. `stripped = _without_derma_block(html)` — returns `None` when the tail cannot be proven
   ours, in which case the format is **skipped and logged**, not rewritten.
2. `new_html = stripped.rstrip() + "\n\n" + BLOCK + "\n"`.
3. If `new_html == html` → `unchanged`, **no write at all**, so `modified` does not move and a
   re-run is a true no-op.
4. Else `frappe.db.set_value("Print Format", name, "html", new_html)` — `db.set_value` rather
   than `doc.save()` so a `standard: Yes` row can be repaired without fighting the standard-doc
   guard, matching how the patches in this repo already repair live sites. Then
   `frappe.clear_cache()`.

`_without_derma_block` is the whole risk of this feature and is deliberately conservative:

```python
def _without_derma_block(html: str) -> str | None:
	index = html.find(LEGACY)
	if index == -1:
		return html
	tail = html[index:]
	# Our own block is marker-delimited; the hand-injected one is not, so removing it means
	# truncating to end-of-string. Only do that when nothing foreign lives in the tail.
	foreign = [c for c in re.findall(r"<!--.*?-->", tail, re.S) if not c.startswith(LEGACY)]
	if foreign or END in tail and not tail.rstrip().endswith(END):
		return None
	return html[:index]
```

Both live formats pass this check — their derma block is the tail and contains only the two
derma comments.

### 3. Registration — `do_derma/hooks.py`, `do_derma/install.py`

```python
# hooks.py
jinja = {"methods": ["do_derma.printing.render.derma_assessment_html"]}
```

```python
# install.py — after the two existing calls, guarded the same way
	try:
		ensure_assessment_block_in_print_formats()
	except Exception:
		frappe.log_error(title="Derma print formats", message=frappe.get_traceback())
```

The existing `ensure_derma_schema()` must keep running first: the injector's block is inert
until the SOAP custom fields exist.

### What stays unchanged

`api.py`, every whitelisted endpoint, `assessment.py`, `schema.py`, `settings.py`, every Vue
and JSX file, `derma_chart.bundle.css`, `e2e_seed.py`, `demo_seed.py`, `patches.txt`, and both
print formats' letterhead, CSS, margins and every line of their existing body.

## Security

The block renders **user-authored clinical narrative into HTML in an environment with
autoescape off** — the trust boundary this feature introduces.

- **Control: escaping happens in `_format_value`, per fieldtype, before the string is wrapped
  in `Markup`.** A practitioner typing `<script>alert(1)</script>` into Subjective prints as
  literal text. `Markup` is applied only to the assembled skeleton, never to a raw field value.
  *Regression test:* `TestAssessmentPrintBlock.test_escapes_html_in_narrative_fields`.
- **Control: no new whitelisted endpoint and no permission decision of our own.** The Jinja
  global receives the `doc` that `printview` already resolved and permission-checked; it reads
  no other document except the `Derma Settings` singleton for the field list. There is nothing
  for `_ensure_clinical_access()` to gate — this feature adds nothing to `api.py`.
  *Regression test:* `TestAssessmentPrintBlock.test_renders_only_the_document_passed_in`.
- **Control: the injector writes only the `html` field of formats it can prove it owns the tail
  of.** `_without_derma_block` returning `None` means skip-and-log.
  *Regression test:* `TestPrintFormatInjection.test_skips_format_with_foreign_trailing_comment`.
- **Not a control, stated for the record:** a clinic that configures a `Text Editor` field into
  the Structured list gets that field's stored HTML printed unescaped. That field's content is
  already trusted as HTML by the desk form that wrote it; this does not widen the boundary.

## Acceptance Criteria

**SOAP**

1. A submitted encounter stamped `SOAP` with all four narratives prints a heading and the four
   labelled paragraphs, in both formats.
2. Its Structured fields, if any hold values, are **not** printed.
3. A SOAP encounter with only Subjective filled prints only Subjective — no empty labels.
4. Newlines inside a narrative render as line breaks, not as one run-on paragraph.

**Structured**

5. An encounter stamped `Structured` prints the configured structured fields and no SOAP block.
6. `custom_differential_diagnosis` prints its child rows comma-joined.
7. Editing the field list in `Derma Settings` changes what prints, with no code change and no
   migrate.

**Legacy and degraded**

8. An unstamped encounter carrying Structured content prints that content even when its
   practitioner's default mode is `SOAP`.
9. An encounter with no assessment content at all prints nothing extra — no heading, no empty
   `<div>`, and the format's existing output is byte-identical to before this feature.
10. On a site where the four SOAP custom fields do not exist, printing raises nothing and the
    Structured block still prints.
11. A raise inside the renderer is logged and prints empty; the rest of the format still renders.

**Injection**

12. After `bench migrate`, both formats contain exactly one `do_derma:assessment:start` marker.
13. Running `migrate` twice changes nothing on the second run — the formats' `modified` values
    are identical before and after.
14. The hand-injected legacy block is replaced, not appended to: the phrase
    `derma_structured_values` no longer appears in either format, and neither `Assessment (SOAP)`
    heading is printed twice.
15. A format with `print_format_builder: 1`, a disabled format, and a `Clinical Procedure`
    format are all left untouched.
16. A format whose tail holds a foreign HTML comment after the derma marker is skipped and
    named in the returned `skipped` list.

**No regression**

17. Every existing endpoint keeps its signature and response shape; `api.py` is unmodified.
18. The Python suite and the e2e suite pass unchanged; no bundle rebuild is required.

## Phases

**Phase 1 — Print the SOAP note.** `printing/render.py` with the SOAP path only, the `jinja`
hook, `printing/inject.py`, the `after_migrate` call, and `test_printing.py` covering SOAP,
escaping, empty, and injection idempotency.
*Exit: a practitioner opens a SOAP-documented encounter, hits Print, and reads the note — on
both formats, with the legacy block gone.*

**Phase 2 — Structured parity and the legacy fallback.** The Structured path, `Table` and
`Check` formatting, the other-mode fallback, and the `Derma Settings`-driven field list.
*Exit: an unstamped pre-revamp encounter prints its structured content, and a clinic that edits
the field list sees the print change without a migrate.*

## Open Questions

- **Should the block sit at the end of the format, or before the prescription table?** The end
  is where the legacy hand-injection put it and where appending is safe without parsing the
  clinic's markup. *Default:* the end. A clinic that wants it higher moves the two marker lines
  by hand; the injector's idempotency check keys off the markers, not their position — the
  `stripped.rstrip() + BLOCK` rule will move it back to the end on the next migrate, so this
  default is worth revisiting if a clinic asks.
- **Should `Encounter Print` (`standard: Yes`, owned by `healthcare`) really be written to?**
  *Default:* yes. It is the fallback format on any site without the Dr Sadiq one, the write is
  DB-only, and `after_migrate` repairs it if `healthcare` reverts it.
- **Does the clinic want the mode named on the printout?** *Default:* only through the heading
  — `Assessment (SOAP)` versus `Assessment`. No separate "Documented in: SOAP" line.

- **An ampersand prints as `&amp;`.** Found during implementation, not planned for. Frappe's
  `_sanitize_content` (`frappe/model/base_document.py`) runs `sanitize_html` on every
  `Small Text` field on save, so a practitioner who types `&` has `&amp;` **stored**; escaping
  that on print yields `&amp;amp;`, which displays as `&amp;`. *Default:* leave it. The stored
  string is what the desk form and the chart textarea both already show, so the printout is
  consistent with every other surface, and un-escaping on the way out is the one direction that
  would reopen the injection hole this feature closes.

## Reconciliation — what changed vs the plan

Five deviations, each forced or better:

- **Both phases shipped in one pass.** Phase 2's Structured path is the same `render_mode()`
  call with a different layout — `assessment.get_layout(mode)` already returns either one.
  Shipping Phase 1 alone would have meant writing a renderer that deliberately ignored half of
  its own input, then deleting that restriction a commit later. The phase boundary was real in
  the plan and turned out to be imaginary in the code.

- **The escaping test moved down a level, and gained a partner.** The planned
  `test_escapes_html_in_narrative_fields` asserted `&lt;script&gt;` in the rendered block and
  **failed** — because Frappe strips `<script>` on save, so the renderer never sees one through
  that path. Asserting on the post-sanitiser value would have tested Frappe, not this code, and
  would silently pass if the escaping were deleted. The test now calls `format_field` directly
  with an unsanitised payload, and a second test,
  `test_a_script_tag_never_reaches_the_printed_block`, keeps the end-to-end property. Both
  layers of the defence are now pinned.

- **`_without_derma_block` became public `strip_derma_block`,** per the repo rule against
  privatising a function for having one caller today. Its `END in tail and not
  tail.rstrip().endswith(END)` clause was dropped as dead: a tail containing our `END` marker
  contains only derma comments by construction, so the foreign-comment check already decides it.

- **`format_value` lives in `frappe.utils.formatters`, not `frappe.utils`.** The sketch's import
  raised `ImportError` at test-discovery time.

- **`FORMATTED_FIELDTYPES` was named.** The Design table listed date/time formatting without a
  constant; the implementation needs one, and extended it to the numeric types for the same
  reason.

## Verification

### Run 2026-08-10, all green

| What | Result |
|---|---|
| `bench --site dermaone.localhost run-tests --module do_derma.tests.test_printing` | **20 passed** |
| `bench --site dermaone.localhost run-tests --app do_derma` | **73 passed**, no regressions |
| `yarn test:e2e` | **44 passed** (5.5m), unchanged and un-rebuilt — confirms no bundle work was needed |
| `bench --site dermaone.localhost migrate` | Clean. Both formats went 7008 → 5180 chars: the 1,800-character hand-injected block replaced by the three-line marker block |
| `bench --site dermaone.localhost migrate` (second run) | Both formats' `modified` byte-identical to the first run — `2026-08-10 20:35:56.567173` / `.566243` before and after. Idempotent |
| `bench --site dermaone2.localhost migrate` | A site that never had the hand-injected block converged from a plain migrate — 1 start marker in each format |
| `ruff check` / `ruff format` on the new files | Clean. (The 5 pre-existing `ruff check` failures in `do_derma/patches/` and the unformatted `tests/test_api.py` are untouched and predate this work.) |

The 20 tests, by class:

| Class | Covers |
|---|---|
| `TestAssessmentPrintBlock` (9) | SOAP rendering, structured values excluded in SOAP mode, empty labels dropped, escaping at `format_field`, script tag absent end-to-end, `\n` → `<br>`, empty encounter renders nothing, only the passed document is read, a raise logs and returns empty |
| `TestStructuredPrintBlock` (3) | Structured rendering with no SOAP heading, child rows comma-joined, and the other-mode fallback for an unstamped legacy encounter whose practitioner defaults to SOAP |
| `TestPrintFormatInjection` (7) | Injected once, second run is a true no-op including `modified`, legacy block replaced not appended, builder/disabled/other-doctype formats skipped, foreign trailing comment refused |
| `TestPrintedEncounter` (1) | `frappe.get_print` on a real encounter through a real print format returns the narrative and the heading |

### Manual, against live data

`frappe.get_print("Patient Encounter", "HLC-ENC-2026-03201", print_format=…)` on
`dermaone.localhost`, for both formats:

```html
<div class="derma-soap"><h5>Assessment (SOAP)</h5>
<p><b>Plan:</b> Topical steroid, review in two weeks.</p></div>
```

Eleven SOAP-stamped encounters exist on the site; the printed block is identical in
`Encounter Print` and `Encounter print (Dr Sadiq)`.

### Not yet run

- **Acceptance criterion 10** — a site without the four SOAP custom fields. Both benches have
  them, so the absent-field path is covered by construction (`get_soap_layout()` returns `[]`
  when `soap_is_supported()` is false, and the fallback then renders Structured) and by the
  `skipTest` guards, but not by an executed test on such a site.
- **PDF output.** Only the HTML printview was rendered; no `wkhtmltopdf` or Chrome PDF was
  produced.
- **Criterion 9's "byte-identical" clause** was verified as "nothing visible is added" (the
  block renders to an empty string between two HTML comments), not by a byte diff of the full
  printview.

## Files to touch (summary)

| File | Change |
|---|---|
| `do_derma/printing/__init__.py` | *(new)* Empty — no re-exports |
| `do_derma/printing/render.py` | *(new)* `derma_assessment_html` Jinja global, per-fieldtype escaping, other-mode fallback |
| `do_derma/printing/inject.py` | *(new)* Marker-delimited idempotent injection, legacy-block removal, skip-and-log guard |
| `do_derma/hooks.py` | *(new key)* `jinja = {"methods": [...]}` |
| `do_derma/install.py` | Call the injector from `after_migrate`, guarded |
| `do_derma/tests/test_printing.py` | *(new)* Renderer + injector coverage |
