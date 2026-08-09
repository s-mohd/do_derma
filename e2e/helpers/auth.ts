import { APIRequestContext, Page } from "@playwright/test";

/**
 * Login through the Frappe API. Faster than the UI, and enough for the
 * `request` fixture.
 */
export async function loginViaAPI(
	request: APIRequestContext,
	email = "Administrator",
	password = "admin",
): Promise<void> {
	const response = await request.post("/api/method/login", {
		form: { usr: email, pwd: password },
	});

	if (!response.ok()) {
		throw new Error(`Login failed: ${response.status()} ${await response.text()}`);
	}
}

/**
 * Login through the desk UI. Only for testing the login flow itself.
 */
export async function loginViaUI(
	page: Page,
	email = "Administrator",
	password = "admin",
): Promise<void> {
	await page.goto("/login");
	await page.waitForLoadState("domcontentloaded");

	await page.fill('input[data-fieldname="email"]', email);
	await page.fill('input[data-fieldname="password"]', password);
	await page.click('button[type="submit"]');

	await page.waitForURL(/\/(app|desk)/, { timeout: 30_000 });
}

/**
 * Log the current session out.
 */
export async function logout(page: Page): Promise<void> {
	await page.goto("/api/method/logout");
	await page.waitForLoadState("domcontentloaded");
}

/**
 * Whether the session is authenticated as a real user.
 */
export async function isLoggedIn(request: APIRequestContext): Promise<boolean> {
	try {
		const response = await request.get("/api/method/frappe.auth.get_logged_user");
		if (!response.ok()) return false;

		const data = await response.json();
		return Boolean(data.message) && data.message !== "Guest";
	} catch {
		return false;
	}
}
