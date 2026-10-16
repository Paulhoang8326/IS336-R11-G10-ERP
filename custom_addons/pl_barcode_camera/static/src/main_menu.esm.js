import {StockBarcodesMainMenu} from "@stock_barcodes/views/actions/stock_barcode_main_menu.esm";
import {patch} from "@web/core/utils/patch";
import {scanWithCamera} from "./camera_dialog.esm";

patch(StockBarcodesMainMenu.prototype, {
    openCameraScanner() {
        scanWithCamera(this.env);
    },
});
