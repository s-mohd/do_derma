import { APIRequestContext } from "@playwright/test";
import { callMethod, deleteDoc, getList, updateDoc } from "./frappe";

// ---------------------------------------------------------------------------
// Document shapes. Each doctype is labelled with the app that owns it, because
// half of what the chart reads lives in other apps.
// ---------------------------------------------------------------------------

/** do_derma. Position is stored as x_percent / y_percent (Float, both reqd). */
export interface DermaChartMark {
	name: string;
	patient: string;
	encounter?: string;
	appointment?: string;
	x_percent: number;
	y_percent: number;
	body_template?: string;
	procedure_template?: string;
	clinical_procedure?: string;
	annotation?: string;
	annotation_json?: string;
	marker_behavior?: string;
	status?: string;
}

/** healthcare */
export interface PatientEncounter {
	name: string;
	patient: string;
	docstatus: 0 | 1 | 2;
}

/** healthcare */
export interface ClinicalProcedure {
	name: string;
	patient: string;
	procedure_template?: string;
	status?: string;
}

/** do_health */
export interface HealthAnnotation {
	name: string;
	annotation_json?: string;
}

/**
 * do_derma.api.ensure_chart_context - the flat id triple, and what the chart
 * page accepts as query params.
 */
export interface ChartContext {
	patient?: string;
	appointment?: string;
	encounter?: string;
}

/**
 * do_derma.api.get_chart_context returns something different: `patient` is the
 * full Patient dict, and the ids live under `*_id` (see api.py `_get_visit_context`).
 */
export interface ResolvedChartContext {
	patient_id: string;
	appointment_id: string | null;
	encounter_id: string | null;
	patient: { name: string; patient_name?: string; sex?: string } | null;
	marks: DermaChartMark[];
	body_templates: Array<Record<string, unknown>>;
	procedure_templates: Array<Record<string, unknown>>;
}

// ---------------------------------------------------------------------------
// Seed fixtures. These names are the contract with do_derma/e2e_seed.py.
// ---------------------------------------------------------------------------

export const E2E_PREFIX = "E2E ";

export const SEED = {
	patientFirstName: "E2E Derma Patient",
	practitionerFirstName: "E2E Derma Practitioner",
	appointmentType: "E2E Derma Visit",
	procedureCategory: "E2E Injectables",
	pointTemplate: "E2E Filler",
	areaTemplate: "E2E Area Peel",
	freehandTemplate: "E2E Freehand Graft",
	bodyTemplate: "E2E Face Map",
	bodyParts: ["E2E Left Cheek", "E2E Right Cheek"],
	consentTitle: "E2E Consent",
	noAccessEmail: "e2e-no-access@example.com",
	noAccessPassword: "admin",
} as const;

const SEED_MISSING =
	"E2E fixtures are missing. Run:\n" +
	"  bench --site dermaone.localhost execute do_derma.e2e_seed.setup_e2e_data";

/**
 * Resolve the seeded Patient. Patient and Healthcare Practitioner use naming
 * series, so they are looked up by first_name rather than by name.
 */
export async function getSeedPatient(request: APIRequestContext): Promise<string> {
	const rows = await getList<{ name: string }>(request, "Patient", {
		fields: ["name"],
		filters: { first_name: SEED.patientFirstName },
		limit: 1,
	});

	if (!rows.length) throw new Error(`${SEED_MISSING}\n(no Patient "${SEED.patientFirstName}")`);
	return rows[0].name;
}

/** Resolve the seeded Healthcare Practitioner. */
export async function getSeedPractitioner(request: APIRequestContext): Promise<string> {
	const rows = await getList<{ name: string }>(request, "Healthcare Practitioner", {
		fields: ["name"],
		filters: { first_name: SEED.practitionerFirstName },
		limit: 1,
	});

	if (!rows.length) throw new Error(`${SEED_MISSING}\n(no Healthcare Practitioner)`);
	return rows[0].name;
}

/**
 * Resolve the seeded Consent Form Template. It does not autoname off `title`
 * (the row is named e.g. "E2E Consent--"), so it must be found by field.
 * Returns null when the doctype or the fixture is absent, so consents.spec.ts
 * can skip itself instead of failing.
 */
export async function getSeedConsentTemplate(request: APIRequestContext): Promise<string | null> {
	try {
		const rows = await getList<{ name: string }>(request, "Consent Form Template", {
			fields: ["name"],
			filters: { title: SEED.consentTitle },
			limit: 1,
		});
		return rows[0]?.name ?? null;
	} catch {
		return null;
	}
}

/**
 * Resolve the seeded Clinical Procedure and the encounter it hangs off. The chart
 * only lists procedures for the encounter it was opened on, so a spec that needs a
 * procedure row must open on this encounter rather than on whatever draft
 * `ensureChartContext` happens to return.
 */
export async function getSeedClinicalProcedure(
	request: APIRequestContext,
	patient: string,
): Promise<{ name: string; encounter: string | null }> {
	const rows = await getList<{ name: string; custom_patient_encounter?: string }>(
		request,
		"Clinical Procedure",
		{
			fields: ["name", "custom_patient_encounter"],
			filters: { patient, procedure_template: SEED.pointTemplate },
			limit: 1,
		},
	);

	if (!rows.length) throw new Error(`${SEED_MISSING}\n(no Clinical Procedure for "${SEED.pointTemplate}")`);
	return { name: rows[0].name, encounter: rows[0].custom_patient_encounter ?? null };
}

// ---------------------------------------------------------------------------
// Chart context
// ---------------------------------------------------------------------------

/**
 * Back-fill the patient/appointment/encounter triple, creating a draft
 * Patient Encounter when there isn't one (do_derma.api._ensure_encounter).
 */
export async function ensureChartContext(
	request: APIRequestContext,
	patient: string,
): Promise<ChartContext> {
	return callMethod<ChartContext>(request, "do_derma.api.ensure_chart_context", { patient });
}

export async function getChartContext(
	request: APIRequestContext,
	context: ChartContext,
): Promise<ResolvedChartContext> {
	return callMethod<ResolvedChartContext>(request, "do_derma.api.get_chart_context", { ...context });
}

/**
 * A private draft encounter for one spec, so a spec that mutates or submits an
 * encounter cannot poison the next one.
 */
export async function freshEncounter(
	request: APIRequestContext,
	patient: string,
): Promise<PatientEncounter> {
	const practitioner = await getSeedPractitioner(request);

	return callMethod<PatientEncounter>(request, "frappe.client.insert", {
		doc: {
			doctype: "Patient Encounter",
			patient,
			appointment_type: SEED.appointmentType,
			practitioner,
			encounter_date: new Date().toISOString().slice(0, 10),
			status: "Open",
		},
	});
}

// ---------------------------------------------------------------------------
// Chart marks
// ---------------------------------------------------------------------------

export const MARK_FIELDS = [
	"name",
	"patient",
	"encounter",
	"appointment",
	"x_percent",
	"y_percent",
	"body_template",
	"procedure_template",
	"clinical_procedure",
	"annotation",
	"annotation_json",
	"marker_behavior",
	"status",
];

/**
 * do_derma.api.save_chart_mark. It back-fills the visit context, so a mark can be
 * planted on an encounter without knowing its appointment.
 */
export async function saveMark(
	request: APIRequestContext,
	values: Partial<DermaChartMark> & { patient: string },
): Promise<DermaChartMark> {
	return callMethod<DermaChartMark>(request, "do_derma.api.save_chart_mark", {
		values: { x_percent: 50, y_percent: 50, ...values },
	});
}

export async function listMarks(
	request: APIRequestContext,
	filters: Record<string, unknown>,
): Promise<DermaChartMark[]> {
	return getList<DermaChartMark>(request, "Derma Chart Mark", {
		fields: MARK_FIELDS,
		filters,
		limit: 100,
		orderBy: "creation asc",
	});
}

/**
 * Remove every mark on an encounter. Marks promoted to a Clinical Procedure are
 * deleted through the API endpoint so its own guards run.
 */
export async function cleanupMarks(request: APIRequestContext, encounter: string): Promise<void> {
	const marks = await listMarks(request, { encounter });

	for (const mark of marks) {
		try {
			await deleteDoc(request, "Derma Chart Mark", mark.name);
		} catch {
			// A mark linked to a submitted procedure may refuse deletion; leaving
			// it behind is harmless because every spec filters by its own encounter.
		}
	}
}

/** Drop a spec's draft encounter once it is done with it. */
export async function cleanupEncounter(request: APIRequestContext, encounter: string): Promise<void> {
	await cleanupMarks(request, encounter);
	try {
		await deleteDoc(request, "Patient Encounter", encounter);
	} catch {
		// Submitted or linked encounters stay; they are inert for later runs.
	}
}

// ---------------------------------------------------------------------------
// Derma Settings feature toggles (do_derma). They gate controls whose
// integration is unfinished, so every spec that flips one must flip it back.
// ---------------------------------------------------------------------------

export const FEATURE_TOGGLES = [
	"enable_whatsapp_consent",
	"enable_lab_cases",
	"enable_billing_sync",
] as const;

export type FeatureToggle = (typeof FEATURE_TOGGLES)[number];

export async function setFeatureToggle(
	request: APIRequestContext,
	toggle: FeatureToggle,
	enabled: boolean,
): Promise<void> {
	await updateDoc(request, "Derma Settings", "Derma Settings", { [toggle]: enabled ? 1 : 0 });
}

export async function resetFeatureToggles(request: APIRequestContext): Promise<void> {
	const off = Object.fromEntries(FEATURE_TOGGLES.map((toggle) => [toggle, 0]));
	await updateDoc(request, "Derma Settings", "Derma Settings", off);
}
