import path from "path";
import { defineConfig, devices } from "@playwright/test";

const authFile = path.join(__dirname, "e2e", ".auth", "user.json");

// Frappe multisite routing keys off the Host header, but Node.js cannot resolve
// `.localhost` TLDs. So API calls (the `request` fixture) go to 127.0.0.1 with an
// explicit Host header, while browser navigations use Chromium's resolver rules.
const SITE_HOST = process.env.SITE_HOST || "dermaone.localhost:8002";
const SITE_NAME = SITE_HOST.split(":")[0];

const API_BASE = process.env.API_BASE || "http://127.0.0.1:8002";
const PAGE_BASE = process.env.BASE_URL || `http://${SITE_HOST}`;

export { API_BASE, PAGE_BASE, SITE_HOST };

export default defineConfig({
	testDir: "./e2e/tests",
	// The seeded fixtures are shared across specs and are not safe to race.
	fullyParallel: false,
	workers: 1,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	// Generous: EmbeddedExcalidraw.jsx dynamically import()s Excalidraw at runtime.
	timeout: 90_000,
	expect: {
		timeout: 15_000,
	},
	reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "html",

	use: {
		baseURL: PAGE_BASE,
		trace: "on-first-retry",
		video: "retain-on-failure",
		screenshot: "only-on-failure",
		actionTimeout: 20_000,
		navigationTimeout: 45_000,
		launchOptions: {
			args: [`--host-resolver-rules=MAP ${SITE_NAME} 127.0.0.1`],
		},
	},

	projects: [
		{
			name: "setup",
			testMatch: "**/auth.setup.ts",
		},
		{
			name: "chromium",
			use: { ...devices["Desktop Chrome"], storageState: authFile },
			dependencies: ["setup"],
		},
	],
});
