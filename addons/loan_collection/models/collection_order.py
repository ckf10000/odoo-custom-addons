import logging
from odoo import models, fields, api, exceptions
from datetime import datetime, date
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from . import enums

class CollectionOrder(models.Model):
    _name = "collection.order"
    _inherit = ["loan.basic.model"]
    _table = "C_order"
    _description = "催收订单"

    order_status_id = fields.Many2one("collection.order.status", string="催收订单状态")
    loan_order_id = fields.Many2one("loan.order", string="关联订单")
    user_id = fields.Many2one(
        "loan.user", string="关联用户", related="loan_order_id.loan_user_id", store=True
    )
    order_no = fields.Char(string="订单编号", related="loan_order_id.order_no", store=True)
    loan_uid = fields.Integer('UserID', related='loan_order_id.loan_uid')
    name = fields.Char(string="姓名", related="loan_order_id.loan_user_name", store=True)
    order_type = fields.Selection(selection=enums.ORDER_TYPE, string='订单类型', related="loan_order_id.order_type", store=True)

    phone_no = fields.Char(string="手机号码", related="loan_order_id.loan_user_phone", store=True)
    card_num = fields.Char(
        string="证件号码"
    )  # todo 显示当前订单关联用户的身份证号码（APP-填资-活体&证照信息-PAN card Number）；
    application_time = fields.Datetime(
        string="申请时间", related="loan_order_id.apply_time", store=True
    )
    contract_amount = fields.Float(
        string="合同金额", releated="loan_order_id.contract_amount"
    )
    borrow_money_date = fields.Integer(
        string="借款期限(天)", related="loan_order_id.loan_period", store=True
    )
    collection_stage_setting_id = fields.Many2one(
        "collection.stage.setting", string="催收阶段配置"
    )
    collection_stage = fields.Char(
        string="催收阶段",
        related="collection_stage_setting_id.collection_stage",
        store=True,
    )
    product_id = fields.Many2one('loan.product', string='产品名称', auto_join=True, index=True, releated="loan_order_id.product_id")
    product_name = fields.Char(
        string="产品名称", 
        index=True, 
        releated="product_id.product_name", 
    )
    app_id = fields.Many2one(
        "loan.app", string="App", related="user_id.app_id", store=True
    )
    app_name = fields.Char(string="APP名称", related="app_id.app_name", store=True)
    version = fields.Integer(string="版本号", compute="_compute_version", store=True)
    
    # 放款
    pay_complete_time = fields.Datetime(string='放款成功时间',related="loan_order_id.pay_complete_time")
    withdraw_time = fields.Datetime(string='取现时间',related="loan_order_id.withdraw_time")
    pay_platform_order_no = fields.Char(string='放款序列号',related="loan_order_id.pay_platform_order_no")
        

    # 还款数据
    # repay_complete_time = fields.Datetime(string='还款完成时间',related="loan_order_id.repay_complete_time")
    repay_date = fields.Date(string='应还日期', related="loan_order_id.repay_date")
    overdue_days = fields.Integer(string='逾期天数', related="loan_order_id.overdue_days")
    # is_overdue = fields.Boolean(string='是否逾期', related="loan_order_id.is_overdue")
    # overdue_rate = fields.Float('逾期罚息费率', related='product_id.penalty_interest_rate')
    overdue_fee = fields.Float('应还罚息', related='loan_order_id.overdue_fee')
    late_fee = fields.Float('应还滞纳金', related='loan_order_id.late_fee')
    repay_amount = fields.Float('应还本息', related='loan_order_id.repay_amount')
    correction_amount = fields.Float('冲正金额', related='loan_order_id.correction_amount')

    repayed_amount = fields.Float('已还款金额', related='loan_order_id.repayed_amount')
    # repayed_overdue_fee = fields.Float('已还罚息', related='loan_order_id.repayed_overdue_fee')
    # platform_profit = fields.Float('平台额外收益', related='loan_order_id.platform_profit')
    pending_amount = fields.Float('挂账金额', related='loan_order_id.pending_amount') # 待还金额
    repay_platform_order_no = fields.Char(string='还款序列号', related='loan_order_id.repay_platform_order_no')

    # 减免
    derate_amount = fields.Float('减免金额', compute='loan_order_id.derate_amount')

    # 平账
    # settle_amount = fields.Float('平账金额', digits=(16, 2), compute='_compute_settle_amount')

    # 退款
    # refund_amount = fields.Float('退款金额', compute='_compute_refund_amount')

    # 展期订单
    # is_extension = fields.Boolean(string='是否展期订单', default=False)
    
    extend_pay_amount = fields.Float('展期金额', digits=(16, 2) ,related="loan_order_id.extend_pay_amount")
    apply_time = fields.Datetime(string='展期申请时间')
    extend_success_time = fields.Datetime('展期结束时间(含)',related="loan_order_id.extend_success_time")
    renewal_repayment_amount = fields.Float(string="申请展期需支付金额", digits=(16, 2))
    add_renewal_no = fields.Integer(string="累计展期次数")    

    receivables_number = fields.Char(string='收款账号', related="loan_order_id.bank_account_no") 
    #loan_movement_id = fields.Many2one("loan.movement",string="放款方式",related="loan_order_id.loan_movement_id",store=True,)
    #loan_movement_name = fields.Char(string="放款方式", related="loan_movement_id.name", store=True)
    payment_way_id = fields.Many2one('payment.way',string='放款方式', related="loan_order_id.payment_way_id")

    repayment_capital = fields.Float(string="应还本金", digits=(16, 2) , releated="loan_order_id.contract_amount")

    loan_amount = fields.Float(
        string="放款金额",
        digits=(16, 2),
        related="loan_order_id.loan_amount",
    )
    
    loan_order_status_id = fields.Selection(
        selection=enums.ORDER_STATUS, 
        string="财务订单状态",
        related="loan_order_id.order_status",
    )

    user_identity_id = fields.Many2one(
        "user.identity",
        string="用户身份信息",
        compute="_compute_user_identity_id",
        store=True,
    )
    gender_code = fields.Selection(
        selection=enums.GENDER,string="性别", 
        #related="user_identity_id.gender_code", 
        store=True
    )
    birth_date = fields.Integer(
        string="生日", 
        #related="user_identity_id.birth_date", 
        store=True
    )  # Modify Pfly Datetime to Integer
    occupation_code = fields.Selection(
        selection=enums.OCCUPATION,
        string="职业", 
        #related="user_identity_id.occupation_code", 
        store=True
    )
    education_code = fields.Selection(
        selection=enums.EDUCATION,
        string="学历", 
        #related="user_identity_id.education_code", 
        store=True
    )
    marital_status_code = fields.Selection(
        selection=enums.MARITAL_STATUS,
        string="婚姻状况", 
        #related="user_identity_id.marital_status_code", 
        store=True
    )
    salary_code = fields.Integer(
        string="月收入", related="user_identity_id.salary_code", store=True
    )
    housing_status_code = fields.Selection(
        selection=enums.HOUSE_STATUS,
        string="居住状况", 
        #related="user_identity_id.housing_status_code", 
        store=True
    )
    children_num_code = fields.Selection(
        selection=enums.CHILDREN_COUNT,
        string="子女数量", 
        #related="user_identity_id.children_num_code", 
        store=True
    )
    loan_purpose_code = fields.Selection(
        selection=enums.LOAN_PURPOSE,string="贷款用途", 
        #related="user_identity_id.loan_purpose_code", 
        store=True
    )
    pay_day_code = fields.Integer(
        string="发薪日", related="user_identity_id.pay_day_code"
    )
    # finished_flag = fields.Boolean(
    #     string="是否完成通讯录填写",
    #     related="user_identity_id.finished_flag",
    #     store=True,
    # )

    collection_user_contact_ids = fields.One2many(
        "collection.user.contact",
        "collection_order_id",
        string="用户联系人信息",
        #compute="_compute_collection_user_contact_ids",
        store=True,
    ) 
    
    user_address_book_ids = fields.One2many(
        "collection.user.address.book", "collection_order_id", string="通讯录"
    )
    user_call_record_ids = fields.One2many(
        "collection.user.call.record", "collection_order_id", string="通话记录"
    )
    history_collection_record_ids = fields.One2many(
        "history.collection.record", "collection_order_id", string="历史催收记录"
    )
    history_loans_record_ids = fields.One2many(
        "history.loans.record", "collection_order_id", string="历史贷款记录"
    )


    pan_front_img = fields.Char(string="PAN卡正面照")  
    pan_back_img = fields.Char(string="PAN卡背面照")
    id_front_img = fields.Char(string="ID卡正面照")
    id_hand_img = fields.Char(string="ID卡手持照")
    body_discern_img = fields.Char(string="活体识别照")

    # 待处理订单字段
    # collection_user_id = fields.Many2one("loan.user", string="催收对象")
    collector_id = fields.Many2one(
        "res.users", domain=[("is_collection", "=", True)], string="催收员"
    )
    collector_name = fields.Char(
        string="催收员姓名", related="collector_id.name", store=True
    )

    @api.depends("app_id")
    def _compute_version(self):
        for rec in self:
            rec.version = (
                rec.app_id.setting_ids[-1].version
                if rec.app_id and rec.app_id.setting_ids
                else 0
            )

    @api.depends("user_id")
    def _compute_user_identity_id(self):
        for rec in self:
            user_identity_id = self.env["user.identity"].search(
                [("user_id", "=", rec.user_id.id)], limit=1
            )
            rec.user_identity_id = user_identity_id.id if user_identity_id else False            

    @api.onchange("collection_user_id")
    def _onchage_collection_user_id(self):
        self.relation_selection = False
        if self.collection_user_id:
            user_contact_id = self.user_contact_ids.filtered(
                lambda x: x.user_id == self.collection_user_id.id
            )
            if self.collection_user_id.name == self.env.user.name:
                self.relation_selection = "oneself"
            elif user_contact_id:
                self.relation_selection = user_contact_id.relation_selection

    def action_server_collection_order_allot(self):
        """
        待分配订单action
        """

        context = self.env.context
        order_status_id = self.env["collection.order.status"].search(
            [("code", "=", "1")]
        )
        domain = [("order_status_id", "=", order_status_id.id)]
        tree_view_id = self.env.ref("loan_collection.collection_order_allot_list")
        search_view_id = self.env.ref("loan_collection.collection_order_allot_search")
        action_id = self.env.ref("loan_collection.collection_order_allot_action")
        return {
            "id": action_id.id,
            "type": "ir.actions.act_window",
            "name": "待分配订单",
            "res_model": self._name,
            "view_mode": "tree",
            "views": [(tree_view_id.id, "list")],
            "search_view_id": [search_view_id.id],
            "target": "current",
            "domain": domain,
            "context": dict(context),
        }

    def action_server_collection_order_pending(self):
        """
        待处理订单action
        """

        context = self.env.context
        order_status_id = self.env["collection.order.status"].search(
            [("code", "=", "2")]
        )
        child_users = self.env["res.users"].search(
            [("parent_id", "=", self.env.user.id)]
        )
        domain = [
            ("order_status_id", "=", order_status_id.id),
            ("collector_id", "in", child_users.ids + [self.env.user.id]),
        ]
        tree_view_id = self.env.ref("loan_collection.collection_order_pending_list")
        search_view_id = self.env.ref("loan_collection.collection_order_pending_search")
        action_id = self.env.ref("loan_collection.collection_order_pending_action")
        return {
            "id": action_id.id,
            "type": "ir.actions.act_window",
            "name": "待处理订单",
            "res_model": self._name,
            "view_mode": "tree",
            "views": [(tree_view_id.id, "list")],
            "search_view_id": [search_view_id.id],
            "target": "current",
            "domain": domain,
            "context": dict(context),
        }

    def action_server_collection_order_process(self):
        """
        处理中订单action
        """
        context = self.env.context
        order_status_id = self.env["collection.order.status"].search(
            [("code", "=", "3")]
        )
        domain = [("order_status_id", "=", order_status_id.id)]
        tree_view_id = self.env.ref("loan_collection.collection_order_process_list")
        search_view_id = self.env.ref("loan_collection.collection_order_process_search")
        action_id = self.env.ref("loan_collection.collection_order_process_action")
        return {
            "id": action_id.id,
            "type": "ir.actions.act_window",
            "name": "处理中订单",
            "res_model": self._name,
            "view_mode": "tree",
            "views": [(tree_view_id.id, "list")],
            "search_view_id": [search_view_id.id],
            "target": "current",
            "domain": domain,
            "context": dict(context),
        }

    def action_look_over(self):
        """
        列表点击查看按钮
        """
        form_view_id = self.env.ref("loan_collection.collection_order_allot_form")
        return {  
            'type': 'ir.actions.act_window',  
            'name': '订单详情',  
            'res_model': self._name,  
            'res_id': self.id,  # 当前记录的ID  
            'view_mode': 'form',  
            'view_type': 'form', 
            "views": [(form_view_id.id, "form")], 
            # 'target': 'new',  
        }  
        # return {
        #     "name": "订单详情",
        #     "type": "ir.actions.act_window",
        #     "res_model": self._name,
        #     "res_id": self.id,
        #     "view_mode": "form",
        #     "views": [(form_view_id.id, "form")],
        #     "target": "new",
        #     "context": {
        #         #"dialog_size": self._action_default_size(),
        #         #**self._action_default_data(),
        #     },
        # }

    def action_follow_up(self):  
        """  
        列表点击跟进按钮  
        """  
        form_view_id = self.env.ref("loan_collection.collection_order_pending_form")  
        return {  
            "name": "订单详情",  
            "type": "ir.actions.act_window",  
            "res_model": self._name,  
            "res_id": self.id,  
            "view_mode": "form",  
            "views": [(form_view_id.id, "form")],  
            # "target": "new",  
            "context": {  
                #"form_view_initial_mode": "edit",  # 如果您希望在编辑模式下打开  
                #"dialog_size": "100%",  # 设置对话框的标准尺寸为100%  
                # "fullscreen": True,  # 确保对话框将以全屏模式显示  
                # 如果您需要传递其他上下文数据，可以在这里添加  
                # **self._action_default_data(),  
            },  
        }

    def action_loan_voucher(self):
        """
        列表点击放款凭证按钮
        """
        form_view_id = self.env.ref("loan_collection.collection_order_pending_form2")
        return {
            "name": "放款凭证",
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(form_view_id.id, "form")],
            "target": "new",
            "context": {
                "dialog_size": self._action_default_size(),
                **self._action_default_data(),
            },
        }

    def action_download_voucher(self):
        """放款凭证-下载凭证按钮"""
        form_view_id = self.env.ref("loan_collection.collection_order_pending_form3")
        url = f"/wizard/form_to_image?res_id={self.id}&res_model=collection.order&view_id={form_view_id.id}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_amount_deduction(self):
        """列表点击金额减免按钮"""
        form_view_id = self.env.ref("loan_collection.loan_reduction_examine_form")
        return {
            "name": "金额减免申请",
            "type": "ir.actions.act_window",
            "res_model": "loan.reduction.examine",
            "view_mode": "form",
            "views": [(form_view_id.id, "form")],
            "target": "new",
            "context": {
                "default_resource_model": "collection",
                "default_order_id": self.loan_order_id.id,
                "default_user_id": self.user_id.id,
                "default_product_id": self.loan_order_id.product_id.id,
                "default_application_time": datetime.now(),
                "default_collection_phase_id": self.collection_stage,
                "default_reduction_type": "permanent",
                "default_max_annul_amount": self.pending_amount - self.loan_amount,
                "dialog_size": self._action_default_size(),
                **self._action_default_data(),
            },
        }

    def action_replacement_order(self):
        """列表点击补单按钮"""
        context = self.env.context
        # self.env.context.update({'order_id': self.id})
        tree_view_id = self.env.ref("loan_collection.replenishment_record_list2")
        search_view_id = self.env.ref("loan_collection.replenishment_record_search2")
        return {
            "name": "补单申请",
            "type": "ir.actions.act_window",
            "res_model": "replenishment.record",
            "view_mode": "tree",
            "views": [(tree_view_id.id, "list")],
            "target": "new",
            "search_view_id": [search_view_id.id],
            "context": dict(context),
        }
        pass

    def action_manual_allocation(self):
        if len(self) == 0:
            raise UserError('请先勾选需要手动分配的订单！')
        elif len(set(self.mapped('collection_stage'))) > 1:
            raise UserError('请勾选相同“催收阶段”的订单，否则无法进行分配')
        else:
            form_view_id = self.env.ref("loan_collection.manual_allocation_wizard_form")
            collection_stage = self[0].collection_stage
            collection_stage_id = self[0].collection_stage_setting_id
            return {
                "name": "手动分单",
                "type": "ir.actions.act_window",
                "res_model": "manual.allocation.wizard",
                #'res_id': self.id,
                "view_mode": "form",
                "views": [(form_view_id.id, "form")],
                "target": "new",
                "context": {
                    "default_selected_ids": len(self),
                    "default_collection_stage": collection_stage,
                    "dialog_size": self._action_default_size(),
                    #**self._action_default_data(),
                },
            }
        
    def collection_auto_assign_orders_button_action(self):
        #self.auto_assign_orders = not self.auto_assign_orders
        
        return True        

    def action_add_contact(self):
        form_view_id = self.env.ref("loan_collection.collection_user_contact_form")
        return {
            "name": "添加联系人",
            "type": "ir.actions.act_window",
            "res_model": "collection.user.contact",
            "view_mode": "form",
            "views": [(form_view_id.id, "form")],
            "target": "new",
            "context": {
                "default_collection_order_id": self.id,
                "dialog_size": self._action_default_size(),
                # **self._action_default_data(),
            },
        }     

    def action_submit(self):  
        self.ensure_one()  

        # 获取处理状态  
        order_status = self.env['collection.order.status'].sudo().search([('code', '=', '3')], limit=1)  
        if not order_status:  
            raise ValidationError("未找到状态为处理中的催收订单。")  

        # 更新状态和收集员信息  
        self.write({  
            'order_status_id': order_status.id,  
            'collector_id': self.env.user.id,  
        })  

        # 增加历史记录  
        history_record_vals = { 
            'collection_order_id': self.id,  
            'sequence': 0,  
            'user_id': self.collection_user_id.id,  
            'relation_selection': self.relation_selection,  
            'phone_no': self.phone_no,  
            'collection_type': self.collection_type,  
            'contact_result': self.contact_result,  
            'remark': self.remark,  
            'file_ids': [(6, 0, self.upload_img_ids.ids)],  
            'collector_id': self.env.user.id,  
        }  
        self.env['history.collection.record'].sudo().create(history_record_vals)  

        # 增加对应分单管理已处理单量  
        points_id = self.env['collection.points'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)  
        if points_id:  
            points_id.write({'today_processed_qty': points_id.today_processed_qty + 1})  

        # 跳转到处理中页面  
        return self.action_server_collection_order_process()  


class CollectionUserContact(models.Model):
    _name = "collection.user.contact"
    _table = "C_user_contact"
    _description = "用户联系人信息"

    sequence = fields.Integer(string="序号", compute="_compute_sequence", store=True)
    name = fields.Char(string="联系人姓名")
    phone_no = fields.Char(string="电话号码")
    collection_order_id = fields.Many2one("collection.order", string="催收订单")
    # replenish_time = fields.Datetime(string='补充时间')
    # operate_user_id = fields.Many2one('res.users', string='操作人')
    relation_selection = fields.Selection(
        [
            ("Father", "Father"),
            ("Mother", "Mother"),
            ("Spouse", "Spouse"),
            ("Friend", "Friend"),
            ("Family", "Family"),
            ("Brothers", "Brothers"),
            ("Colleague", "Colleague"),
            ("Others", "Others"),
            ("oneself", "本人"),
        ],
        string="关系",
    )

    @api.depends("collection_order_id")
    def _compute_sequence(self):
        for record in self.mapped("collection_order_id"):
            num = 0
            for line in record.collection_user_contact_ids:
                num += 1
                line.update({"sequence": num})


class CollectionUserAddressBook(models.Model):
    _name = "collection.user.address.book"
    _table = "C_user_address_book"
    _description = "用户通讯录"

    collection_order_id = fields.Many2one("collection.order", string="催收订单")
    order_no = fields.Char(string='订单号', index=True)
    sequence = fields.Integer(string="序号", compute="_compute_sequence", store=True)
    name = fields.Char(string="姓名")
    phone_no = fields.Char(string="电话")
    active = fields.Boolean(default=True)

    @api.depends("collection_order_id")
    def _compute_sequence(self):
        for record in self.mapped("collection_order_id"):
            num = 0
            for line in record.user_address_book_ids:
                num += 1
                line.update({"sequence": num})


class UserCallRecord(models.Model):
    _name = "collection.user.call.record"
    _table = "C_user_call_record"
    _description = "通话记录"

    collection_order_id = fields.Many2one("collection.order", string="催收订单")
    order_no = fields.Char(string='订单号', index=True)
    name = fields.Char(string="姓名")
    phone_no = fields.Char(string="电话")
    sequence = fields.Integer(string="序号", compute="_compute_sequence", store=True)
    call_type = fields.Selection(
        [("send", "发送"), ("receive", "接收"), ("unreceived", "未接")],
        string="通话类型",
    )
    call_time = fields.Datetime(string="通话时间")
    total_call_times = fields.Integer(string="通话总次数")
    total_call_duration = fields.Integer(string="通话总时长(m)")
    active = fields.Boolean(default=True)

    @api.depends("collection_order_id")
    def _compute_sequence(self):
        for record in self.mapped("collection_order_id"):
            num = 0
            for line in record.user_address_book_ids:
                num += 1
                line.update({"sequence": num})


class HistoryCollectionRecord(models.Model):
    _name = "history.collection.record"
    _table = "C_history_collection_record"
    _description = "历史催收记录"

    collection_order_id = fields.Many2one("collection.order", string="催收订单")
    sequence = fields.Integer(string="序号", compute="_compute_sequence", store=True)
    user_id = fields.Many2one("collection.user.contact", string="催收对象")
    relation_selection = fields.Selection(
        [
            ("Father", "Father"),
            ("Mother", "Mother"),
            ("Spouse", "Spouse"),
            ("Friend", "Friend"),
            ("Family", "Family"),
            ("Brothers", "Brothers"),
            ("Colleague", "Colleague"),
            ("Others", "Others"),
            ("oneself", "本人"),
        ],
        string="与本人关系",
        related="user_id.relation_selection",
    )
    phone_no = fields.Char(string="跟踪电话", related="user_id.phone_no")
    collection_type = fields.Selection(
        [
            ("phone", "电话催收"),
            ("sms", "短信催收"),
            ("work_phone", "工作手机催收"),
            ("customer_service", "客服进线"),
            ("other", "其他"),
        ],
        string="催收形式",
    )
    contact_result = fields.Selection(
        [
            ("联系人造假", "联系人造假"),
            ("工作信息造假", "工作信息造假"),
            ("离职", "离职"),
            ("投诉备注", "投诉备注"),
            ("失去联系/拒绝转告", "失去联系/拒绝转告"),
            ("疑似欺诈", "疑似欺诈"),
            ("另设日期联系", "另设日期联系"),
            ("声明已缴", "声明已缴"),
            ("无人接听", "无人接听"),
            ("忙音/通话中", "忙音/通话中"),
            ("电话拒接", "电话拒接"),
            ("关机", "关机"),
            ("无法接通", "无法接通"),
            ("短信通知", "短信通知"),
            ("停机", "停机"),
            ("空号", "空号"),
            ("其他", "其他"),
        ],
        string="联络结果",
    )
    remark = fields.Char(string="备注")
    file_ids = fields.Many2many("ir.attachment", string="附件图片")
    collector_id = fields.Many2one("res.users", string="催收员")

    @api.depends("collection_order_id")
    def _compute_sequence(self):
        for record in self.mapped("collection_order_id"):
            num = 0
            for line in record.history_collection_record_ids:
                num += 1
                line.update({"sequence": num})


class HistoryLoansRecord(models.Model):
    _name = "history.loans.record"
    _table = "C_history_loans_record"
    _description = "历史贷款记录"

    collection_order_id = fields.Many2one("collection.order", string="催收订单")
    sequence = fields.Integer(string="序号", compute="_compute_sequence", store=True)
    loan_order_id = fields.Many2one("loan.order", string="关联订单")
    order_no = fields.Char(string="订单编号", related="loan_order_id.order_no", store=True)
    contract_amount = fields.Float(
        string="合同金额", releated="loan_order_id.contract_amount"
    )
    borrow_money_date = fields.Integer(
        string="借款期限(天)", related="loan_order_id.loan_period", store=True
    )
    application_time = fields.Datetime(
        string="申请时间", related="loan_order_id.apply_time", store=True
    )
    product_name = fields.Char(
        string="产品名称", index=True, releated="loan_order_id.product_id.product_name"
    )
    app_id = fields.Many2one(
        "loan.app", string="App", related="loan_order_id.app_id", store=True
    )
    app_name = fields.Char(string="APP名称", related="app_id.app_name", store=True)
    loan_order_status_id = fields.Selection(selection=enums.ORDER_STATUS, default='1', string='财务订单状态')
    
    credit_examiner = fields.Many2one("res.users", string="信审员")
    credit_audit_reason = fields.Char(string="信审原因")
    remark = fields.Char(string="备注")

    @api.depends("collection_order_id")
    def _compute_sequence(self):
        for record in self.mapped("collection_order_id"):
            num = 0
            for line in record.history_collection_record_ids:
                num += 1
                line.update({"sequence": num})


class CollectionAutoAssignOrders(models.Model):
    _name = 'collection.auto.assign.orders'
    _table = 'C_auto_assign_orders'
    _description = '自动分单'

    auto_assign_orders = fields.Boolean(string='自动分单', default=False)
    
