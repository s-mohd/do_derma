import { createApp } from "vue"
import App from "./App.vue"

class DermaChart {
	constructor({ page, wrapper }) {
		this.$wrapper = $(wrapper)
		this.page = page
		this.setup_app()
	}

	setup_app() {
		this.app = createApp(App)
		this.vm = this.app.mount(this.$wrapper.get(0))
	}
}

frappe.provide("frappe.ui")
frappe.ui.DermaChart = DermaChart
export default DermaChart
