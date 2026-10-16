import {_t} from "@web/core/l10n/translation";
import {Dialog} from "@web/core/dialog/dialog";
import {
    BarcodeVideoScanner,
    isBarcodeScannerSupported,
} from "@web/core/barcode/barcode_video_scanner";
import {Component, useState} from "@odoo/owl";

/**
 * Camera scan dialog: live preview with crop area, plus a text input to type
 * the barcode when the camera cannot read it.
 */
export class CameraScanDialog extends Component {
    static template = "pl_barcode_camera.CameraScanDialog";
    static components = {BarcodeVideoScanner, Dialog};
    static props = ["close", "onResult"];

    setup() {
        this.done = false;
        this.state = useState({
            supported: isBarcodeScannerSupported(),
            errorMessage: _t("Check your browser permissions"),
            manualBarcode: "",
        });
    }

    onResult(barcode) {
        // The video scanner keeps detecting until it unmounts: keep the first read.
        if (this.done || !barcode) {
            return;
        }
        this.done = true;
        this.props.close();
        this.props.onResult(barcode);
    }

    onError(error) {
        this.state.supported = false;
        this.state.errorMessage = error.message;
    }

    applyManual() {
        this.onResult(this.state.manualBarcode.trim());
    }

    onManualKeydown(ev) {
        if (ev.key === "Enter") {
            this.applyManual();
        }
    }
}

/**
 * Open the camera dialog and send the read barcode to the barcode service bus,
 * the same way a hardware scanner does.
 */
export function scanWithCamera(env) {
    env.services.dialog.add(CameraScanDialog, {
        onResult: (barcode) => {
            env.services.barcode.bus.trigger("barcode_scanned", {
                barcode,
                target: document.body,
            });
        },
    });
}
