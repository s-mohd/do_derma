# Derma Chart QA Findings — 2026-08-29

Status: draft, awaiting prioritisation
Source: full-page exploratory QA on 2026-08-29 against `dermaone.localhost`, branch
`fix/annotation-studio-review-findings`, driving the real UI and verifying every save
against the database. Follows on from `derma-chart-review-findings.md` (2026-08-28); the
findings fixed there were re-verified working and are not repeated here.

## Problem Statement

A practitioner working a visit through the Derma Chart page cannot finish two of its six
tabs. Saving a prescription fails every time with no visible error — the row simply does
not persist, and the practitioner has no way to know. Selecting any consent template shows
"Unable to render consent preview" instead of the form. A third problem is quieter and
worse over time: editing a procedure note writes the new text to a different field than the
one the original note lives in, so the chart, the desk form, and reports each see a
different version of the clinical record.

Around those, the visit flow works but talks past the practitioner in places: completing an
encounter flashes "App do_dental is not installed" twice while actually succeeding; opening
the annotation studio from a procedure row says it is scoped to that procedure but will not
stamp until the procedure is picked a second time; inventory blocker banners warn about
stock without naming the item; and the prescription grid demands a "Duration" that no
visible column offers.

## Solution

Make every tab of the chart able to complete its job, and make every failure speak.

Prescriptions save and reload correctly. Consent previews render for the seeded templates,
or state precisely why they cannot. A procedure note has exactly one owner field, and an
edit that cannot be applied is refused loudly rather than dropped. Encounter completion
reports only outcomes that concern the derma visit. The studio, when opened from a
procedure row, is immediately ready to stamp that procedure. Blocker banners name the item
they are blocking on. Grid-level validation failures point at a field the practitioner can
actually see.

## User Stories

1. As a practitioner, I want a prescription row I saved to actually persist, so that the patient leaves with the medication order I wrote.
2. As a practitioner, I want a failed prescription save to show me an error, so that I never assume a lost order was recorded.
3. As a practitioner, I want an encounter that already has prescriptions to load its Rx tab, so that I can review and extend prior orders.
4. As a practitioner, I want the mandatory prescription fields visible in the grid, so that I can satisfy validation without opening each row's detail editor.
5. As a practitioner, I want the grid's column label to match the name validation uses, so that "Value missing for: Duration" points at something I can find.
6. As a practitioner, I want unreasonable values like 500 repeats rejected at entry, so that a typo in the wrong column cannot become a standing order.
7. As a practitioner, I want to select a consent template and see the rendered form, so that I can capture consent during the visit.
8. As a practitioner, I want a consent template that cannot render to say what is missing, so that an administrator can fix the template rather than me retrying.
9. As a practitioner, I want a procedure note to read the same everywhere it appears, so that the chart, the desk form, and reports never disagree about what I wrote.
10. As a practitioner, I want an edit to a note that cannot be applied to be refused with a message, so that my correction is never silently discarded.
11. As an auditor, I want one authoritative field holding the procedure note, so that the clinical record has no second version to reconcile.
12. As a practitioner, I want completing an encounter to show only messages about this visit, so that "App do_dental is not installed" never makes a successful completion look failed.
13. As a practitioner, I want the completion summary to confirm what was submitted and billed, so that I can hand off to reception with confidence.
14. As a practitioner, I want opening the studio from a procedure row to arm that procedure for stamping, so that my first canvas click places a mark instead of doing nothing.
15. As a practitioner, I want the studio's live marks list to show every mark on the canvas, so that the panel and the drawing never disagree mid-session.
16. As a practitioner, I want badge numbers to stay stable while I work, so that a legend I glanced at a moment ago still matches the canvas.
17. As a practitioner, I want the procedures list scope to match its own empty-state copy, so that I know whether I am looking at this visit or this patient's history.
18. As a practitioner, I want an inventory blocker banner to name the item it concerns, so that I can resolve the stock problem without opening the completion dialog to find out.
19. As a practitioner, I want the chart to open on the Assessment tab for a fresh visit, so that documentation starts where the visit starts.
20. As a practitioner, I want the "Overlay Marks" confirmation to say where the overlay is visible, so that I am not left hunting for what the button did.
21. As a clinic administrator, I want validation and error surfacing consistent across tabs, so that training one tab's behaviour teaches all of them.

## Implementation Decisions

- The prescription row serialiser must treat encounter child rows as documents, not
  dictionaries — build each returned row from the child document's fields rather than
  membership-testing the row like a dict. One helper backs both the read and write
  endpoints, so a single fix covers loading and saving.
- The chart frontend must surface non-success responses from every save endpoint it calls.
  A save that returns a server error shows the server's message; no save path may resolve
  silently on failure. This is the "fail loudly near the bug" rule applied at the
  UI boundary.
- Procedure notes get one owner. Decision needed at implementation time between two
  routes: (a) stop marking the underlying notes field set_only_once so edits go to the
  original field, retiring the shadow custom field, with a one-off migration copying any
  drifted shadow values back; or (b) make the custom field the sole owner everywhere,
  including create. Route (a) is preferred because everything outside the chart already
  reads the original field. Whichever route is taken, the update endpoint must throw, not
  skip, when asked to change a field it cannot apply.
- The consent preview failure originates in the sibling health app's consent controller,
  which assumes a field the consent template doctype does not declare. Within this repo the
  preview endpoint should catch the render failure and return a message naming the
  template, so the chart shows an actionable error; the underlying controller fix belongs
  to the health app and is tracked as out of scope here.
- The "do_dental is not installed" messages leak from the health app's invoice-for-visit
  call during session completion. The completion endpoint should suppress foreign
  msgprint noise from that call while preserving its return value and preserving genuine
  failures in the error log, which it already writes.
- The studio's procedure-anchored open path must seed the tagging state with the anchoring
  procedure — the same state the Procedures panel sets on click — so the header's
  "Procedure: X" claim and the canvas behaviour agree.
- The live marks panel and the badge counter must derive from the same collection; the
  saved-drawing reopen path already renders the full list and is the reference behaviour.
- Badge numbering: number marks and area selections from one sequence assigned at save
  time, and stop reassigning numbers of existing marks when an area is selected
  mid-session. Numbers shown during editing must match what the saved legend will say.
- The procedures list either loads the patient's prior-visit procedures under their own
  date groups (the timeline proves the data is reachable) or scopes its copy and counters
  honestly to the current visit. Decision preferred: keep the list visit-scoped and fix
  the copy, since history already has a home on the Review timeline.
- Inventory blocker header cards reuse the per-item naming the completion confirm dialog
  already renders — same source data, same wording, one owner for blocker text.
- Default tab on a fresh visit is Assessment. Tab state may persist within a session, but
  a newly opened visit starts at the first tab.

## Testing Decisions

- The seam is the whitelisted API layer, exercised from the existing Python suite the same
  way prior remediation rounds tested `save_derma_annotation` and `prune_chart_marks`. A
  good test calls the endpoint as the UI would and asserts on what lands in — or is
  refused from — the database, never on helper internals.
- Prescription round-trip is the anchor test: set rows through the write endpoint, read
  them back through the read endpoint, assert the row content survives. This single test
  fails on the current TypeError for both directions.
- Note ownership gets a drift test: create a procedure with a note, edit it through the
  update endpoint, assert exactly one field holds the final text and that a refused edit
  raises rather than returning success.
- Consent preview gets a test asserting the endpoint returns an error payload naming the
  template rather than raising, using a seeded legacy template.
- Completion gets a test asserting the response carries no foreign-app messages on the
  success path.
- Studio arming, live marks list, badge renumbering, tab default, and blocker card naming
  are browser-verified: the Python suite cannot observe payloads the studio builds or
  fails to build, as the mark-size regression proved. Their acceptance criteria are
  manual walkthrough steps mirroring the QA session that found them.

## Out of Scope

- The consent controller fix in the health app (reading a field the template doctype does
  not declare) — this spec only makes the derma endpoint fail informatively.
- The invoice-for-visit internals in the health app that emit the do_dental messages —
  this spec only stops the noise crossing into the derma completion response.
- Photo capture, comparison, and staging — verified working during the QA pass.
- The three deferrals from the 2026-08-28 round (mobile sidebar collapse, Excalidraw
  console warnings) — unchanged, still owned elsewhere.
- Patient selection UI — owned by the health sidebar by standing decision; nothing here
  touches it.

## Further Notes

- The QA pass left artefacts on the dev site: submitted encounter HLC-ENC-2026-03107,
  completed procedure HLC-CPR-2026-02852 (with drifted note fields — useful as a live
  reproduction of finding 9), a draft invoice, and one uploaded photo.
- The prescription bug is the highest-value fix in this spec: small, isolated, and it
  unblocks an entire tab. It is also the clearest example of the silent-failure pattern
  the frontend decision above addresses; fixing the serialiser without the error
  surfacing would leave the next backend bug just as invisible.
- Verified working and needing no action: assessment structured/SOAP round-trip, procedure
  creation validation, per-mark materials, area-variable persistence and reload, mark
  deletion reconciliation, photo privacy default, copy-marks tooltip, completion blocker
  gating with override reason.
