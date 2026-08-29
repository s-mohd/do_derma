/**
 * What a Clinical Procedure row is called in clinical columns. Its `title` leads with the
 * patient's name ("MONA ALHEJAILAN - Test1"), and every surface that shows a procedure
 * already names the patient elsewhere, so the template's own name comes first.
 */
export function procedureDisplayName(row = {}) {
  return String(row.template_label || row.procedure_template || row.title || row.name || "").trim()
}
