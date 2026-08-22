# Annotation Studio Camera Capture

## Problem Statement

The derma annotation studio opens on a configured body template — a silhouette the practitioner marks up. On an iPad at the chairside, the practitioner is looking at the actual lesion, not a silhouette. Today the only way to get that lesion into the record is to leave the studio, go to the Photos tab, open the Frappe file uploader and shoot from there, then come back and re-establish where they were. The drawing and the photograph are captured in two separate places at two separate moments, and nothing on the canvas points at the photograph that was just taken.

The studio itself has no capture affordance at all. The practitioner can insert an image with Excalidraw's own image tool, but that image is not a Derma Photo, does not appear in the Photos tab, does not carry a stage (Before / After / Visit), and lands as base64 inside the Health Annotation JSON.

## Solution

Add a camera button to the annotation studio, sitting beside the Excalidraw tool icons, in both the consultation sketchpad and the full procedure studio.

Tapping it opens the device camera (rear-facing by default). Each shot is downscaled, uploaded as a private file, and recorded as a real `Derma Photo` inside a `Derma Photo Set` — patient, appointment, encounter and clinical procedure filled from the studio's own context, stage derived by the same rule the Photos tab already uses, and body view / body region taken from the body template on screen. The photo then appears on the canvas as a movable, resizable image element that the practitioner can mark up, measure against, or draw over.

The canvas element references the stored file rather than owning the bytes: the annotation JSON stays small, and the photograph lives where the rest of the patient's imagery lives — visible in the Photos tab, in comparisons, and linked to the selected chart mark when there is one.

Because the practitioner treats the canvas as the place where the photo lives, deleting the photo element from the drawing deletes the photo — reconciled at save time, so undo before saving remains honest.

## User Stories

1. As a dermatologist working on an iPad, I want a camera button beside the drawing tools, so that I can photograph a lesion without leaving the annotation studio.
2. As a dermatologist, I want the camera to open rear-facing by default, so that I am pointing at the patient and not at myself.
3. As a dermatologist, I want to flip to the front camera when I need to, so that the device orientation never blocks a shot.
4. As a dermatologist, I want the captured photo to appear on the canvas straight away, so that I can annotate the real lesion instead of a silhouette.
5. As a dermatologist, I want to take several shots in one camera session, so that I can capture multiple angles without reopening the camera each time.
6. As a dermatologist, I want each shot in a burst to land slightly offset from the last, so that I can see and separate them rather than one photo hiding another.
7. As a dermatologist, I want the photo to arrive at a workable size in the middle of my current view, so that I do not have to hunt for it or resize it before I can work.
8. As a dermatologist, I want to move and resize the photo on the canvas, so that I can place it beside the body template rather than on top of the region I am marking.
9. As a dermatologist, I want to draw, measure and place marks over the photo, so that my annotations describe the actual lesion.
10. As a dermatologist, I want the body template to keep behaving exactly as it does today when a photo is on the canvas, so that fit-to-template, area outlines and badges are unaffected.
11. As a dermatologist, I want the photo to still be there when I reopen the drawing, so that my annotation still means something the next time I look at it.
12. As a dermatologist, I want the printed and exported chart image to include the photo I drew over, so that the record shows what I was annotating.
13. As a dermatologist, I want a photo taken during a consultation to be filed as a visit photo, so that it lands in the patient's photo history without me tagging it.
14. As a dermatologist, I want a photo taken before a procedure starts to be filed as a Before photo, so that before/after evidence builds itself.
15. As a dermatologist, I want a photo taken once the procedure is running or complete to be filed as an After photo, so that procedure evidence requirements are satisfied without extra tagging.
16. As a dermatologist, I want the photo to carry the body view and region of the template I am working on, so that the Photos tab can group and compare it correctly.
17. As a dermatologist with a chart mark selected, I want the photo linked to that mark, so that the mark carries its own visual evidence.
18. As a dermatologist, I want photos captured in the studio to appear in the Photos tab immediately, so that there is one place to review all imagery for the visit.
19. As a dermatologist, I want the photo stored as a private file, so that patient imagery is never served to an unauthenticated URL.
20. As a clinic that gates clinical data by role, I want capture to run through the same clinical access check as every other chart write, so that no new hole is opened.
21. As a dermatologist, I want the camera button disabled while a shot is uploading, so that I do not fire duplicate captures on a slow connection.
22. As a dermatologist, I want a clear confirmation when the photo has been saved, so that I know the record has it and not just my screen.
23. As a dermatologist, I want an explicit, readable error when the upload fails, so that I know to retake rather than assuming it worked.
24. As a dermatologist on a device or network where the camera cannot open, I want the file picker offered instead, with the reason the camera did not open, so that I am not stranded mid-consultation.
25. As a dermatologist, I want the fallback to be visibly a fallback and not a silent substitution, so that I understand what the app just did.
26. As a dermatologist, I want to delete a photo I mis-shot by deleting it from the canvas, so that a bad photo does not linger in the patient's record.
27. As a dermatologist, I want to undo a deletion before saving and get my photo back intact, so that a stray tap is not destructive.
28. As a dermatologist, I want the deletion to actually take effect only when I save the drawing, so that the record matches what I chose to keep.
29. As a dermatologist, I want deleting the last photo of a set to clean up the empty set too, so that the Photos tab is not littered with empty entries.
30. As a dermatologist who discards a drawing, I want photos I captured in that same session discarded with it, so that abandoning a drawing does not leave orphaned imagery on the chart.
31. As a dermatologist, I want the discard confirmation to tell me how many photos will go with it, so that I can decide with the full picture.
32. As a dermatologist reopening a drawing whose photo file is missing or unreadable, I want one clear alert and the element left in place, so that I can see something was there rather than silently losing it.
33. As a dermatologist, I want a photo that failed to load never replaced by a different image, so that I can never annotate the wrong patient's photograph.
34. As a dermatologist, I want captured photos downscaled and re-encoded before upload, so that capture is fast on clinic wifi and reopening a chart is not slow.
35. As a dermatologist, I want the downscale to preserve enough detail to be clinically useful, so that the photo is worth having.
36. As a dermatologist using the plain consultation sketchpad, I want the same camera button as the full procedure studio, so that the most common iPad case is covered.
37. As a dermatologist, I want to retake by deleting the photo and shooting again, so that the interaction stays simple and predictable.
38. As a clinic manager, I want photos captured in the studio to satisfy the procedure's before/after photo requirement, so that readiness checks pass without duplicate uploads.
39. As a practice using the Photos tab, I want studio-captured photos to be retaggable and deletable there exactly like uploaded ones, so that there is one set of controls for photos.
40. As a developer, I want the annotation JSON to stay free of photo bytes, so that Health Annotation documents remain small and loadable.
41. As a developer, I want photo rehydration to reuse the existing template rehydration path, so that there is one mechanism for putting stored images back on a canvas.
42. As a developer, I want capture to reuse the existing photo set creation, upload and deletion endpoints, so that no new server surface is introduced for this feature.

## Implementation Decisions

### Surface and entry point

- The feature is scoped to the annotation studio only. The Photos tab already reaches the camera through `frappe.ui.FileUploader`'s Camera button and is not changed here.
- The camera button renders inside the Excalidraw container, positioned by studio-owned CSS to sit next to the tool island. Excalidraw 0.17 exposes no injection point in that island, so the button is absolutely positioned with a fixed offset. This is an accepted coupling to Excalidraw's layout and needs re-checking on any Excalidraw upgrade.
- The button is present for both anchors: the stripped-down consultation sketchpad and the full procedure studio. It does not depend on the `isProcedureAnchor` gate.
- The button carries a `data-test` hook, matching the studio's existing convention.

### Capture

- Capture uses `frappe.ui.Capture` directly rather than the full uploader dialog, so the camera is one tap away. `Capture` already defaults to `facingMode: "environment"` and provides its own flip control.
- `Capture` returns data URLs and performs no upload. The studio converts each data URL to a blob and uploads it through Frappe's existing `upload_file` endpoint as a private file, then passes the returned file URL on.
- Before upload, each shot is re-encoded to JPEG at quality 0.85 with its long edge capped at 2048px, using the same canvas re-encode approach the studio already uses to prepare template images.
- A camera session that returns several shots produces one photo set holding several photos, and several canvas elements cascaded by a small offset.

### Persistence

- After upload, the studio calls the existing photo set creation endpoint with: patient, appointment, encounter and clinical procedure from the studio context; the uploaded file URLs as photo rows; the selected chart mark when one is active; and body view / body region derived from the selected body template.
- Photo stage (`photo_type`) is not chosen in the studio. The server's existing derivation from the clinical procedure's state decides Before / After / Visit, and the Photos tab's retag flow remains the way to change it.
- Photos are private files, and capture is gated by the same clinical access check as the rest of the chart API. No new whitelisted method is added.

### Canvas representation

- The photo becomes an Excalidraw image element tagged in `customData` with a photo kind plus the photo name, photo set name and file URL.
- The element's binary payload is stripped from the scene before the annotation is saved — the same treatment the body template image already gets — so the Health Annotation JSON never carries photo bytes.
- On load, photo elements are rehydrated from their file URL through the existing template rehydration path.
- Photo elements are explicitly not template elements: the template detection stays keyed on the template element itself, so fit-to-template, template rebuild and template-part behaviour are untouched.
- New photos are placed at the centre of the current viewport, sized to roughly 40% of the visible canvas, and are freely movable and resizable.
- The exported chart image saved alongside the annotation includes photo elements.

### Deletion and discard

- Removing a photo element from the canvas deletes the underlying photo, reconciled at **save** time: on save, any photo element that was present when the drawing loaded (or was captured this session) and is now gone is deleted through the existing photo deletion endpoint. Undo before saving therefore restores both element and record.
- That endpoint already deletes the containing photo set when it empties, and releases chart mark and treatment entry links first. No new cascade logic is needed.
- Photos captured during a session that is then discarded are deleted with the session, mirroring how session-created chart marks are handled today. The discard confirmation names the photo count alongside the mark count.

### Failure handling

- If the camera cannot open — permission denied, no secure context, no `mediaDevices` — the studio shows an explicit message naming the reason and then offers the standard file uploader dialog so the practitioner can pick from the photo library. The fallback is never silent.
- If upload or photo set creation fails, no element is placed and the error is surfaced with the studio's existing error message pattern. Partial state is not kept.
- If a photo's file cannot be fetched on reopen, the studio alerts once and leaves the element with Excalidraw's placeholder, exactly as an unavailable body template behaves. It never substitutes another image.
- The capture button is disabled for the duration of the upload, and success is confirmed with the studio's existing alert pattern. No placeholder element is drawn on the canvas while the upload is in flight — the file document is the single owner of the image state.

## Testing Decisions

A good test here asserts externally observable behaviour: given a studio-shaped payload, what does the patient's record end up containing? It does not assert on internal helper names, element ordering, or how the scene JSON is assembled.

- **Seam.** The single, existing seam is the photo API in `do_derma/api.py` — photo set creation and photo deletion — already exercised by the photo tests in `do_derma/tests/test_api.py`. No new seam is introduced: capture adds no server surface, so all server-side coverage extends the existing photo test class.
- **Prior art.** The existing photo tests build a photo set through the public API and assert stage derivation and set type (`test_a_photo_taken_outside_a_procedure_is_a_visit_photo`, the Before/After variants, and the explicit-type case). New tests follow that shape and use the same helper.
- **What gets tested server-side.** That a studio-shaped payload — patient, appointment, encounter, optional clinical procedure, chart mark, body view and body region — produces a photo set with the right stage, the right body metadata, and a chart mark linked back to the set; and that deleting the last photo of a studio-created set removes the set and releases its links.
- **What is verified in the browser.** Everything that lives only in the studio front end: the button's position beside the tool island, capture on an iPad, placement and cascade, rehydration on reopen, delete-at-save reconciliation, discard behaviour, and the camera-unavailable fallback. The repo has no JavaScript test runner and none is introduced.
- Frontend behaviour that never reaches the server cannot be asserted from Python; those cases are covered by the manual browser pass, not by a Python test that pretends to cover them.

## Out of Scope

- Any change to the Photos tab, including the separately specified capture-first redesign.
- Appending later captures to an existing photo set. Each camera session creates its own set.
- A replace-in-place / retake affordance on an existing canvas photo. Delete and re-shoot.
- Choosing or editing the photo stage from inside the studio. Retagging stays in the Photos tab.
- Consent capture, a consent flag, or any audit record beyond what the existing clinical access check and file privacy already provide.
- Video capture, burst mode beyond what the frappe capture dialog already offers, and any image processing beyond downscale and re-encode.
- Cropping, rotation or colour correction of captured photos.
- Offline capture with deferred upload.

## Further Notes

- `getUserMedia` requires a secure context. iPads served over plain HTTP on a LAN will always take the file-picker fallback; the deployment is expected to be HTTPS.
- The absolute positioning of the capture button against Excalidraw's tool island is the most fragile part of this change. It is confined to the studio's own stylesheet so that an Excalidraw upgrade has one place to look.
- Captured photos count towards a procedure template's before/after photo requirement, since they are ordinary photo sets — the readiness check needs no change.
- Branch: `feat/annotation-studio-camera-capture`.
