frappe.ui.form.on("Clinical Procedure", {
	refresh(frm) {
		do_derma.setup_annotations_button?.(frm);
	},
	// A throwing refresh handler in another app aborts the chain before ours runs; this form
	// has one. onload_post_render is a separate trigger, so the button survives it.
	onload_post_render(frm) {
		do_derma.setup_annotations_button?.(frm);
	},
});
