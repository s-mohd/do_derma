# E2E tests

Playwright browser tests for the Derma Chart desk page. The layout is a port of
[bwhtech/hive](https://github.com/bwhtech/hive)'s harness (`playwright.config.ts`
at the app root, `e2e/{tests,helpers,pages}`, an `auth.setup.ts` project, and an
`e2e_seed.py` run through `bench execute`).

## Running

From `apps/do_derma`, with the bench running:

```bash
# once per site: plant the E2E fixtures (idempotent)
bench --site dermaone.localhost execute do_derma.e2e_seed.setup_e2e_data

# once per machine
yarn install
npx playwright install chromium

yarn test:e2e            # headless
yarn test:e2e:headed     # watch it drive the browser
yarn test:e2e:ui         # Playwright UI mode
yarn test:e2e:debug      # step through
```

Rebuild the bundles after touching anything under `public/js/`, or the
`data-test` hooks the specs select on will be stale:

```bash
bench build --app do_derma
```

## Environment

Defaults target this bench; override for another site.

| Variable | Default | Used for |
|---|---|---|
| `SITE_HOST` | `dermaone.localhost:8002` | the `Host` header on API calls |
| `BASE_URL` | `http://dermaone.localhost:8002` | browser navigation |
| `API_BASE` | `http://127.0.0.1:8002` | the `request` fixture |
| `FRAPPE_USER` | `Administrator` | login |
| `FRAPPE_PASSWORD` | `admin` | login |

## Three things that will bite you

1. **Two base URLs, on purpose.** Node cannot resolve `.localhost` TLDs, so API
   calls go to `127.0.0.1` with an explicit `Host` header while the browser uses
   Chromium's `--host-resolver-rules`. That is also why `helpers/frappe.ts`
   attaches cookies and the CSRF token by hand instead of relying on the
   `request` fixture's cookie jar.

2. **Never wait on `networkidle`.** The Vue bundle is loaded lazily by
   `frappe.require` inside `on_page_show`, and the desk holds long-poll sockets
   open forever. Wait for a `data-test` element instead — `ChartPage.open()`
   does this once so specs don't have to.

3. **The chart does not always open on "Clinical Notes".** The active section is
   persisted (localStorage plus Frappe user settings), so set it explicitly with
   `ChartPage.setSection()` rather than assuming a default.

## Layout

```
e2e/
  helpers/
    frappe.ts   REST + whitelisted-method wrappers (Host/CSRF/cookie plumbing)
    auth.ts     login / logout / session checks
    derma.ts    typed doctype shapes and the seed-fixture names
  pages/
    chart.page.ts   the /app/derma-chart page object
  tests/
    auth.setup.ts        logs in once, writes e2e/.auth/{user,csrf}.json
    chart-context.spec.ts
```

`e2e/.auth/` holds live session cookies and is gitignored. Never commit it.

## Fixtures

Everything `e2e_seed.py` creates is prefixed `E2E ` and is looked up by that
prefix from `helpers/derma.ts`. Nothing in the suite reads whatever rows happen
to exist — the dev site is a production clone with 40k+ patients.

Patient and Healthcare Practitioner use naming series, so they are resolved by
`first_name`, not by name. Consent Form Template does not autoname off `title`
either; `getSeedConsentTemplate()` handles that.
