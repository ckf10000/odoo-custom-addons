import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

 
class LoanOrderSettings(models.TransientModel):
    _name = 'loan.order.settings'
    _description = '财务订单配置'
    _inherit = ['loan.basic.model']
    _table = 'F_loan_order_settings'

    key = fields.Char(string='key', required=True, index=True)
    value = fields.Char(string='value', required=True)
    
    @api.model
    def get_param(self, key, default=None):
        rec = self.search([('key', '=', key)], limit=1)
        return rec.value if rec else default
    
    @api.model
    def set_param(self, key, value):
        rec = self.search([('key', '=', key)], limit=1)
        if rec:
            rec.write({'value': value})
        else:
            self.create({'key': key, 'value': value})