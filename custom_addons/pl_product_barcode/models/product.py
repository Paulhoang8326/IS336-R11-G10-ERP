from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools.barcode import get_barcode_check_digit

# GS1 keeps prefixes 200-299 for in-store numbers, so these codes never clash
# with a manufacturer EAN printed on purchased goods.
EAN13_PREFIX = "200"
SEQUENCE_CODE = "pl_product_barcode.ean13"


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _pl_barcode_in_use(self, barcode):
        products = self.sudo().with_context(active_test=False)
        packagings = self.env["product.packaging"].sudo()
        return bool(
            products.search_count([("barcode", "=", barcode)], limit=1)
            or packagings.search_count([("barcode", "=", barcode)], limit=1)
        )

    def _pl_next_ean13(self):
        sequence = self.env["ir.sequence"].sudo()
        while True:
            number = sequence.next_by_code(SEQUENCE_CODE)
            if not number:
                raise UserError(_("Sequence %s is missing.", SEQUENCE_CODE))
            base = EAN13_PREFIX + number
            if len(base) != 12:
                raise UserError(_("The EAN-13 sequence has run out of numbers."))
            # get_barcode_check_digit ignores the last character: pad with 0.
            barcode = base + str(get_barcode_check_digit(base + "0"))
            if not self._pl_barcode_in_use(barcode):
                return barcode

    def action_pl_generate_barcode(self):
        for product in self:
            if product.barcode:
                raise UserError(
                    _("%s already has a barcode.", product.display_name)
                )
            product.barcode = product._pl_next_ean13()


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def action_pl_generate_barcode(self):
        for template in self:
            if template.product_variant_count != 1:
                raise UserError(
                    _(
                        "%s has several variants: generate the barcode on each "
                        "variant instead.",
                        template.display_name,
                    )
                )
        self.product_variant_ids.action_pl_generate_barcode()
