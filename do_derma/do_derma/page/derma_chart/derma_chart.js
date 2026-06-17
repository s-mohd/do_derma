frappe.pages["derma-chart"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Derma Chart"),
		single_column: true,
	});
};

frappe.pages["derma-chart"].on_page_show = function (wrapper) {
	load_derma_chart(wrapper);
};

function load_derma_chart(wrapper) {
	const $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	frappe.require(["derma_chart.bundle.css", "derma_chart.bundle.js"]).then(() => {
		wrapper.derma_chart = new frappe.ui.DermaChart({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
