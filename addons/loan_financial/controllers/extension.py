# -*- coding: utf-8 -*-
import urllib
import logging
import datetime, pytz
from odoo import http, fields
from ..utils import pay_utils

_logger = logging.getLogger(__name__)


class PayController(http.Controller):

    @http.route('/finance/get_extension_detail', auth='public', csrf=False, type="json", methods=['POST'])
    def get_extension_detail(self, **kw):
        request = http.request
        data = request.get_json_data()
        order = request.env['loan.order'].sudo().search([('order_no', '=', data['order_no'])], limit=1)
        if not order:
            return {'extension_amount': 0, 'pending_amount': 0}
        extension_rec = request.env['extension.record'].sudo().search([('order_id', '=', order.id)], limit=1)
        if extension_rec:
            return {
                "extension_amount": extension_rec.extension_amount if extension_rec else 0,
                "pending_amount": extension_rec.pending_amount if extension_rec else 0,
            }
        extension_amount = order.compute_extension_amount()
        return {
            "extension_amount": extension_amount,
            "pending_amount": extension_amount
        }

    @http.route('/finance/apply_extension', auth='public', csrf=False, type="json", methods=['POST'])
    def apply_extension(self, **kw):
        request = http.request
        data = request.get_json_data()
        order = request.env['loan.order'].sudo().search([('order_no', '=', data['order_no'])], limit=1)

        # 获取或者创建展期记录
        extension = request.env['extension.record'].sudo().search([('order_id', '=', order.id), ("status", "not in", ["5", "6"])], limit=1)
        if not extension:
            extension = request.env['extension.record'].sudo().create({
                'order_id': order.id,
                'status': "1",
                'extension_days': order.loan_period,
                'extension_amount': order.compute_extension_amount(),
                'order_repay_date': order.repay_date,
            })

        # 创建交易记录
        payment_channel = order.repayment_setting_id.payment_channel_id
        trade_no = request.env['ir.sequence'].sudo().next_by_code('trade_record_no_seq')
        if payment_channel.enum_code == 2:
            data = {
                'mchId': int(payment_channel.merchant_no),
                'key': payment_channel.merchant_key,
                'mchOrderNo': trade_no,
                'orderAmount': int(extension.pending_amount * 100),
                'notifyUrl': payment_channel.call_back_url or "",
                'returnUrl': payment_channel.redirect_url or "",
                'device': data.get('device', 'android'),
                'uid': order.loan_uid,
                'customerName': order.loan_user_name,
                'tel': order.loan_user_phone
            }
            res = pay_utils.coin_pay.create_pay_order(data)
            pay_url = res.get('data', {}).get('payUrl')
        else:
            data = {
                'merchantNo': payment_channel.merchant_no,
                'key': payment_channel.merchant_key,
                'orderNo': trade_no,
                'amount': str(extension.pending_amount),
                'notifyUrl': payment_channel.call_back_url or "",
                'userName': order.loan_user_name,
                'timestamp': datetime.datetime.now().astimezone(tz=pytz.timezone( 'Asia/Kolkata' )).strftime('%Y-%m-%d %H:%M:%S'),
            } 
            res = pay_utils.sf_pay.create_pay_order(data)
            pay_url = res.get('url', "")

        # 创建交易记录
        trade_data = {
            'order_id': order.id,
            'payment_setting_id': order.repayment_setting_id.id,
            'payment_way_id': order.repayment_way_id.id,
            'trade_amount': extension.pending_amount,
            'trade_no': trade_no,
            'trade_status': '1' if res.get('code', 999) == 200 else '3',
            'trade_type': '1',
            'trade_start_time': fields.Datetime.now(),
            'platform_order_no': data.get('data', {}).get('payOrderId'),
            'trade_data': res,
            'res_model': 'extension.record',
            'res_id': extension.id
        }
        request.env['payment.setting.trade.record'].sudo().create(trade_data)

        res = {
            "payUrl": pay_url
        }
        return res

        