import {Component} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {scanWithCamera} from "./camera_dialog.esm";
import {standardWidgetProps} from "@web/views/widgets/standard_widget_props";

/** Camera button placed in the status bar of the stock_barcodes scan screens. */
export class CameraScanButton extends Component {
    static template = "pl_barcode_camera.CameraScanButton";
    static props = standardWidgetProps;

    onClick() {
        scanWithCamera(this.env);
    }
}

registry.category("view_widgets").add("pl_barcode_camera_button", {
    component: CameraScanButton,
});
