import logging
from odoo import models, fields, api, exceptions
from . import enums


_logger = logging.getLogger(__name__)


class DerateRecord(models.Model):
    _name = 'derate.record'
    _description = '减免记录'
    _inherit = ['loan.basic.model']
    _table = 'F_derate_record'

    order_id = fields.Many2one('loan.order', string="订单编号", required=True, index=True, auto_join=True)
    repay_order_id = fields.Many2one('repay.order', string="还款订单", required=True, index=True, auto_join=True)
    order_no = fields.Char(string='订单编号', related="order_id.order_no")
    loan_uid = fields.Integer('UserID', related='order_id.loan_uid')
    loan_user_name = fields.Char(string='姓名', related='order_id.loan_user_name')
    loan_user_phone = fields.Char(string='手机号码', related="order_id.loan_user_phone")
    app_id = fields.Many2one('loan.app', string='APP名称', related="order_id.app_id")
    app_version = fields.Char(string='APP版本', related="order_id.app_version")
    product_id = fields.Many2one('loan.product', string='产品名称', related="order_id.product_id")
    order_apply_time = fields.Datetime(string='申请时间', related="order_id.apply_time")
    order_status = fields.Selection(related="order_id.order_status", store=True, index=True)

    loan_cycle = fields.Char(string='期数', default="1/1")

    order_pending_amount = fields.Float(string='挂账金额')
    max_derate_amount = fields.Float(string='最大可减免金额') 

    derate_no = fields.Char(string='减免编号', required=True, index=True)
    derate_amount = fields.Float(string='减免金额', digits=(16, 2))
    apply_user_id = fields.Many2one('res.users', string='申请人')
    apply_reason = fields.Text(string='申请理由')
    apply_time = fields.Datetime(string='申请时间')
    derate_type = fields.Selection(selection=enums.DERATE_TYPE, string='减免类型')
    valid_time = fields.Datetime(string='有效期截止时间', index=True)
    is_effective = fields.Boolean(string='是否生效', default=False)

    col_approval_status = fields.Selection(selection=enums.DERATE_APPROVAL_STATUS, string='催收审核状态', default="0")
    col_approval_user_id = fields.Many2one('res.users', string='催收审核人员')
    col_approval_time = fields.Datetime(string='催收审核时间')
    col_approval_remark = fields.Text(string='催收备注')

    fin_approval_status = fields.Selection(selection=enums.DERATE_APPROVAL_STATUS, string='财务审核状态', default="0")
    fin_approval_user_id = fields.Many2one('res.users', string='财务审核人员')
    fin_approval_time = fields.Datetime(string='财务审核时间')
    fin_approval_remark = fields.Text(string='财务备注')

    @api.model
    def task_lose_efficacy(self):
        """
        定时任务, 将已过期的减免记录失效
        """
        now = fields.Datetime.now()
        platform_data = []
        for rec in self.search([('order_status', '=', '7'), ('valid_time', '<', now), ('derate_type', '=', '1'), ('is_effective', '=', True)]):
            rec.write({'is_effective': False})
            platform_data.append({
                "order_id": rec.order_id.id,
                "flow_type": enums.FLOW_TYPE[1][0],
                "flow_amount": rec.derate_amount,
                "trade_type": enums.TRADE_TYPE[21][0],
                "flow_time": now
            })
            rec.order_id.update_order_status(now)
        if platform_data:
            self.env['platform.flow'].create(platform_data)

    @api.model
    def _check_derate_data(self, data):
        """
        检查减免数据
        """
        errors = [] 
        derate_amount, max_derate_amount = data['derate_amount'], data['max_derate_amount']
        if derate_amount <= 0:
            errors.append('减免金额>0')

        if derate_amount > max_derate_amount:
            errors.append('减免金额≤最大可减免金额')
            
        if errors:
            raise exceptions.ValidationError(self.format_action_error(errors))

    @api.model
    def create(self, vals):
        self._check_derate_data(vals)

        order = self.env['loan.order'].browse(vals['order_id'])
        vals.update({
            "derate_no": self.env['ir.sequence'].next_by_code('derate_record_seq'),
            'app_version': order.app_version,
            'apply_user_id': self.env.user.id,
            'apply_time': fields.Datetime.now(),
            'fin_approval_status': "1"
        })
        return super(DerateRecord, self).create(vals)

    def action_show_approval_wizard(self):
        approve_flag = self.env.context.get('flag', 0)
        return {
            'name': '审核通过' if approve_flag else '审核拒绝',
            'type': 'ir.actions.act_window',
            'res_model': "derate.record.approval.wizard",
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'dialog_size': self._action_default_size(),
                'default_derate_id': self.id,
                'default_stage': '2',
                'default_status': "2" if approve_flag else "3",
                'default_desc': f"{self.derate_amount}, 否确定审核{'通过' if approve_flag else '拒绝'}?"
            }
        }


class DerateRecordApprovalWizard(models.TransientModel):
    _name = 'derate.record.approval.wizard'
    _description = '减免记录审核向导'
    _inherit = ['loan.basic.model']

    derate_id = fields.Many2one('derate.record', string="减免记录", required=True)
    stage = fields.Selection([('1', "催收审核"), ('2', "财务审核")], string='审核阶段')
    desc = fields.Text(string='审核描述')
    status = fields.Selection(enums.DERATE_APPROVAL_STATUS, '结论')
    remark = fields.Text(string='备注', required=True)
    user_id = fields.Many2one('res.users', string="审核人", default=lambda self: self.env.user.id)

    def create(self, vals):
        obj = super().create(vals)

        derate_rec_data = {}
        now = fields.Datetime.now()
        if obj.stage == '1':
            derate_rec_data.update({
                'col_approval_status': obj.status,
                'col_approval_user_id': self.env.user.id,
                'col_approval_time': now,
                'col_approval_remark': obj.remark,
            })
        else:
            derate_rec_data.update({
                'fin_approval_status': obj.status,
                'fin_approval_user_id': self.env.user.id,
                'fin_approval_time': now,
                'fin_approval_remark': obj.remark,
                'is_effective': True if obj.status == "2" else False
            })
            obj.derate_id.write(derate_rec_data)

            # 流水
            if obj.status == '2':
                self.env['platform.flow'].create({
                    "order_id": obj.derate_id.order_id.id,
                    "flow_type": enums.FLOW_TYPE[0][0],
                    "flow_amount": obj.derate_id.derate_amount,
                    "trade_type": enums.TRADE_TYPE[20][0],
                    "flow_time": now
                })
            
                obj.derate_id.repay_order_id.update_repay_status(now)
        return obj




