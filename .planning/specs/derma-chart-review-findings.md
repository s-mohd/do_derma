# Derma Chart Review Findings — Remediation

Status: draft, awaiting prioritisation
Sources: three review passes on 2026-08-28 (annotation studio review, chart page QA sweep,
end-to-end encounter walkthrough), all on `dermaone.localhost` against branch
`fix/annotation-studio-review-findings`.

## Problem Statement

Three exploratory reviews of the Derma Chart page and its annotation studio produced a body of
findings that currently lives in session reports and memory notes. Some were fixed on the
`fix/annotation-studio-review-findings` branch; the rest are open, ranging from a clinical
data-loss bug to accessibility gaps. This spec collects every finding in one place, records
what is already fixed so no session re-diagnoses it, and defines the acceptance criteria for
what remains.

## Already Fixed (reference only — commit f244df0)

These four studio findings were fixed on the current branch and re-verified in the final
walkthrough. They are listed so later readers do not mistake them for open work.

1. Deleting a mark's canvas elements left its Derma Chart Mark row behind: the chart counted
   it, inventory blockers saw it, and reopening the drawing resurrected it. Fixed with the
   `prune_chart_marks` endpoint and save-time reconciliation.
2. `save_chart_mark` copied only `DERMA_MARK_FIELDS`, silently dropping configured variables
   with no matching mark field. Fixed with Procedure-source Derma Mark Variable child rows.
3. Values typed in Procedure Variables after placing a mark bound to the next mark instead of
   the placed one. Fixed with write-behind to the last placed mark and selection clearing on
   entering select mode.
4. Blank required variables could be saved without notice. Fixed with a save-time confirm.

## Open Findings

### Critical

#### 1. Area variable values are destroyed on resave (data loss)

An area variable filled in without a mark placed on that area persists only inside the
regenerated legend HTML (`annotation_data` on the Health Annotation Table child row). Nothing
durable holds the value. When the drawing is reopened, `seedPartValues(marks)` in
`DermaAnnotationStudio.jsx` seeds part values from mark rows only, finds none, and the next
save regenerates the legend without the area row.

Reproduced end to end: a drawing carried "Forehead — Severity: aaa"; opening it, placing one
unrelated procedure mark, and saving removed the area row from the legend and erased "aaa"
from the database entirely (verified by SQL — the value existed nowhere after the save). The
practitioner gets no warning, and the printed sheet quietly loses a recorded clinical value.

Fix direction: give area-only values a durable owner — either persist them as mark-less
Derma Mark Variable rows on the annotation, or refuse to save them with a clear warning that
a mark is required. Additionally seed `partValues` from the saved drawing state, not only
from mark rows, so reopening reflects everything previously saved.

Acceptance criteria:
- Filling an area variable and saving, with no mark on that area, either persists the value
  durably or is blocked with a message naming the area and the missing mark.
- Reopening a saved drawing shows every previously saved area value in the panel and legend.
- Editing a drawing and saving never removes an area value the edit did not touch.
- A regression test covers the reopen-and-resave path (note: the Python suite cannot see
  payloads the studio fails to send, so this needs a test that exercises the seed path with
  a saved annotation fixture).

### High

#### 2. Procedure column shows the patient's name

The procedure table's PROCEDURE column renders "MONA ALHEJAILAN - Test1" — the Clinical
Procedure document title, which leads with the patient name. The patient is already named in
the page header and sidebar; the one column meant to say what was done instead repeats who it
was done to, and truncates on two lines doing it.

Fix direction: render the template or procedure name (with the area already in its own
column), not the document title.

Acceptance criteria: the column shows clinical content only; the patient name appears nowhere
in the table body; existing sort by "Procedure A-Z" still works on the displayed value.

#### 3. Inventory blocker banner truncates its message

The header banner shows "Dose/quantity is missing. Lot number is missing. Expiry date is …"
with no way to expand it. The full text is only discoverable by triggering the Complete
Encounter confirm dialog. The Review tab shows the same blockers with full text, but nothing
points the reader there.

Fix direction: make the banner expandable or wrap the full text; a banner that exists to
block completion must be readable where it appears.

Acceptance criteria: the complete blocker message is readable from the banner itself without
opening the completion dialog.

#### 4. Review tab blocker cards render broken stat tiles

The blocker cards on the Review tab contain orphaned fragments — "Nos / available / marks",
"materials recorded in", "dose recorded in" — value/label pairs misaligned into cryptic
tiles. The information is important (it gates sign-off) and currently reads as debris.

Fix direction: rebuild the card layout so each metric is a labelled value; drop tiles that
have no value to show.

Acceptance criteria: every tile on a blocker card reads as "label: value"; no fragment
appears without its counterpart; cards render correctly at 1280px and tablet widths.

### Medium

#### 5. Raw internal ID as a section header

Expanding a procedure's Materials shows the consumables grouped under "DCM-2545362" — the
Derma Chart Mark autoname. Practitioners have no way to map that to a mark on the drawing.

Fix direction: label the group by badge number and procedure, e.g. "Mark #1 — Test1".

#### 6. "Completing…" busy state shows while the confirm dialog is still open

Clicking Complete Encounter greys the button to "Completing…" before the user has answered
the blocker confirm. Answering "No" restores it, but during the dialog the page reads as if
completion is already running.

Fix direction: enter the busy state only after the confirm is accepted.

#### 7. Marks Placed panel shows only a count

The studio panel says "1 tagged mark(s) on this drawing" with no list, no way to focus a
mark, and no per-mark delete. Related open annoyance from the first studio review: marks
under an area outline are hard to click because the part wins the hit-test — a mark list
would also be the workaround for that.

Fix direction: list marks with badge number, procedure, and variables; clicking a row
selects/centres the mark on canvas.

#### 8. No-patient state is a dead end

The empty state says "Use the health sidebar to select a patient" instead of offering the
search directly. Search exists in the sidebar, but the main panel — where the eye lands —
only describes it.

Fix direction: put a patient search (or a button focusing the sidebar search) in the empty
state itself.

#### 9. Broken photo asset handling

A seeded patient photo (`/private/files/PAT-2022-011c52196.jpg`) 404s; thumbnails render
broken. Missing files should degrade to a placeholder, not a broken image. (The wider Photos
tab rework is specced separately — see the Photos tab redesign spec; this item is only the
graceful-placeholder behaviour.)

### Low

#### 10. Accessibility gaps in dialogs

The New Procedure dialog's Procedure Template combobox, Notes textarea, and close button have
no accessible names; the accessibility tree shows bare `combobox` / `textbox` / `button`
entries. Screen-reader users get no field identity.

Fix direction: associate the visible labels via `for`/`id` or `aria-label`; name the close
button.

#### 11. Nested scroll friction

`.main-section` and `.procedure-table-wrapper` both scroll; reaching an expanded materials
row's Remove/Add controls takes two-level scrolling, and the sticky table header intercepts
clicks on rows scrolled beneath it.

Fix direction: let the table grow with its content inside the page scroll (one scroll owner),
or at minimum make the sticky header non-interactive for hit-testing.

#### 12. Mobile sidebar overlay

At 390px the health sidebar overlays chart content with no responsive collapse.

Fix direction: collapse the sidebar behind a toggle at narrow widths.

#### 13. Console warnings

A React controlled/uncontrolled input warning fires from Excalidraw's `LockButton` (upstream,
cosmetic), and a React error trace appears after mark save originating in the
`DermaAnnotationStudio` wrapper — the save completes, but the error should be run down before
it hides a real failure. Socket.io "xhr poll error" spam is a dev-bench artefact, not app
code.

## Unresolved / Not Reproduced

- Pen-tool CPU spin: resuming a saved drawing then using the pen once pegged the Chrome
  renderer at ~100% for 7+ minutes, twice, via CDP input. Never reproduced on fresh studio
  instances; may be a CDP-input artefact. Keep an eye on it; do not build a fix without a
  repro.
- Badge numbers reshuffling between sessions is by design (Y-sorted for print) — not a bug,
  but worth a help hint if users report it.

## Out of Scope

- The Photos tab capture-first redesign (own spec).
- The annotation studio camera capture feature (own spec, `annotation-studio-camera-capture.md`).
- Denormalised mark fields (`marker_label`, `body_template_part`, `annotation_json`) staying
  NULL while the JSON holds the data — worth a look, but it is a schema-consistency question,
  not a review regression; raise separately if a consumer needs those fields.

## Suggested Order

1. Finding 1 (data loss) — clinical record integrity, blocks trust in the studio.
2. Findings 2–4 — the three most visible daily-use defects.
3. Findings 5–9 — polish with clear value.
4. Findings 10–13 — accessibility and hygiene, batchable.
