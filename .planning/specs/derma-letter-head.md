# Derma prints use Letter Head records and the practitioner's mark

Agreed 2026-10-04.

## Goal

Every Derma Chart printable — assessment note, AI letters, consent, annotation review — prints on
the site's default Letter Head, or on the practitioner's own Letter Head when one is set, and
carries the practitioner's signature and/or stamp.

Success: changing the default Letter Head in Desk changes every derma print; giving one doctor a
Letter Head changes only their visits.

## Today

- `do_derma/printing/letterhead.py` hardcodes the Derma One logo, swaps it by matching the
  practitioner's name (`"sadiq abdulla"`), and hardcodes the company footer.
- `public/js/shared/print_window.js` duplicates that footer and logo for client-side prints.
- The signature block is an empty ink line with the name and title. `custom_signature` and
  `custom_stamp` are unused by do_derma.

## Deployment prerequisite

The site default ("DermaOne Letter Head") is currently Dr Nedhal's personal one with an empty
footer. Before release, an admin creates a neutral clinic Letter Head (logo header + company
footer) and makes it the default, then sets Dr Nedhal's and Dr Sadiq's own Letter Heads on their
practitioner records. The footer must fit the 42mm reserved at the foot of each page.

## 1. Field and resolution

New Custom Field, owned by do_derma in `schema.py` (never a patch alone — fresh installs skip
patches):

| Property | Value |
|---|---|
| DocType | Healthcare Practitioner |
| fieldname | `custom_derma_letter_head` |
| label | Letter Head |
| fieldtype | Link → Letter Head |
| insert_after | `custom_official_document_mark` |
| description | Derma chart prints use this instead of the site's default Letter Head. |

`letterhead.get_letter_head(practitioner)` returns a Letter Head doc:

1. the practitioner's `custom_derma_letter_head`, when set and not disabled;
2. else the site default (`is_default=1, disabled=0`);
3. else `frappe.throw(_("Set a default Letter Head to print derma documents."), frappe.ValidationError)`.

A disabled override falls back to the default.

Practitioner per printable:

| Printable | Practitioner |
|---|---|
| Assessment note, AI letters | the encounter's practitioner (unchanged) |
| Consent, annotation review | the encounter's practitioner, else the appointment's |
| none found | default Letter Head, no mark |

Deleted: `PRACTITIONER_LOGO_FILES`, `LOGO_SRC`, `PRACTITIONER_LOGO_SRCS`, `get_logo_file`,
`get_logo_url`, `derma_letterhead_logo`, `FOOTER_LINES`, `FOOTER`, the two bundled logo PNGs
(once nothing else references them), and the `letterhead_logo` chart payload key.

## 2. Page shell and mark

The existing shell in `printing/letterhead.py` stays: the table with the repeating tfoot spacer,
the fixed footer, `#footer-html` for wkhtmltopdf, and `STYLE`. What changes is what fills it:

- header = the Letter Head's `content`, top of page one;
- footer = the Letter Head's `footer`, fixed to the foot of every sheet;
- the 42mm footer reservation is one named constant;
- Letter Head HTML is inserted as-is, not rendered as Jinja;
- image-source Letter Heads need no special case — Frappe writes the image into `content` /
  `footer` on save.

The fixed strings `OPEN`, `HEADER`, `CLOSE`, `SIGNATURE` become Jinja globals registered in
`hooks.py`, so the Letter Head resolves at render time rather than at seed time:

- `derma_letterhead_open(practitioner)`
- `derma_letterhead_close(practitioner)`
- `derma_practitioner_mark(practitioner)`

`practitioner` may be a Healthcare Practitioner doc, do_health's practitioner context dict, or
empty.

### Mark

`derma_practitioner_mark(practitioner)` replaces the empty ink line:

- signature image = `custom_signature` (data URI from the Signature field);
- stamp image = `custom_stamp` (file URL);
- `custom_official_document_mark` picks: Signature → signature, Stamp → stamp, Both → both
  overlaid in the same signing area; empty or unknown → Signature;
- a chosen image that is missing is skipped; with no image shown, the empty ink line returns so
  the doctor can sign by hand;
- the name and title (`custom_specialty` or `designation`) always print under the line.

The rule mirrors do_health's `_practitioner_context` (private, so not imported); a test pins it.

### Images in PDFs

Private Letter Head and stamp images (`/private/files/...`) are inlined with Frappe's
`frappe.utils.pdf.inline_private_images` on the PDF path. The browser print window fetches them
with the logged-in session. Public `/files/...` images load normally.

## 3. Per printable

### Assessment note (Patient Encounter print formats)

- `printing/note.py` template uses the three Jinja globals.
- The chart keeps `no_letterhead=1` on the printview URL so Frappe never adds a second header.
- `TEMPLATE_VERSION` 20 → 21; `after_migrate` re-seeds the formats.

### AI letters (do_health Patient Print Templates seeded by `documents.py`)

- `LETTER_TEMPLATE` uses the three Jinja globals, for both the English and Arabic blocks' marks.
- do_health's renderer already passes `practitioner` with `custom_signature`, `custom_stamp` and
  `custom_official_document_mark`; no do_health change.
- `TEMPLATE_VERSION` 21 → 22. Already-issued PDFs are not re-rendered.

### Consent and annotation review (moved server-side)

New whitelisted endpoint in `api.py`:

```python
@frappe.whitelist()
def get_derma_print_html(kind: str, name: str) -> dict[str, str]:
	"""Returns {"title": ..., "html": ...}: a complete page on the practitioner's Letter Head."""
```

- Gates with `_ensure_clinical_access()` first, then reuses the existing helpers.
- `kind="consent"`: reuses `get_derma_consent_html`'s doctype lookup and render-if-missing, practitioner from `doc.get("encounter")`; page
  = identity line (patient · MRN · encounter) + `rendered_html` (waiver note included as today)
  + mark.
- `kind="annotation"`: reads the saved Health Annotation — preview image, server-generated
  `annotation_data` legend, template label; identity line = MRN · drawing label · date ·
  practitioner · encounter, the same fields the client uses today.
- Every interpolated value is escaped with `frappe.utils.escape_html`; the legend is already
  escaped at generation.
- Unknown `kind` → `frappe.throw(_("Unknown printable: {0}").format(kind), frappe.ValidationError)`.
- Missing records raise `DoesNotExistError` unchanged.

### Client

- `public/js/shared/print_window.js` becomes `printHtml(title, html)`: open a window, write the
  server's page, print. Its CSS, logo and footer are deleted.
- `printConsent` and `printAnnotationReview` in `DermaChart.vue` call the endpoint, then
  `printHtml`. Errors show through the existing `serverErrorText` alert.
- The consent preview dialog is unchanged.

## 4. Testing

Each test builds its own Letter Heads and practitioner; nothing relies on site data.

1. Resolution: override wins; disabled override → default; no override → default; nothing → raises.
2. Shell: output contains the chosen Letter Head's `content` and `footer`; the hardcoded Derma
   One address is gone.
3. Mark: Signature / Stamp / Both / empty each show the right images; a missing image falls
   back to the ink line; name and title always present.
4. Assessment note through printview with an override practitioner shows their Letter Head and
   signature (requires `bench migrate` first).
5. AI letter through do_health's renderer shows the override Letter Head and the mark.
6. Endpoint: access gate; consent contains identity line, body and mark; annotation contains
   image, escaped label and mark; unknown kind raises.
7. Schema: `custom_derma_letter_head` exists after install, links Letter Head, sits after
   `custom_official_document_mark`.
8. Browser: each printable for Dr Sadiq with his own Letter Head, and for a practitioner without
   an override.

Run with `--module` (`--test ClassName` is a silent no-op on this bench) and diff failures
against the six known failures on main.

## Out of scope

- Re-rendering already-issued PDFs.
- do_health's own print templates.
- Creating the neutral clinic Letter Head on live sites (deployment prerequisite above).
