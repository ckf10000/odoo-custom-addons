import logging
import requests
import base64
from odoo import models, fields, api, exceptions
from datetime import datetime, date
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from . import enums

_logger = logging.getLogger(__name__)

class CollectionOrder(models.Model):
    _name = "collection.order"
    _inherit = ["loan.basic.model"]
    _table = "C_order"
    _description = "催收订单"

    order_status_id = fields.Many2one("collection.order.status", string="催收订单状态")
    collection_status = fields.Char(string="催收状态", related="order_status_id.code")
    loan_order_id = fields.Many2one("loan.order", string="关联订单")
    user_id = fields.Many2one(
        "loan.user", string="关联用户", related="loan_order_id.loan_user_id", store=True
    )
    order_no = fields.Char(string="订单编号", related="loan_order_id.order_no", store=True)
    loan_uid = fields.Integer('UserID', related='loan_order_id.loan_uid')
    name = fields.Char(string="姓名", related="loan_order_id.loan_user_name", store=True)
    order_type = fields.Selection(selection=enums.ORDER_TYPE, string='订单类型', related="loan_order_id.order_type", store=True)

    phone_no = fields.Char(string="手机号码", related="loan_order_id.loan_user_phone", store=True)

    application_time = fields.Datetime(
        string="申请时间", related="loan_order_id.apply_time", store=True
    )
    contract_amount = fields.Float(
        string="合同金额", related="loan_order_id.contract_amount"
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
    product_id = fields.Many2one('loan.product', string='产品名称', related="loan_order_id.product_id")
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
    overdue_days = fields.Integer(string='逾期天数', related="loan_order_id.overdue_days", store=True)
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
    derate_amount = fields.Float('减免金额', related='loan_order_id.derate_amount')

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

    repayment_capital = fields.Float(string="应还本金", digits=(16, 2) , related="loan_order_id.contract_amount")

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
    
    gender_code_1 = fields.Integer(
        related="user_identity_id.gender_code"
    )
    gender_code = fields.Selection(
        selection=enums.GENDER,string="性别", 
        compute = "_compute_gender_code"
    )
    
    birth_date_1 = fields.Integer(
        string="生日", 
        related="user_identity_id.birth_date", 
    ) 
    birth_date = fields.Date(
        string="生日", 
        compute = "_compute_birth_date"
    )   
    
    occupation_code_1 = fields.Integer(
        string="职业", 
        related="user_identity_id.occupation_code", 
    )
    occupation_code = fields.Selection(
        selection=enums.OCCUPATION,
        string="职业", 
        compute = "_compute_occupation_code"
    )
    
    education_code_1 = fields.Integer(
        string="学历", 
        related="user_identity_id.education_code", 
    )
    education_code = fields.Selection(
        selection=enums.EDUCATION,
        string="学历", 
        compute = "_compute_education_code"
    )    
    marital_status_code_1 = fields.Integer(
        string="婚姻状况", 
        related="user_identity_id.marital_status_code", 
    )
    marital_status_code = fields.Selection(
        selection=enums.MARITAL_STATUS,
        string="婚姻状况", 
        compute = "_compute_marital_status_code",
    )    
    salary_code = fields.Integer(
        string="月收入", related="user_identity_id.salary_code"
    )
    housing_status_code_1 = fields.Integer(
        string="居住状况", 
        related="user_identity_id.housing_status_code", 
    )
    housing_status_code = fields.Selection(
        selection=enums.HOUSE_STATUS,
        string="居住状况", 
        compute = "_compute_housing_status_code", 
    )    
    children_num_code_1 = fields.Integer(
        string="子女数量", 
        related="user_identity_id.children_num_code", 
    )
    children_num_code = fields.Selection(
        selection=enums.CHILDREN_COUNT,
        string="子女数量", 
        compute = "_compute_children_num_code", 
    )    
    loan_purpose_code_1 = fields.Integer(
        string="贷款用途", 
        related="user_identity_id.loan_purpose_code", 
    )
    loan_purpose_code = fields.Selection(
        selection=enums.LOAN_PURPOSE,
        string="贷款用途", 
        compute = "_compute_loan_purpose_code", 
    )    
    pay_day_code = fields.Integer(
        string="发薪日", related="user_identity_id.pay_day_code"
    )

    collection_user_contact_ids = fields.One2many(
        "collection.user.contact",
        "collection_order_id",
        string="用户联系人信息"
    ) 

    is_relative = fields.Char(string="亲属号", compute="_compute_from_user_contact")
    is_risk = fields.Char(string="风险号", compute="_compute_from_user_contact")
    
    user_address_book_ids = fields.One2many(
        "collection.user.address.book", "collection_order_id", string="通讯录"
    )
    user_call_record_ids = fields.One2many(
        "collection.user.call.record", "collection_order_id", string="通话记录"
    )
    history_collection_record_ids = fields.One2many(
        "history.collection.record", "collection_order_id", string="历史催收记录"
    )
    # history_loans_record_ids = fields.One2many(
    #     "history.loans.record", "collection_order_id", string="历史贷款记录"
    # )
    loan_order_ids = fields.One2many(
        "loan.order", string="贷款记录", compute="_compute_loan_orders"
    )

    user_photo_set_id = fields.Many2one(
        "user.photo.set",
        string="用户证件照",
        compute="_compute_user_photo_set_id",
        store=True,
    )

    pan_front_img_url = fields.Char(string="PAN卡正面照", related="user_photo_set_id.photo_url_1")
    pan_back_img_url = fields.Char(string="PAN卡背面照", related="user_photo_set_id.photo_url_2")
    id_front_img_url = fields.Char(string="ID卡正面照", related="user_photo_set_id.photo_url_3")
    id_hand_img_url = fields.Char(string="ID卡手持照", related="user_photo_set_id.photo_url_4")    
    pan_front_img = fields.Image(string="PAN卡正面照" ,compute = "_compute_pan_front_img")  
    pan_back_img = fields.Image(string="PAN卡背面照", compute ="_compute_pan_back_img" )
    id_front_img = fields.Image(string="ID卡正面照", compute ="_compute_id_front_img")
    id_hand_img = fields.Image(string="ID卡手持照", compute="_compute_id_hand_img")
    
    user_action_living_rec_id = fields.Many2one(
        "user.action.living.rec",
        string="活体识别照",
        compute="_compute_user_action_living_rec_id",
        store=True,
    )    
    body_discern_img_url = fields.Char(string="活体识别照", related="user_action_living_rec_id.snapshot_url")
    body_discern_img = fields.Image(string="活体识别照", compute="_compute_body_discern_img") 
    
    
    card_num = fields.Char(
        string="证件号码",
        related="user_photo_set_id.ocr_result_2"
    )  # todo 显示当前订单关联用户的身份证号码（APP-填资-活体&证照信息-PAN card Number）；

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

    @api.depends("pan_front_img_url")
    def _compute_pan_front_img(self):
        for rec in self:
            # logging.debug("pan_front_img_url: %s", rec.pan_front_img_url)
            if  not rec.pan_front_img and rec.pan_front_img_url:
                try:
                    response = requests.get(rec.pan_front_img_url)
                    if response.status_code == 200:
                        rec.pan_front_img = base64.b64encode(response.content).decode('utf-8')
                except requests.exceptions.RequestException:
                    pass       

    @api.depends("pan_back_img_url")
    def _compute_pan_back_img(self):
        for rec in self:
            if not rec.pan_back_img and rec.pan_back_img_url:
                try:
                    response = requests.get(rec.pan_back_img_url)
                    if response.status_code == 200:
                        rec.pan_back_img = base64.b64encode(response.content).decode('utf-8')
                except requests.exceptions.RequestException:
                    pass   

    @api.depends("id_front_img_url")
    def _compute_id_front_img(self):
        for rec in self:
            if not rec.id_front_img and rec.id_front_img_url:
                try:
                    response = requests.get(rec.id_front_img_url)
                    if response.status_code == 200:
                        rec.id_front_img = base64.b64encode(response.content).decode('utf-8')
                except requests.exceptions.RequestException:
                    pass                               

    @api.depends("id_hand_img_url")
    def _compute_id_hand_img(self):
        for rec in self:
            if not rec.id_hand_img and rec.id_hand_img_url:
                try:
                    response = requests.get(rec.id_hand_img_url)
                    if response.status_code == 200:
                        rec.id_hand_img = base64.b64encode(response.content).decode('utf-8')
                except requests.exceptions.RequestException:
                    pass  
          
    @api.depends("body_discern_img_url")
    def _compute_body_discern_img(self):
        for rec in self:
            if not rec.body_discern_img and rec.body_discern_img_url:
                try:
                    response = requests.get(rec.body_discern_img_url)
                    if response.status_code == 200:
                        rec.body_discern_img = base64.b64encode(response.content).decode('utf-8')
                except requests.exceptions.RequestException:
                    pass 
                
    @api.depends("user_id","app_id")
    def _compute_user_identity_id(self):
        for rec in self:
            user_identity_id = self.env["user.identity"].search(
                [("user_id", "=", rec.user_id.id),("app_id", "=", rec.app_id.id)], limit=1
            )
            rec.user_identity_id = user_identity_id.id if user_identity_id else False   
    
    @api.depends("collection_user_contact_ids.name")
    def _compute_from_user_contact(self):
        for rec in self:
            contacts = rec.collection_user_contact_ids
            rec.is_relative = f"aunt、uncle、friend; 数量：{len(contacts.filtered(lambda c: c.is_relative))}"
            rec.is_risk = f"bank、loan; 数量: {len(contacts.filtered(lambda c: c.is_risk))}"

    @api.depends("user_id","app_id")
    def _compute_collection_user_contact_ids(self):
        for rec in self:
            user_contact_id = self.env["user.contact"].search(
                [("user_id", "=", rec.user_id.id),("app_id", "=", rec.app_id.id)],limit=1
            )
            # 检查是否有现有的 collection.user.contact 记录  
            if rec.collection_user_contact_ids:  
                # 记录已存在，您可以选择继续处理  
                continue  
            else:  
                self.env['collection.user.contact'].create({  
                    'sequence':1,
                    'collection_order_id': rec.id,                                         
                    'name': rec.name,  
                    'phone_no': rec.phone_no,
                    'relation_selection': "oneself",
                },
                {  
                    'sequence':2,
                    'collection_order_id': rec.id,                                         
                    'name': user_contact_id.name_1,  
                    'phone_no': user_contact_id.phone_no_1,
                    'relation_selection': user_contact_id.relation_code_1,
                },
                {  
                    'sequence':3,
                    'collection_order_id': rec.id,                                         
                    'name': user_contact_id.name_2,  
                    'phone_no': user_contact_id.phone_no_2,
                    'relation_selection': user_contact_id.relation_code_2,
                },
                {  
                    'sequence':4,
                    'collection_order_id': rec.id,                                         
                    'name': user_contact_id.name_3,  
                    'phone_no': user_contact_id.phone_no_3,
                    'relation_selection': user_contact_id.relation_code_3,
                })                            
            
    @api.depends("user_id","app_id")
    def _compute_user_photo_set_id(self):
        for rec in self:
            user_photo_set_id = self.env["user.photo.set"].search(
                [("user_id", "=", rec.user_id.id),("app_id", "=", rec.app_id.id)], limit=1
            )
            rec.user_photo_set_id = user_photo_set_id.id if user_photo_set_id else False                

    @api.depends("user_id","app_id")
    def _compute_user_action_living_rec_id(self):
        for rec in self:
            user_action_living_rec_id = self.env["user.action.living.rec"].search(
                [("user_id", "=", rec.user_id.id),("app_id", "=", rec.app_id.id)], limit=1
            )
            rec.user_action_living_rec_id = user_action_living_rec_id.id if user_action_living_rec_id else False  
                   
    @api.depends("occupation_code_1")
    def _compute_occupation_code(self):
        for rec in self:
            rec.occupation_code = str(rec.occupation_code_1)
            
    @api.depends("gender_code_1")
    def _compute_gender_code(self):
        for rec in self:
            rec.gender_code = str(rec.gender_code_1) 
                       
    @api.depends("education_code_1")
    def _compute_education_code(self):
        for rec in self:
            rec.education_code = str(rec.education_code_1)  
            
    @api.depends("marital_status_code_1")
    def _compute_marital_status_code(self):
        for rec in self:
            rec.marital_status_code = str(rec.marital_status_code_1)
            
    @api.depends("housing_status_code_1")
    def _compute_housing_status_code(self):
        for rec in self:
            rec.housing_status_code = str(rec.housing_status_code_1)            
                               
    @api.depends("children_num_code_1")
    def _compute_children_num_code(self):
        for rec in self:
            rec.children_num_code = str(rec.children_num_code_1)    
            
    @api.depends("loan_purpose_code_1")
    def _compute_loan_purpose_code(self):
        for rec in self:
            rec.loan_purpose_code = str(rec.loan_purpose_code_1)  
                                       
    @api.depends("birth_date_1")
    def _compute_birth_date(self):
        for rec in self:
            rec.birth_date = date.fromtimestamp(rec.birth_date_1)                        
    
    @api.depends('user_id')
    def _compute_loan_orders(self):
        for rec in self:
            rec.loan_order_ids = rec.user_id.loan_order_ids.filtered(lambda x: x.id != self.loan_order_id.id and x.order_status in ["7", "8"])

    def action_server_collection_order_allot(self):
        """
        待分配订单action
        """
        context = self.env.context
        order_status_id = self.env["collection.order.status"].search(
            [("code", "=", "1")]
        )
        domain = [("order_status_id", "=", order_status_id.id)]
        # 获取所有记录并手动过滤 pending_amount > 0
        records = self.search(domain)
        filtered_ids = records.filtered(lambda r: r.pending_amount > 0).ids

        tree_view_id = self.env.ref("loan_collection.collection_order_allot_list")
        search_view_id = self.env.ref("loan_collection.collection_order_allot_search")
        action_id = self.env.ref("loan_collection.collection_order_allot_action")
        return {
            "id": action_id.id,
            "type": "ir.actions.act_window",
            "name": "待分配订单",
            "res_model": self._name,
            "view_mode": "tree",
            "view_id": tree_view_id.id,
            # "views": [(tree_view_id.id, "list")],
            "search_view_id": [search_view_id.id],
            "target": "current",
            "domain": [("id", "in", filtered_ids)],
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

        # 获取所有记录并手动过滤 pending_amount > 0
        records = self.search(domain)
        filtered_ids = records.filtered(lambda r: r.pending_amount > 0).ids

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
            "domain": [("id", "in", filtered_ids)],
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

        # 获取所有记录并手动过滤 pending_amount > 0
        records = self.search(domain)
        filtered_ids = records.filtered(lambda r: r.pending_amount > 0).ids

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
            "domain": [("id", "in", filtered_ids)],
            "context": dict(context),
        }

    def action_look_over(self):
        """
        列表点击查看按钮
        """
        return {  
            'type': 'ir.actions.act_window',  
            'name': '订单详情',  
            'res_model': self._name,  
            'res_id': self.id,  # 当前记录的ID  
            'view_mode': 'form',  
            'view_id':self.env.ref("loan_collection.form_collection_order").id,
            # 'target': 'new',  
        }  

    def action_follow_up(self):  
        """  
        列表点击跟进按钮  
        """  
        return {  
            "name": "订单详情",  
            "type": "ir.actions.act_window",  
            "res_model": self._name,  
            "res_id": self.id,  
            "view_mode": "form",  
            'view_id':self.env.ref("loan_collection.form_collection_order").id, 
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
        return {
            'name': '金额减免申请',
            'type': 'ir.actions.act_window',
            'res_model': "derate.record",
            'view_mode': 'form',
            'view_id': self.env.ref("loan_collection.form_derate_record_col_apply").id,
            'target': 'new',
            'context': {
                'dialog_size': self._action_default_size(), 
                'default_order_id': self.loan_order_id.id,
                "default_order_pending_amount": self.loan_order_id.pending_amount,
                'default_max_derate_amount': self.loan_order_id.can_derate_amount,
                'default_derate_type': "2",
                'default_col_approval_status': "1",
                'default_collection_stage_setting_id': self.collection_stage_setting_id.id
            }
        }

    def action_replacement_order(self):
        """列表点击补单按钮"""
        return self.loan_order_id.action_show_additional_record()

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

    def action_show_extension(self):
        """
        获取展期相关信息
        1. 判断是否允许展期
        """
        if not self.loan_order_id._check_order_can_extension():
            raise exceptions.UserError("该订单不符合展期条件，不能申请展期。")
        
        extension_record = self.env['extension.record'].search([('order_id', '=', self.loan_order_id.id), ("status", "not in", ["5", "6"])], limit=1)
        if not extension_record:
            extension_record = self.env['extension.record'].create({
                'order_id': self.loan_order_id.id,
                'status': "1",
                'extension_days': self.loan_order_id.loan_period,
                'extension_amount': self.loan_order_id.compute_extension_amount(),
                'order_repay_date': self.loan_order_id.repay_date,
            })
        pay_link_url = extension_record.get_pay_link()
        amount = extension_record.pending_amount
        return


class CollectionUserContact(models.Model):
    _name = "collection.user.contact"
    _table = "C_user_contact"
    _description = "用户联系人信息"

    sequence = fields.Integer(string="序号")
    name = fields.Char(string="联系人姓名")
    phone_no = fields.Char(string="电话号码")
    collection_order_id = fields.Many2one("collection.order", string="催收订单")
    can_edit = fields.Boolean(string="是否可编辑", default=True)
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
    add_user_id = fields.Many2one("res.users", string="操作人")
    add_date = fields.Datetime(string="补充时间")

    is_relative = fields.Boolean(string="是否为亲属号", compute="_compute_from_name")
    is_risk = fields.Boolean(string="是否为风险号", compute="_compute_from_name")
    
    @api.depends("name")
    def _compute_from_name(self):
        for rec in self:
            name = rec.name.lower()
            if name.count("aunt") or name.count("uncle") or name.count("friend"):
                rec.is_relative = True
            else:
                rec.is_relative = False
            
            if name.count("bank") or name.count("loan"):
                rec.is_risk = True
            else:
                rec.is_risk = False

    @api.model
    def create(self, vals):
        vals["add_user_id"] = self.env.user.id
        vals["add_date"] = datetime.now()
        return super(CollectionUserContact, self).create(vals)


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
    collection_stage = fields.Char(
        string="催收阶段",
        related="collection_order_id.collection_stage",
        store=True,
    )
    overdue_days = fields.Integer(string='逾期天数', related="collection_order_id.overdue_days",store=True,)
    

    @api.depends("collection_order_id")
    def _compute_sequence(self):
        for record in self.mapped("collection_order_id"):
            num = 0
            for line in record.history_collection_record_ids:
                num += 1
                line.update({"sequence": num})

    def create(self, vals: dict):
        """待处理的订单，催收员添加催收记录后，催收订单状态变更为：待放款"""
        res = super(HistoryCollectionRecord, self).create(vals)
        if res.collection_order_id.order_status_id.code in ("2", ):
            res.collection_order_id.write(
                {'order_status_id': self.env['collection.order.status'].sudo().search([('code', '=', '3')]).id}
            )
        return res


class HistoryLoansRecord(models.Model):
    _name = "history.loans.record"
    _table = "C_history_loans_record"
    _description = "历史贷款记录"

    collection_order_id = fields.Many2one("collection.order", string="催收订单")
    sequence = fields.Integer(string="序号", compute="_compute_sequence", store=True)
    loan_order_id = fields.Many2one("loan.order", string="关联订单")
    order_no = fields.Char(string="订单编号", related="loan_order_id.order_no", store=True)
    contract_amount = fields.Float(
        string="合同金额", related="loan_order_id.contract_amount"
    )
    borrow_money_date = fields.Integer(
        string="借款期限(天)", related="loan_order_id.loan_period", store=True
    )
    application_time = fields.Datetime(
        string="申请时间", related="loan_order_id.apply_time", store=True
    )
    product_id = fields.Many2one('loan.product',
        string="产品名称", index=True, related="loan_order_id.product_id"
    )
    app_id = fields.Many2one(
        "loan.app", string="App", related="loan_order_id.app_id", store=True
    )
    app_name = fields.Char(string="APP名称", related="app_id.app_name", store=True)
    loan_order_status_id = fields.Selection(selection=enums.ORDER_STATUS, default='1', string='财务订单状态')
    
    credit_examiner = fields.Many2one("res.users", string="信审员")
    credit_audit_reason = fields.Char(string="信审原因")
    collection_stage = fields.Char(
        string="催收阶段",
        related="collection_order_id.collection_stage",
        store=True,
    )
    overdue_days = fields.Integer(string='逾期天数', related="collection_order_id.overdue_days",store=True,)    
    collector_id = fields.Many2one("res.users", string="催收员",related="collection_order_id.collector_id",)
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

    def cron_auto_assign_orders(self):
        _logger.info("开始系统自动分单......")
        # 自动分单开关开启状态下，才会执行自动分单逻辑
        records = self.env['collection.auto.assign.orders'].search([], limit=1, order='write_date desc')
        if not records.auto_assign_orders:
            _logger.warning("系统自动分单功能已处于关闭状态")
            return {"success": False}
        order_status_allot = self.env["collection.order.status"].search([("code", "=", "1")], limit=1)
        order_status_pending = self.env["collection.order.status"].search([("code", "=", "2")], limit=1)
        # 获取所有的催收阶段配置
        collection_stage_setting_objects = self.env["collection.stage.setting"].search([
            ("status", "=", True),
            ("active", "=", True),
            ("status_select", "=", "active")
        ])
        collection_stage_setting_ids = [obj.id for obj in collection_stage_setting_objects]
        # 获取所有待处理的催收订单，如果催收员状态被设置为"关闭"，需要将订单改为待分配，进行重新分配
        collection_orders_pending = self.env['collection.order'].search([
            ("order_status_id", "=", order_status_pending.id),
            ("collection_stage_setting_id", "in", collection_stage_setting_ids)
        ]) or list()
        for collection_order_pending in collection_orders_pending:
            if collection_order_pending.collector_id.active is False:
                collection_order_pending.write({
                    'order_status_id': order_status_allot.id,
                    'collector_id': None
                })
        # 获取所有的催收员
        collector_objects = self.env["collection.points"].search([
            ("active", "=", True),
            ("is_input", "=", True),
            ("is_input_select", "=", "active"),
            ("collection_stage_id", "in", collection_stage_setting_ids)
        ])
        # 给催收员按照催收阶段，产品分组
        group_collectors = dict()
        for collector_object in collector_objects:
            if collector_object.collection_stage_id.id in group_collectors:
                stage_setting_group_coolectors = group_collectors[collector_object.collection_stage_id.id]
                for loan_product in collector_object.loan_product_ids:
                    if loan_product.id in stage_setting_group_coolectors:
                        product_group_coolectors = stage_setting_group_coolectors[loan_product.id]
                        product_group_coolectors.append(collector_object)
                        stage_setting_group_coolectors[loan_product.id] = product_group_coolectors
                    else:
                        stage_setting_group_coolectors[loan_product.id] = [collector_object]
            else:
                stage_setting_group_coolectors = dict()
                for loan_product in collector_object.loan_product_ids:
                    stage_setting_group_coolectors[loan_product.id] = [collector_object]
            group_collectors[collector_object.collection_stage_id.id] = stage_setting_group_coolectors
        # 获取所有待分配的订单
        collection_orders_allot = self.env['collection.order'].search([
            ("order_status_id", "=", order_status_allot.id),
            ("collection_stage_setting_id", "in", collection_stage_setting_ids)
        ])
        # 给待分配的订单按照催收阶段，产品分组
        group_orders = dict()
        for collection_order in collection_orders_allot:
            if collection_order.collection_stage_setting_id.id in group_orders:
                stage_setting_group_orders = group_orders[collection_order.collection_stage_setting_id.id]
                if collection_order.product_id.id in stage_setting_group_orders:
                    product_group_orders = stage_setting_group_orders[collection_order.product_id.id]
                    product_group_orders.append(collection_order)
                else:
                    product_group_orders = [collection_order]
                stage_setting_group_orders[collection_order.product_id.id] = product_group_orders
            else:
                product_group_orders = [collection_order]
                stage_setting_group_orders = {
                    collection_order.product_id.id: product_group_orders
                }
            group_orders[collection_order.collection_stage_setting_id.id] = stage_setting_group_orders
        # 开始自动分配订单，分单规则如下：
        # 1）同一催收阶段的订单，系统平均分配给的对应催收阶段的催收员；
        # 2）如果催收员“状态”为“关闭”，则系统不分配订单给该催收员；
        # 3）如果催收员今日已分配订单数量达到催收员“每日进件上限”，则系统不再分配订单给该催收员；
        # 4）如果订单所属产品不属于催收员“进件产品”范围，则系统不分配该订单给该催收员；
        # 5）如果所有催收员均已达到“每日进件”上限，则系统停止自动分单；新增计划任务，每隔1小时重新触发一次自动分单；
        # 6）如果催收员的“是否进件”状态临时调整为“关闭”，则系统不再分配订单给该催收员，该催收员名下待处理订单不做调整，仍保留在该催收员名下；
        # 7）如果催收员的系统账户状态被调整为“关闭”（设置-用户管理-用户），则系统不再分单给该催收员，同时将该催收员名下所有待处理订单重新转移到待分配订单列表，以重新进行分配。
        for stage_setting_id, stage_setting_group_orders in group_orders.items():
            stage_setting_group_collectors = group_collectors.get(stage_setting_id)
            if stage_setting_group_collectors:
                for product_id, product_group_orders in stage_setting_group_orders.items():
                    product_group_collectors = stage_setting_group_collectors.get(product_id)
                    if product_group_collectors:
                        for product_group_order in product_group_orders:
                            for product_group_collector in product_group_collectors:
                                today_allocated_qty = self.env['collector.link.order.record'].sudo().search_count([
                                    ('collector_id', '=', product_group_collector.user_id.id),
                                    ('allot_date', '=', date.today())
                                ])
                                if product_group_collector.max_daily_intake >= today_allocated_qty + 1:
                                    self.env.cr.execute(
                                        f'update "C_order" set order_status_id={order_status_pending.id},' +
                                        f'collector_id={product_group_collector.user_id.id} ' +
                                        f'where id={product_group_collector.id}'
                                    )
                                    self.env['collector.link.order.record'].sudo().create(
                                        {
                                            'company_id': product_group_order.company_id.id,
                                            'collector_id': product_group_collector.user_id.id,
                                            'collection_order_id': product_group_order.id,
                                            'allot_date': date.today()
                                        }
                                    )
                    else:
                        collection_order_ids = [product_group_order.id for product_group_order in product_group_orders]
                        _logger.warning(
                            f"当前催收阶段: <{stage_setting_id}>没有配置符合产品：{product_id}的催收员，无法给待分配的订单：{collection_order_ids}自动分配催收员"
                        )
            else:
                collection_order_ids = [product_group_order.id for product_group_orders in stage_setting_group_orders.values() for product_group_order in product_group_orders]
                _logger.warning(
                    f"当前催收阶段: <{stage_setting_id}>没有配置催收员，无法给待分配的订单：{collection_order_ids}自动分配催收员"
                )
