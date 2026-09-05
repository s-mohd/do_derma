/**
 * Procedures that record one set of variables for the whole treatment rather than one per mark.
 *
 * The studio keys its state by the label a clinician reads; the server keys these values by the
 * template's docname. Everything that crosses that boundary goes through here.
 */

export function capturesPerProcedure(procedure) {
  return Boolean(procedure?.custom_derma_variables_per_procedure)
}

/** The labels whose procedure records one shared set, for the studio to test membership against. */
export function perProcedureLabels(procedures, labelOf) {
  return new Set((procedures || []).filter(capturesPerProcedure).map(labelOf))
}

/** label -> template docname, the translation every read and write needs. */
export function templateNamesByLabel(procedures, labelOf) {
  const names = {}
  for (const procedure of procedures || []) {
    if (capturesPerProcedure(procedure)) names[labelOf(procedure)] = procedure.name
  }
  return names
}

/**
 * What the procedure already holds, relabelled for the studio. Read rather than derived from the
 * marks: a procedure drawn freehand has values and no marks to carry them.
 */
export async function fetchSharedValues(clinicalProcedure, procedures, labelOf) {
  if (!clinicalProcedure) return {}
  const response = await window.frappe.call({
    method: "do_derma.api.get_procedure_variables",
    args: { clinical_procedure: clinicalProcedure },
  })
  const byTemplate = response?.message || {}
  const shared = {}
  for (const procedure of procedures || []) {
    const values = byTemplate[procedure.name]
    if (values && Object.keys(values).length) shared[labelOf(procedure)] = values
  }
  return shared
}

export async function persistSharedValues(clinicalProcedure, procedureTemplate, values) {
  await window.frappe.call({
    method: "do_derma.api.save_procedure_variables",
    args: {
      clinical_procedure: clinicalProcedure,
      procedure_template: procedureTemplate,
      values: values || {},
    },
  })
}

/**
 * Which required variables a shared set still leaves empty, in the same shape the canvas scan
 * returns. The canvas cannot answer this on its own: a procedure that keeps one set may have
 * placed no marks at all, so there is nothing on it to inspect.
 *
 * Only procedures the clinician actually engaged with are reported. Every configured template
 * is offered in the drawer, and warning about ones nobody touched would bury the real gaps.
 */
export function sharedRequiredGaps(procedures, engagedLabels, sharedValues, labelOf, missingOf) {
  const gaps = []
  for (const procedure of procedures || []) {
    const label = labelOf(procedure)
    if (!capturesPerProcedure(procedure) || !engagedLabels.has(label)) continue
    const missing = missingOf(procedure, sharedValues[label] || {})
    if (missing.length) gaps.push({ procedure: label, missing })
  }
  return gaps
}
