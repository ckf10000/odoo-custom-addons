import logging
from odoo import models, fields, api, exceptions
from datetime import datetime, date
from odoo.exceptions import ValidationError


class CollectionStageSetting(models.Model):
    _name = 'collection.stage.setting'
    _inherit = ['loan.basic.model']
    _table = 'C_stage_setting'
    _description = '催收阶段配置'
    _sql_constraints = [
        ('collection_stage_uniq', 'unique(collection_stage)', '催收阶段名称已使用，请调整'),
        ('check_number_of_min_day', 'CHECK(min_day >= -7)', '预期天数下限值为-7'),
        ('check_number_of_max_day', 'CHECK(max_day <= 999)', '预期天数上限值为999'),
    ]
    _rec_name = 'collection_stage'

    collection_stage = fields.Char(string='催收阶段')
    overdue_days = fields.Char(string='逾期天数', compute='compute_overdue_days', store=True)
    min_day = fields.Integer(string='逾期天数min')
    max_day = fields.Integer(string='逾期天数max', default=999)
    status = fields.Boolean(string='状态', default=True)
    status_select = fields.Selection([('active', '开启'), ('stop', '关闭')], string='状态', compute='compute_status_select', store=True)
    history_ids = fields.One2many('collection.stage.setting.history', 'collection_stage_setting_id', string='历史记录')

    @api.depends('min_day', 'max_day')
    def compute_overdue_days(self):
        """拼接逾期天数范围"""
        for record in self:
            record.overdue_days = str(record.min_day) + '~' + str(record.max_day) + '天'

    @api.depends('status')
    def compute_status_select(self):
        for record in self:
            record.status_select = 'active' if record.status else 'stop'

    def action_server_collection_stage_setting(self):
        """
        催收阶段配置action
        """
        context = self.env.context
        tree_view_id = self.env.ref('loan_collection.collection_stage_setting_list')
        search_view_id = self.env.ref('loan_collection.collection_stage_setting_search')
        action_id = self.env.ref('loan_collection.collection_stage_setting_action')
        return {
            'id': action_id.id,
            'type': 'ir.actions.act_window',
            'name': '催收阶段配置',
            'res_model': self._name,
            'view_mode': 'tree',
            'views': [(tree_view_id.id, 'list')],
            'search_view_id': [search_view_id.id],
            'target': 'current',
            'context': dict(context)
        }

    def action_edit(self):
        """
        列表点击编辑按钮
        """
        form_view_id = self.env.ref('loan_collection.collection_stage_setting_form')
        return {
            'name': '编辑',
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(form_view_id.id, 'form')],
            'target': 'new',
            'context': {'dialog_size': self._action_default_size(), **self._action_default_data()}
        }

    def action_delete(self):
        """
        列表点击删除按钮
        """
        form_view_id = self.env.ref('loan_collection.collection_stage_setting_wizard_delete_form')
        return {
            'name': '编辑',
            'type': 'ir.actions.act_window',
            'res_model': 'collection.stage.setting.wizard',
            'view_mode': 'form',
            'views': [(form_view_id.id, 'form')],
            'target': 'new',
            'context': {'dialog_size': self._action_default_size(), **self._action_default_data()}
        }

    def action_history(self):
        """
        列表点击历史记录按钮
        """
        tree_view_id = self.env.ref('loan_collection.collection_stage_setting_history_list')
        search_view_id = self.env.ref('loan_collection.collection_stage_setting_history_search')
        return {
            'name': '历史记录',
            'type': 'ir.actions.act_window',
            'res_model': 'collection.stage.setting.history',
            'view_mode': 'tree',
            'views': [(tree_view_id.id, 'list')],
            'search_view_id': [search_view_id.id],
            'domain': [('collection_stage_setting_id', '=', self.id)],
            'target': 'new',
            'context': {'dialog_size': self._action_default_size(), **self._action_default_data()}
        }

    def write(self, vals):
        """编辑保存后增加一条历史记录"""
        result = super(CollectionStageSetting, self).write(vals)
        if result:
            self.env['collection.stage.setting.history'].create({
                'collection_stage_setting_id': self.id,
                'collection_stage': self.collection_stage,
                'overdue_days': self.overdue_days,
                'min_day': self.min_day,
                'max_day': self.max_day,
                'status': self.status,
                'status_select': self.status_select,
                'edit_date': datetime.now(),
                'edit_user_id': self.env.user.id
            })
        return result

    @api.model
    def create(self, values):
        """新增后后增加一条历史记录"""
        res_id = super(CollectionStageSetting, self).create(values)
        self.env['collection.stage.setting.history'].create({
            'collection_stage_setting_id': res_id.id,
            'collection_stage': res_id.collection_stage,
            'overdue_days': res_id.overdue_days,
            'min_day': res_id.min_day,
            'max_day': res_id.max_day,
            'status': res_id.status,
            'status_select': res_id.status_select,
            'edit_date': datetime.now(),
            'edit_user_id': self.env.user.id
        })
        return res_id

    # region 校验
    @api.constrains('min_day', 'max_day')
    def _check_min_max_day(self):
        if self.min_day > self.max_day:
            raise ValidationError('逾期天数下限值不能大于逾期天数上限值')

    # endregion

    def cron_collection_stage_setting(self):
        """
        每日凌晨1:00根据该模块的配置，对所有待还款（还款中、还款逾期）订单重新划分催收阶段，重新进行分单
        """
        # 重置分单管理的今日待处理、已处理单量
        for i in self.env["collection.points"].sudo().search([]):
            i.write({"today_processed_qty": 0, "today_pending_qty": 0})

        def distribute_orders(orders, limits, acceptable_attrs):
            """
            自动分配方法
            """
            # 确定待处理的订单状态id
            order_status_id = (
                self.env["collection.order.status"]
                .sudo()
                .search([("code", "=", "2")], limit=1)
                .id
            )
            distribution = {person: 0 for person in limits}
            total_limit = sum(limits.values())

            # 如果订单总数超过总的最大限制，取最大值
            if len(orders) > total_limit:
                orders = orders[:total_limit]

            # 分配订单
            for order in orders:
                for person, limit in limits.items():
                    if (
                        distribution[person] < limit
                        and order.id in acceptable_attrs[person].ids
                    ):
                        distribution[person] += 1
                        order.write(
                            {
                                "collector_id": person.id,
                                "order_status_id": order_status_id,
                            }
                        )
                        self.env["collector.link.order.record"].sudo().create(
                            {
                                "collector_id": person.id,
                                "allot_date": date.today(),
                                "collection_order_id": order.id,
                            }
                        )
                        break

            return distribution

        # repayment_status_id = self.env['repayment.status'].search([('code', '=', '1')], limit=1)
        loan_order_ids = self.env["loan.order"].search(
            [("order_status", "=", "7")]
        )  #'7', '待还款'
        values = []

        # 处理催收阶段设置
        user_contact_dict = {
            i.user_id.id: i
            for i in self.env["user.contact"].sudo().search([("user_id", "in", loan_order_ids.mapped("loan_user_id").ids)])
        }
        for loan_order in loan_order_ids:
            overdue_days = (date.today() - loan_order.repayin_date).days
            collection_stage_setting_id = (
                self.env["collection.stage.setting"]
                .sudo()
                .search(
                    [("min_day", "<=", overdue_days), ("max_day", ">=", overdue_days)],
                    limit=1,
                )
            )

            if collection_stage_setting_id:
                exist_order = self.env["collection.order"].search(
                    [("loan_order_id", "=", loan_order.id)], limit=1
                )
                if exist_order:
                    if (
                        exist_order.collection_stage_setting_id.id
                        != collection_stage_setting_id.id
                    ):
                        exist_order.write(
                            {
                                "collection_stage_setting_id": collection_stage_setting_id.id
                            }
                        )
                else:
                    user_contact = user_contact_dict.get(loan_order.loan_uid, [])
                    relation_dict = {
                        1: "Father",
                        2: "Mother",
                        3: "Spouse",
                        4: "Friend",
                        5: "Family",
                        6: "Brothers",
                        7: "Colleague",
                        99: "Others"
                    }
                    collection_user_contacts = [
                        (0, 0, {
                            "can_edit": False,
                            "sequence": 1,
                            "name": user_contact.name_1,
                            "phone_no": user_contact.phone_no_1,
                            "relation_selection": relation_dict.get(user_contact.relation_code_1, "Others"),
                        }),
                        (0, 0, {
                            "can_edit": False,
                            "sequence": 2,
                            "name": user_contact.name_2,
                            "phone_no": user_contact.phone_no_2,
                            "relation_selection": relation_dict.get(user_contact.relation_code_2, "Others"),
                        }),
                        (0, 0, {
                            "can_edit": False,
                            "sequence": 3,
                            "name": user_contact.name_3,
                            "phone_no": user_contact.phone_no_3,
                            "relation_selection": relation_dict.get(user_contact.relation_code_3, "Others"),
                        })
                    ]
                    values.append(
                        {
                            "order_status_id": self.env["collection.order.status"]
                            .sudo()
                            .search([("code", "=", "1")], limit=1)
                            .id,
                            "loan_order_id": loan_order.id,
                            "collection_stage_setting_id": collection_stage_setting_id.id,
                            "collection_user_contact_ids": collection_user_contacts if user_contact else []
                        }
                    )

        if values:
            self.env["collection.order"].sudo().create(values)

        # 检查系统参数以决定是否执行自动分单
        auto_distribute = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("collection.auto_distribute", default="False")
            == "True"
        )

        if auto_distribute:
            order_status_id = self.env["collection.order.status"].search(
                [("code", "=", "1")], limit=1
            )
            allot_order_ids = self.env["collection.order"].search(
                [("order_status_id", "=", order_status_id.id)]
            )
            points_ids = self.env["collection.points"].search(
                [("is_input", "=", True), ("user_id.active", "=", True)]
            )

            limits = {}
            acceptable_attrs = {}

            for points_id in points_ids:
                today_allocated_qty = (
                    self.env["collector.link.order.record"]
                    .sudo()
                    .search_count(
                        [
                            ("collector_id", "=", points_id.user_id.id),
                            ("allot_date", "=", date.today()),
                        ]
                    )
                )
                if points_id.max_daily_intake > today_allocated_qty:
                    limits[points_id.user_id] = (
                        points_id.max_daily_intake - today_allocated_qty
                    )
                    acceptable_attrs[points_id.user_id] = points_id.loan_product_ids

            distribute_orders(allot_order_ids, limits, acceptable_attrs)

class CollectionStageSettingHistory(models.Model):
    _name = 'collection.stage.setting.history'
    _table = 'C_stage_setting_history'
    _inherit = ['loan.basic.model']
    _description = '催收阶段配置-历史记录'

    collection_stage_setting_id = fields.Many2one('collection.stage.setting', string='催收阶段配置')
    collection_stage = fields.Char(string='催收阶段')
    overdue_days = fields.Char(string='逾期天数')
    min_day = fields.Integer(string='逾期天数min')
    max_day = fields.Integer(string='逾期天数max')
    status = fields.Boolean(string='状态')
    status_select = fields.Selection([('active', '开启'), ('stop', '关闭')], string='状态')
    edit_date = fields.Datetime(string='编辑时间')
    edit_user_id = fields.Many2one('res.users', string='操作人')