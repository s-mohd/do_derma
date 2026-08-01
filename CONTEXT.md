# Do Derma

Dermatology charting and encounter workflows for a Frappe/ERPNext Healthcare bench. This
glossary fixes the language used across the derma chart page, its APIs, and its doctypes.

## Language

### Charting

**Derma Chart**:
The single-page clinical workspace at `/app/derma-chart` where a practitioner documents one
dermatology visit.
_Avoid_: derma page, chart page, console

**Body Template**:
A labelled anatomical image (face, hands, legs, full body) that marks are placed on.
_Avoid_: body map, image template, chart template

**Mark**:
One placed point on a Body Template, recording what was done at that anatomical location.
_Avoid_: marker, dot, pin, annotation point

**Annotation**:
A saved drawing scene over a Body Template. Stored as a do_health `Health Annotation`, not as
a do_derma doctype.
_Avoid_: drawing, sketch, scene

### Assessment

**Assessment Mode**:
The documentation format a visit is written in. Exactly two exist: **SOAP Note** and
**Structured Assessment**. The mode is stamped on the encounter once anything is written, so a
note always reopens in the format it was written in.
_Avoid_: note type, template, layout, view

**SOAP Note**:
An Assessment Mode consisting of four free-text narrative fields — Subjective, Objective,
Assessment, Plan — stored independently of the structured encounter fields.
_Avoid_: narrative note, free-text note

**Structured Assessment**:
The Assessment Mode built from the existing Patient Encounter clinical fields (symptoms,
symptom duration, symptom notes, diagnosis, differential diagnosis, diagnosis note, physical
examination, other examination, illness progression).
_Avoid_: Subjective/Objective mode, classic mode, current fields

**Practitioner Default**:
A practitioner's preferred Assessment Mode for *new* encounters only. It never overrides the
mode already stamped on an existing encounter.
_Avoid_: user preference, default template

### Anchoring

**Encounter-anchored**:
Clinical content attached to a `Patient Encounter`. The Derma Chart is encounter-anchored.

**Procedure-anchored**:
Clinical content attached to a `Clinical Procedure`. The incumbent do_health annotation
workflow is procedure-anchored — 5,485 of 5,500 annotation links point at procedures.
