import logging
import datetime, pytz
from typing import Dict, List
from odoo import models, fields, api, exceptions
from . import enums
from ..utils import pay_utils


_logger = logging.getLogger(__name__)


class AdditionalRecord(models.Model):
    _name = 'additional.record'
    _description = '补单记录'
    _inherit = ['loan.basic.model']
    _table = 'F_additional_record'
    _order = 'apply_time desc'

    order_id = fields.Many2one('loan.order', string="财务订单", required=True, index=True, auto_join=True)
    repay_order_id = fields.Many2one('repay.order', string="还款订单", required=True, index=True, auto_join=True)
    order_no = fields.Char(string='订单编号', related="order_id.order_no")
    order_user_id = fields.Integer('UserID', related='order_id.loan_uid')
    order_user_name = fields.Char(string='姓名', related='order_id.loan_user_name')
    order_user_phone = fields.Char(string='手机号码', related="order_id.loan_user_phone")
    product_id = fields.Many2one('loan.product', string='产品名称', related="order_id.product_id")
    # order_apply_time = fields.Datetime(string='申请时间', related="order_id.apply_time")
    order_contract_amount = fields.Float(string='合同金额', related="order_id.contract_amount")

    addition_type = fields.Selection(enums.ADDITION_TYPE, string="业务类型", default='1')
    status = fields.Selection(enums.ADDITION_STATUS, string="状态", required=True)
    is_process = fields.Boolean('是否已处理', compute="_compute_is_process")
    
    utr = fields.Char('UTR', required=True)
    amount = fields.Float('补单金额')
    apply_time = fields.Datetime('申请时间', required=True, default=fields.Datetime.now)
    apply_user_id = fields.Many2one('res.users', string="申请人", default=lambda self: self.env.user)
    
    approval_user_id = fields.Many2one('res.users', string="审核人")
    approval_time = fields.Datetime('审核时间')
    close_reason_id = fields.Many2one('additional.record.close.reason', string='关单原因')

    payment_setting_id = fields.Many2one('payment.setting', string='支付渠道', domain="[('use_type', '=', '2')]")
    platform_order_no = fields.Char(string='支付订单号')
    merchant_order_no = fields.Char(string='支付ID')
    update_time = fields.Datetime('支付完成时间', default=fields.Datetime.now)

    attachment_id = fields.Many2one(
		'ir.attachment',
		'凭证图片',
		compute="_compute_attachment_id",
		store=True
	)
    voucher_img = fields.Image(string='凭证')

    @api.depends('status')
    def _compute_is_process(self):
        for record in self:
            record.is_process = False if record.status == '1' else True
    
    @api.depends('voucher_img')
    def _compute_attachment_id(self):
        for record in self:
            record.attachment_id = None
            if record.voucher_img:
                attachment_id = self.env['ir.attachment'].search([("res_model", "=", "additional.record"), ("res_id", "=", record.id), ('res_field', '=', 'voucher_img')], limit=1)
                if attachment_id:
                    record.attachment_id = attachment_id.id
    
    @api.model
    def create(self, vals):
        if vals.get('addition_type') == "2":
            order = self.env['loan.order'].search([('id', '=', vals.get('order_id'))])
            if not order._check_order_can_extension():
                raise exceptions.ValidationError('该订单不能进行展期补单')
                return
            
        if vals.get('amount') <= 0:
            raise exceptions.ValidationError('补单金额必须大于0')
        
        vals['status'] = '1'
        obj = super(AdditionalRecord, self).create(vals)
        return obj
    
    def action_show_additional_record(self):
        return {
            'name': '补单记录',
            'type': 'ir.actions.act_window',
            'res_model': "repay.order",
            'res_id': self.repay_order_id.id,
            'view_mode': 'form',
            'view_id': self.env.ref('loan_financial.form_order_additional_record').id,
            'target': 'new',
            'context': {
            }
        }
    
    def action_show_update_payment_setting(self):
        """
        审核通过-选择支付渠道
        """
        return {
            'name': '审核通过',
            'type': 'ir.actions.act_window',
            'res_model': "additional.record",
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('loan_financial.form_additional_record_pass').id,
            'target': 'new',
            'context': {
                'dialog_size': self._action_default_size(), 
            }
        }
    
    def call_pay_handler(self):
        """
        调用补单接口
        """
        trade_no = self.env['ir.sequence'].next_by_code('trade_record_no_seq')
        now = fields.Datetime.now()

        payment_channel_id = self.payment_setting_id.payment_channel_id
        trade_status = "3"
        if payment_channel_id.enum_code == 1:
            data = pay_utils.sf_pay.create_supplement_order({
                "merchantNo": payment_channel_id.merchant_no,
                'key': payment_channel_id.merchant_key,
                "orderNo": trade_no,
                "utr": self.utr,
                "timestamp": datetime.datetime.now().astimezone(tz=pytz.timezone( 'Asia/Kolkata' )).strftime('%Y-%m-%d %H:%M:%S'),
            })
            if data.get('code') == 0 and data.get('budanResult') == "succ":
                trade_status = "2"
            
        else:
            data = pay_utils.coin_pay.create_supplement_order({
                'mchId': int(payment_channel_id.merchant_no),
                'key': payment_channel_id.merchant_key,
                'mchOrderNo': trade_no,
                'utr': self.utr
            })
            if data['code'] == 200:
                trade_status = "2"

        # 创建交易记录
        trade_data = {
            'order_id': self.order_id.id,
            'payment_setting_id': self.payment_setting_id.id,
            # 'payment_way_id': self.order_id.repayment_way_id.id,
            'trade_amount': self.amount,
            'trade_no': trade_no,
            'trade_status': trade_status,
            'trade_type': '1',
            'trade_start_time': now,
            'trade_end_time': now,
            'platform_order_no': "",
            'trade_data': data,
            'res_model': self._name,
            'res_id': self.id
        }
        trade_record = self.env['payment.setting.trade.record'].create(trade_data)
        if trade_record.trade_status == "3":
            return
        
        if self.addition_type == '1':
            self.repay_order_id.after_payment(trade_record)
        else:
            self.env["extension.record"].update_or_create_from_additional(trade_record)

    def action_approval_pass(self):
        """
        审核通过
        1. 根据商户id(从产品获取),utr,对接支付接口，获取商户订单号(支付订单号)
        2. 调用补单接口(传“商户ID”、“支付订单号”)执行补单，等待补单回调结果
        3. 模拟回调
        """
        self.write({
            'status': '2',
            'approval_user_id': self.env.user.id,
            'approval_time': fields.Datetime.now()
        })
        self.call_pay_handler()

    def action_show_close_record(self):
        """
        打开选择关单原因界面
        """
        return {
            'name': '关闭补单申请',
            'type': 'ir.actions.act_window',
            'res_model': "additional.record",
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('loan_financial.form_additional_record_close').id,
            'target': 'new',
            'context': {
                'dialog_size': self._action_default_size(), 
            }
        }

    def action_close_record(self):
        """
        确认关闭记录
        """
        self.write({
            'status': '4',
            'approval_user_id': self.env.user.id,
            'approval_time': fields.Datetime.now()
        })
        
    def action_test_pay(self):
        """
        模拟支付补单费用
        """
        self.write({
            'status': '2',
            'approval_user_id': self.env.user.id,
            'approval_time': fields.Datetime.now()
        })

        trade_no = self.env['ir.sequence'].next_by_code('trade_record_no_seq')
        now = fields.Datetime.now()
        # 创建交易记录
        trade_data = {
            'order_id': self.order_id.id,
            'payment_setting_id': self.payment_setting_id.id,
            # 'payment_way_id': self.order_id.repayment_way_id.id,
            'trade_amount': self.amount,
            'trade_no': trade_no,
            'trade_status': "2",
            'trade_type': '1',
            'trade_start_time': now,
            'trade_end_time': now,
            'platform_order_no': "",
            'trade_data': {},
            'res_model': self._name,
            'res_id': self.id
        }
        trade_record = self.env['payment.setting.trade.record'].create(trade_data)
        
        if self.addition_type == '1':
            self.repay_order_id.after_payment(trade_record)
        else:
            self.env["extension.record"].update_or_create_from_additional(trade_record)


class AdditionalRecordCloseReason(models.Model):
    _name = 'additional.record.close.reason'
    _description = '补单关闭原因'
    _inherit = ['loan.basic.model']
    _table = 'F_additional_record_close_reason'
    _rec_name = 'text'
    _order = 'sequence'
    
    text = fields.Char(string='原因')
    sequence = fields.Integer(string='排序', default=0)
    



