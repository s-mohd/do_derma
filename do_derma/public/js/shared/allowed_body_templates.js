/** The body maps a procedure template may be charted on. Mirrors `_ensure_body_template_allowed`
 * in api.py, which is the gate: free text, comma-separated, case-insensitive, empty means
 * no restriction. A Derma Body Template autonames `field:title`, so its name is its title. */
export function allowedBodyTemplates(procedure) {
  return String(procedure?.custom_derma_allowed_body_templates || "")
    .split(",")
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean)
}

export function isBodyTemplateAllowed(procedure, bodyTemplateName) {
  const allowed = allowedBodyTemplates(procedure)
  return !allowed.length || allowed.includes(String(bodyTemplateName || "").toLowerCase())
}
