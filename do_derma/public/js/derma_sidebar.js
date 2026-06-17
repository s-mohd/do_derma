(() => {
	if (typeof frappe !== "undefined" && frappe.provide) {
		frappe.provide("do_derma");
	} else {
		window.do_derma = window.do_derma || {};
	}

	const translate = (...args) => (typeof __ === "function" ? __(...args) : args[0]);

	do_derma.openChart = async function ({ patient } = {}) {
		const context = patient || window.doHealthSidebar?.getSelectedPatient?.() || window.do_health?.patientWatcher?.read?.();
		const patientId = context?.patient;
		if (!patientId) {
			frappe.msgprint(translate("Select a patient first."));
			return;
		}

		try {
			const { message } = await frappe.call({
				method: "do_derma.api.ensure_chart_context",
				args: {
					patient: patientId,
					appointment: context?.appointment,
					encounter: context?.encounter_name || context?.encounter,
				},
			});

			frappe.route_options = {
				patient: message?.patient || patientId,
				appointment: message?.appointment || context?.appointment,
				encounter: message?.encounter || context?.encounter_name || context?.encounter,
			};
			return { route: ["derma-chart"] };
		} catch (error) {
			console.warn("[do_derma] Failed to open chart", error);
			frappe.msgprint({
				title: translate("Derma Chart"),
				message: translate("Unable to open the dermatology chart."),
				indicator: "red",
			});
		}
	};
})();
