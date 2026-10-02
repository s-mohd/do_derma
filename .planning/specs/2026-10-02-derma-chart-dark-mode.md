# Derma chart: dark mode (phase 2c)

Status: agreed 2026-10-02.
Branch: `feat/derma-chart-dark-mode`, cut from `feat/derma-chart-panel-restyle`.
Builds on `.planning/specs/2026-10-01-derma-chart-panel-restyle.md` (2b).

## Goal

When desk runs in Dark, or in Automatic while the operating system is dark, the derma
chart follows, using the Patient Overview's dark palette. There are no light islands,
text stays readable, and the accent stays distinct from OK green. The annotation studio
and prints stay light.

## Decisions

| Topic | Decision |
|---|---|
| Trigger | `[data-theme="dark"]` on `<html>`, which desk sets for Dark and resolves live for Automatic. No chart toggle |
| Palette | do_health's dark `--ov-*` values, mapped to `--chart-*` |
| Annotation studio | Stays fully light: header, panels and canvas (Excalidraw dark mode would invert clinical images) |
| Prints | Stay light (separate window, inline styles) |
| Approach | Tokenise the stylesheet's literal colours, then redefine the tokens in one dark block |

## Where the tokens live

| Block | Selector | Purpose |
|---|---|---|
| Light tokens | `.dental-chart-page.derma-chart-page, .derma-annotation-modal, .modal` | Already in place (db7fbf6) |
| Dark tokens | `[data-theme="dark"] .dental-chart-page.derma-chart-page, [data-theme="dark"] .modal` | New. Excludes the studio on purpose |
| Desk variables pinned light | `[data-theme="dark"] .derma-annotation-modal` | Moved from the chart page to the studio only |

The chart page and the chart's desk dialogs go dark. The studio keeps the light tokens and
desk's light variables, so its desk controls stay light too.

## Dark palette

Every `--chart-*` token with an `--ov-*` twin takes do_health's dark value:
`--chart-bg #141414`, `--chart-surface #1e1e1e`, `--chart-surface-muted #262626`,
`--chart-text #f4f4f5`, and the translucent danger, caution, OK and info tints as declared on
`[data-theme="dark"] .do-health-drawer--overview`. A test pins each value to do_health's.

### Accent

| Token | Light | Dark |
|---|---|---|
| `--chart-accent` | `var(--do-health-header-accent, #16a34a)` | unchanged |
| `--chart-accent-strong` (filled buttons, white text) | accent 70% + black | unchanged |
| `--chart-accent-soft` (tints) | accent 10% + white | accent 18% + `--chart-surface` |
| `--chart-accent-text` (new; accent-coloured text on surfaces or tints) | `var(--chart-accent-strong)` | accent 70% + white |

Components and shared rules that colour **text** with `--chart-accent-strong` switch to
`--chart-accent-text`: the active tab, the tab tick, the avatar initials, accent and selected
pills, and the derma detail chip. Filled buttons keep `--chart-accent-strong`. Light mode is
unchanged because the two tokens are equal there.

### Desk variables and native controls

- The `[data-theme="dark"] .dental-chart-page.derma-chart-page { --alert-bg-…: … }` block
  that pinned desk's dark variables to light values is retargeted to
  `[data-theme="dark"] .derma-annotation-modal`. Desk controls inside the chart (link
  fields, the prescription grid) go dark with desk.
- `color-scheme: light` on the chart page becomes `light` by default and `dark` under
  `[data-theme="dark"]`, so scrollbars and native pickers follow.

## Stylesheet tokenisation

Scope: `derma_chart.bundle.css` outside the three token blocks.

- **Hex** (about 250): replaced by role through the 2b hex map, extended with the
  stylesheet's extra shades. Anything without a mapping is listed and decided by role in the
  commit body.
- **`background: white` / `#fff`**: becomes `var(--chart-surface)`.
- **`color: white`**: stays (text on filled buttons, white in both themes).
- **Translucent white `rgba(255, 255, 255, a)`** used as a fill: becomes
  `color-mix(in srgb, var(--chart-surface) a%, transparent)`.
- **Navy `rgba(15, 23, 42, a)` shadows**: stay.
- **JavaScript colours stay**: print HTML in `DermaChart.vue` (separate window) and the
  waveform canvas fallback in `VoiceWaveform.vue`.

Light mode: nearest-token mapping may shift shades slightly. Before committing, compare
computed styles of every element in light mode against the previous build and review the
whole list of changed colours.

## Out of scope

- Excalidraw dark mode or any change to `annotation/**`
- Print templates and print HTML
- The early-closing `@media` bug in `derma_chart.bundle.css`
- Any do_health change

## Testing

Source tests in `do_derma/tests/test_chart_theme.py`:
- every dark `--ov-*` value has a matching `--chart-*` in the dark block
- the dark block covers the chart page and `.modal` and not `.derma-annotation-modal`
- desk variables are pinned light on `.derma-annotation-modal` only
- white on `--chart-accent-strong`, and `--chart-accent-text` on the dark surface, reach
  4.5:1 for `#16a34a` and `#EC864B`
- no hex in the stylesheet outside the three token blocks; components already carry none
- `TestChartDarkMode` (which asserted light-only) and
  `test_chart_tokens_are_not_overridden_in_dark_mode` are replaced by the above

Browser:
- **Light unchanged**: computed-style comparison against the pre-2c build, every changed
  colour reviewed
- **Dark, light-island check**: each tab, the materials editor, the consent dialog and each
  chart desk dialog at 1280 and 1600. A script lists elements in the chart page or a chart
  dialog whose background is near-white under dark, excluding images and the studio.
  Target: none
- **Studio** under dark: header, buttons and canvas light
- **Accent**: site orange and a temporary purple; OK green stays green in both themes;
  restore the site's original colour
- **Automatic**: desk on Automatic, OS appearance toggled, chart follows live

Suite: diff against `main`'s baseline failures; fresh whole-branch review at the end.
