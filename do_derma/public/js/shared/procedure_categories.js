/**
 * Groups derma procedure templates under the category the chart picks them by.
 * A template's `custom_derma_category` holds a Derma Procedure Category name, but
 * `_is_derma_template` in api.py also admits templates that carry no category at all,
 * so those land in an Uncategorised bucket instead of falling out of reach.
 */
export const UNCATEGORISED = "Uncategorised"

export function groupTemplatesByCategory(templates = [], categories = []) {
  const byCategory = new Map()
  for (const template of templates) {
    const key = matchCategory(template?.custom_derma_category, categories)?.name || UNCATEGORISED
    if (!byCategory.has(key)) byCategory.set(key, [])
    byCategory.get(key).push(template)
  }

  const named = categories
    .filter((category) => byCategory.has(category.name))
    .map((category) => ({
      value: category.name,
      label: category.title || category.name,
      templates: byCategory.get(category.name),
    }))
  const loose = byCategory.get(UNCATEGORISED)
  if (!loose) return named
  return [...named, { value: UNCATEGORISED, label: __("Uncategorised"), templates: loose }]
}

/** Categories are matched on name or title the way `categorySettings` in DermaChart.vue does. */
function matchCategory(category, categories) {
  if (!category) return null
  return categories.find((row) => row.name === category || row.title === category) || null
}
