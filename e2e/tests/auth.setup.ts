import * as fs from "fs";
import * as path from "path";
import { expect, test as setup } from "@playwright/test";

const authFile = "e2e/.auth/user.json";
const csrfFile = "e2e/.auth/csrf.json";

/**
 * Authenticate once, before every other project.
 *
 * The login is issued from a browser `fetch()` rather than the `request`
 * fixture so the session cookie is stored against the site domain
 * (Chromium resolves it through --host-resolver-rules). The `request` fixture
 * talks to 127.0.0.1 and would scope the cookie to the wrong host.
 */
setup("authenticate", async ({ page }) => {
	const authDir = path.dirname(authFile);
	if (!fs.existsSync(authDir)) {
		fs.mkdirSync(authDir, { recursive: true });
	}

	const usr = process.env.FRAPPE_USER || "Administrator";
	const pwd = process.env.FRAPPE_PASSWORD || "admin";

	await page.goto("/login");
	await page.waitForLoadState("domcontentloaded");

	const loginResult = await page.evaluate(
		async ({ usr, pwd }) => {
			const resp = await fetch("/api/method/login", {
				method: "POST",
				headers: { "Content-Type": "application/x-www-form-urlencoded" },
				body: `usr=${encodeURIComponent(usr)}&pwd=${encodeURIComponent(pwd)}`,
			});
			return { ok: resp.ok, status: resp.status };
		},
		{ usr, pwd },
	);
	expect(loginResult.ok, `login returned ${loginResult.status}`).toBeTruthy();

	const loggedUser = await page.evaluate(async () => {
		const resp = await fetch("/api/method/frappe.auth.get_logged_user");
		const data = await resp.json();
		return data.message as string;
	});
	expect(loggedUser).toBeTruthy();
	expect(loggedUser).not.toBe("Guest");
	console.log(`Authenticated as: ${loggedUser}`);

	// The desk sets window.frappe.csrf_token; helpers/frappe.ts needs it for writes.
	await page.goto("/app", { waitUntil: "domcontentloaded" });
	await page
		.waitForFunction(
			() =>
				(window as unknown as { frappe?: { csrf_token?: string } }).frappe?.csrf_token !== undefined,
			{ timeout: 20_000 },
		)
		.catch(() => {
			console.warn("CSRF token not found, continuing without it");
		});

	const csrfToken = await page.evaluate(
		() => (window as unknown as { frappe?: { csrf_token?: string } }).frappe?.csrf_token,
	);

	if (csrfToken) {
		fs.writeFileSync(csrfFile, JSON.stringify({ csrf_token: csrfToken }));
	}

	await page.context().storageState({ path: authFile });
});
