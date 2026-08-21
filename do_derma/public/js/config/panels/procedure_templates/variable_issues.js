import { variableFieldname } from "../../../shared/variable_fieldname.js"

/** What the chart will store a variable under. A row the server already knows keeps its
 * fieldname when it is relabelled - `_validated_variable_rows` reads `fieldname` first, and
 * re-keying an existing variable would orphan every value already recorded under it. */
export function variableFieldnameOf(row) {
  return row.fieldname || variableFieldname(row.label)
}

/** The two things the server refuses, named here so the panel can say so before a save
 * fails: the first pair of labels that collapse to one fieldname, and a blank label. */
export function variableIssues(rows = []) {
  const labels = {}
  let collision = null
  for (const row of rows) {
    const fieldname = variableFieldnameOf(row)
    if (!fieldname) continue
    if (labels[fieldname] && !collision) {
      collision = { first: labels[fieldname], second: row.label, fieldname }
    }
    labels[fieldname] = row.label
  }
  return {
    collision,
    hasBlankLabel: rows.some((row) => !variableFieldnameOf(row)),
  }
}
