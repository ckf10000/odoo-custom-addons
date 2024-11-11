# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import date


class ManualAllocationWizard(models.TransientModel):
    _name = 'manual.allocation.wizard'
    _table = 'C_manual_allocation_wizard'
    _description = '手动分单向导'

    selected_ids = fields.Integer(string='已选择订单数量')
    collection_stage = fields.Char(string='催收阶段')
    collector_id = fields.Many2one('res.users', string='分配对象')  # 催收员

    def action_confirm(self):
        """
        确认按钮
        """

        if not self.collector_id:
            raise ValidationError(_('没有可选对象，请调整“分单管理”配置!'))
        else:
            order_ids = self.env['collection.order'].browse(self._context.get('active_ids'))
            points_id = self.env['collection.points'].sudo().search([('user_id', '=', self.collector_id.id), ('collection_stage', '=', self.collection_stage)], limit=1)
            today_allocated_qty = self.env['collector.link.order.record'].sudo().search_count([('collector_id', '=', points_id.user_id.id), ('allot_date', '=', date.today())])
            can_allocated_ids = order_ids.filtered(lambda x: x.loan_order_id.id in points_id.loan_product_ids.ids)
            # 如果选择的订单 可以完全分配则执行并返回执行成功
            if points_id.max_daily_intake > today_allocated_qty + self.selected_ids:
                if len(can_allocated_ids) == self.selected_ids:
                    order_ids.write({'order_status_id': self.env['collection.order.status'].sudo().search([('code', '=', '2')]).id, 'collector_id': points_id.user_id.id})
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': '提示',
                            'message': '手动分单成功',
                            'sticky': False,
                            'next': {'type': 'ir.actions.act_window_close'},
                        },
                    }
                else:
                    can_allocated_ids.write({'order_status_id': self.env['collection.order.status'].sudo().search([('code', '=', '2')]).id, 'collector_id': points_id.user_id.id})
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': '提示',
                            'message': f'手动分单失败数量：{self.selected_ids - len(can_allocated_ids)} \n订单产品不属于该催收员“进件产品”范围。',
                            'sticky': False,
                            'next': {'type': 'ir.actions.act_window_close'},
                        },
                    }
            elif today_allocated_qty < points_id.max_daily_intake < today_allocated_qty + self.selected_ids:
                    order_ids[:points_id.max_daily_intake - today_allocated_qty].write({'order_status_id': self.env['collection.order.status'].sudo().search([('code', '=', '2')]).id, 'collector_id': points_id.user_id.id})
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': '提示',
                            'message': f'手动分单失败数量：{self.selected_ids - (points_id.max_daily_intake - today_allocated_qty)}\n已达到该催收员今日进件上限',
                            'sticky': False,
                            'next': {'type': 'ir.actions.act_window_close'},
                        },
                    }



class ManualAllocationTitleWizard(models.TransientModel):
    _name = 'manual.allocation.title.wizard'
    _description = '手动分单提示'