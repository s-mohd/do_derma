import * as fs from "fs";
import { APIRequestContext } from "@playwright/test";

/**
 * Frappe API response envelope.
 */
export interface FrappeResponse<T = unknown> {
	message?: T;
	exc?: string;
	exc_type?: string;
	_server_messages?: string;
}

// Written by e2e/tests/auth.setup.ts.
const CSRF_FILE = "e2e/.auth/csrf.json";
const AUTH_FILE = "e2e/.auth/user.json";

// Node.js cannot resolve `.localhost` TLDs, so API calls go via 127.0.0.1 and
// carry the Host header Frappe's multisite router needs.
const SITE_HOST = process.env.SITE_HOST || "dermaone.localhost:8002";
export const API_BASE = process.env.API_BASE || "http://127.0.0.1:8002";

let csrfTokenCache: string | null = null;
let cookieCache: string | null = null;

/**
 * Read the CSRF token captured during auth setup.
 */
function getCsrfToken(): string {
	if (csrfTokenCache !== null) {
		return csrfTokenCache;
	}

	try {
		if (fs.existsSync(CSRF_FILE)) {
			const data = JSON.parse(fs.readFileSync(CSRF_FILE, "utf-8"));
			csrfTokenCache = data.csrf_token || "";
			return csrfTokenCache;
		}
	} catch (error: unknown) {
		console.warn("Failed to read CSRF token file:", error);
	}

	csrfTokenCache = "";
	return "";
}

/**
 * Read auth cookies from the storage state file. The `request` fixture talks to
 * 127.0.0.1 while the cookies are scoped to the site domain, so they are not
 * sent automatically and must be attached by hand.
 */
function getAuthCookies(): string {
	if (cookieCache !== null) {
		return cookieCache;
	}

	try {
		if (fs.existsSync(AUTH_FILE)) {
			const data = JSON.parse(fs.readFileSync(AUTH_FILE, "utf-8"));
			const cookies = data.cookies as Array<{ name: string; value: string }> | undefined;
			if (cookies?.length) {
				cookieCache = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
				return cookieCache;
			}
		}
	} catch (error: unknown) {
		console.warn("Failed to read auth cookies file:", error);
	}

	cookieCache = "";
	return "";
}

/**
 * Common headers for every API request: Host + CSRF + session cookies.
 */
function apiHeaders(extra: Record<string, string> = {}): Record<string, string> {
	const csrfToken = getCsrfToken();
	const cookies = getAuthCookies();
	return {
		Host: SITE_HOST,
		...(csrfToken ? { "X-Frappe-CSRF-Token": csrfToken } : {}),
		...(cookies ? { Cookie: cookies } : {}),
		...extra,
	};
}

/**
 * Create a document via the Frappe REST API.
 */
export async function createDoc<T = Record<string, unknown>>(
	request: APIRequestContext,
	doctype: string,
	doc: Record<string, unknown>,
): Promise<T> {
	const response = await request.post(`${API_BASE}/api/resource/${encodeURIComponent(doctype)}`, {
		data: doc,
		headers: apiHeaders({ "Content-Type": "application/json" }),
	});

	if (!response.ok()) {
		throw new Error(`Failed to create ${doctype}: ${await response.text()}`);
	}

	const result = await response.json();
	return result.data as T;
}

/**
 * Fetch a document by name.
 */
export async function getDoc<T = Record<string, unknown>>(
	request: APIRequestContext,
	doctype: string,
	name: string,
): Promise<T> {
	const response = await request.get(
		`${API_BASE}/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`,
		{ headers: apiHeaders() },
	);

	if (!response.ok()) {
		throw new Error(`Failed to get ${doctype}/${name}: ${await response.text()}`);
	}

	const result = await response.json();
	return result.data as T;
}

/**
 * Update a document.
 */
export async function updateDoc<T = Record<string, unknown>>(
	request: APIRequestContext,
	doctype: string,
	name: string,
	updates: Record<string, unknown>,
): Promise<T> {
	const response = await request.put(
		`${API_BASE}/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`,
		{
			data: updates,
			headers: apiHeaders({ "Content-Type": "application/json" }),
		},
	);

	if (!response.ok()) {
		throw new Error(`Failed to update ${doctype}/${name}: ${await response.text()}`);
	}

	const result = await response.json();
	return result.data as T;
}

/**
 * Delete a document.
 */
export async function deleteDoc(
	request: APIRequestContext,
	doctype: string,
	name: string,
): Promise<void> {
	const response = await request.delete(
		`${API_BASE}/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`,
		{ headers: apiHeaders() },
	);

	if (!response.ok()) {
		throw new Error(`Failed to delete ${doctype}/${name}: ${await response.text()}`);
	}
}

/**
 * Call a whitelisted method and return its `message` payload.
 */
export async function callMethod<T = unknown>(
	request: APIRequestContext,
	method: string,
	args: Record<string, unknown> = {},
): Promise<T> {
	const response = await request.post(`${API_BASE}/api/method/${method}`, {
		data: args,
		headers: apiHeaders({ "Content-Type": "application/json" }),
	});

	if (!response.ok()) {
		throw new Error(`Failed to call ${method}: ${await response.text()}`);
	}

	const result: FrappeResponse<T> = await response.json();
	return result.message as T;
}

/**
 * Call a whitelisted method without throwing, so a spec can assert on the
 * failure itself (used by clinical-access.spec.ts).
 */
export async function callMethodRaw(
	request: APIRequestContext,
	method: string,
	args: Record<string, unknown> = {},
): Promise<{ status: number; ok: boolean; body: string }> {
	const response = await request.post(`${API_BASE}/api/method/${method}`, {
		data: args,
		headers: apiHeaders({ "Content-Type": "application/json" }),
		failOnStatusCode: false,
	});

	return {
		status: response.status(),
		ok: response.ok(),
		body: await response.text(),
	};
}

/**
 * List documents.
 */
export async function getList<T = Record<string, unknown>>(
	request: APIRequestContext,
	doctype: string,
	options: {
		fields?: string[];
		filters?: Record<string, unknown> | unknown[][];
		limit?: number;
		orderBy?: string;
	} = {},
): Promise<T[]> {
	const params = new URLSearchParams();

	if (options.fields) {
		params.set("fields", JSON.stringify(options.fields));
	}
	if (options.filters) {
		params.set("filters", JSON.stringify(options.filters));
	}
	if (options.limit) {
		params.set("limit_page_length", options.limit.toString());
	}
	if (options.orderBy) {
		params.set("order_by", options.orderBy);
	}

	const response = await request.get(
		`${API_BASE}/api/resource/${encodeURIComponent(doctype)}?${params.toString()}`,
		{ headers: apiHeaders() },
	);

	if (!response.ok()) {
		throw new Error(`Failed to list ${doctype}: ${await response.text()}`);
	}

	const result = await response.json();
	return result.data as T[];
}

/**
 * Check whether a document exists.
 */
export async function docExists(
	request: APIRequestContext,
	doctype: string,
	name: string,
): Promise<boolean> {
	try {
		await getDoc(request, doctype, name);
		return true;
	} catch {
		return false;
	}
}
