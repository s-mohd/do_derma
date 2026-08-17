## Main Rules

- Whitelisted endpoints gate first, then reuse the `api.py` helpers instead of re-deriving context or schema checks.
- Group related files in folders instead of adding many same-prefix modules.
- Avoid lazy re-exports in package `__init__.py` when autocomplete matters.
- Keep comments short. Remove comments that restate the code.
- Do not put comments at the top of a file. Use a short, terse class or method docstring instead.

## Code Taste

These rules are mandatory for agents changing this repo:

- Choose clean code over clever code.
- Prefer explicit config over implicit behavior.
- Prefer object-oriented code where it maps to the domain.
- Keep functions small. Around 25 lines is a useful target, not a reason to split readable code blindly.
- Keep cyclomatic complexity <= 8
- Keep files 800 lines max when practical. `api.py` (3.5k), `DermaChart.vue` (2.8k), `ProcedurePanel.vue` (2.5k) and `EmbeddedExcalidraw.jsx` (1.3k) are sanctioned exceptions: the limit binds new files, so do not split those four opportunistically.
- Avoid crowded modules. If a folder grows too large, group related files into a subfolder instead of adding more same-prefix files.
- Avoid abbreviations.
- Use standard APIs and existing repo helpers before adding custom logic.
- Reuse existing patterns. Write as little new code as the change needs.
- Delete before adding when existing code can be simplified.
- Always add or update tests for behavior changes, and make sure they pass.
- Build the minimum working change, then iterate.
- Keep comments and docstrings terse. Explain only what the code does not already make obvious.
- Put detailed change explanation in commit messages or docs, not inline comments.
- Keep one owner for state that can drift out of sync.
- Keep state scoped. Do not let temporary state leak across object or module boundaries.
- Fail loudly near the bug. Do not hide corrupt or partial state behind broad fallbacks.
- Retry only operations that are safe to repeat.
- For a no-argument method that computes and returns one noun-like value, use `@property`.
- For methods with arguments or multi-step work, prefer `get_<what_it_returns>()`, such as `get_chart_context()`.
- Default to public methods. Use a leading underscore only for raw parsing, security-sensitive validation, OS plumbing, or genuinely internal details callers should not reach for.
- Do not make a method private just because it currently has one caller.
- Do not split code into more helpers than necessary. A single-use one-liner usually reads better inline.
- Name boolean-returning properties and methods with `is_` or `has_`, such as `_has_doctype` or `_has_field`.

## Implementation Guidelines
* Create a new branch before working on a new feature/spec (branch name patterns: feat/, fix/, just like conventional commit pre-fixes)
