# -*- coding: utf-8 -*-
"""
# ---------------------------------------------------------------------------------------------------------
# ProjectName:  admin
# FileName:     loan_settings_user.py
# Description:  TODO
# Author:       zw
# CreateDate:   2024/10/30
# Copyright ©2011-2024. Hunan xxxxxxx Company limited. All rights reserved.
# ---------------------------------------------------------------------------------------------------------
"""
from odoo import models, fields, _, api
from ..libs.converter import ModelKwargsConverter


class LoanSettingUsers(models.Model):
    _name = 'loan.settings.user'
    _description = 'User'
    _table = 'R_user'
    _inherit = 'loan.basic.model'
    _rec_name = 'name'

    sequence = fields.Char(string=_('UserID'), index=True, required=True)
    is_collection = fields.Boolean(string=_('是否为催收员'), default=False)
    res_user_id = fields.Many2one("res.users", string="User", required=True, index=True, auto_join=True)
    res_partner_id = fields.Many2one("res.partner", string="Partner", required=True, index=True, auto_join=True)
    login = fields.Char(string=_('Login'), related="res_user_id.login", store=False)
    password = fields.Char(string=_("Password"), related="res_user_id.password", store=False)
    name = fields.Char(string=_('Username'), related='res_partner_id.name', store=False)
    phone = fields.Char(string=_('Phone'), related='res_partner_id.phone', store=False)
    lang = fields.Selection(string=_('Language'), related='res_partner_id.lang', store=False)
    tz = fields.Selection(string=_('Timezone'), related='res_partner_id.tz', store=False)
    merchant_id = fields.Many2one('loan.settings.merchant', string=_('Belong Merchant'), required=True, auto_join=True)
    res_company_id = fields.Many2one('res.company', string='Company', required=True, auto_join=True)
    team_id = fields.Many2one('loan.settings.team', string=_('Belong Team'), required=True, auto_join=True)
    hr_depart_id = fields.Many2one('hr.department', string='Department', required=True, auto_join=True)
    role_ids = fields.Many2many(
        'loan.settings.role',
        'R_role_user_rel',
        'uid',
        'rid',
        ondelete='restrict',
        string=_('Role')
    )
    # 新增的 Many2many 字段，用于关联下属用户
    subordinates_ids = fields.Many2many(
        'loan.settings.user',
        'R_user_subordinates_rel'
        'uid',
        'did',
        string=_('Subordinates')
    )

    active = fields.Boolean(string=_('Enable'), default=True)
    formatted_create_date = fields.Char(string=_("Created on"), compute='_compute_formatted_create_date')
    formatted_write_date = fields.Char(string=_("Last Updated on"), compute='_compute_formatted_write_date')

    def create(self, vals):
        vals['sequence'] = self.env['ir.sequence'].next_by_code('user_code_seq')
        res_company_id = self.env['loan.settings.merchant'].browse([vals.get("merchant_id")]).company_id.id
        hr_depart_id = self.env['loan.settings.team'].browse([vals.get("team_id")]).hr_depart_id.id
        partner_kwargs = ModelKwargsConverter.get_res_partner_kwargs(vals=vals)
        partner_kwargs.update(dict(company_id=res_company_id))
        partner = self.env['res.partner'].sudo().create(partner_kwargs)
        add_group_ids, _ = ModelKwargsConverter.parse_many2many_args(*vals.get('role_ids'))
        role_ids = self.env['loan.settings.role'].sudo().browse(add_group_ids)
        raw_role_ids = [role_id.res_groups_id.id for role_id in role_ids]
        res_users = self.env['res.users'].sudo().create(
            {
                'company_id': res_company_id,
                'partner_id': partner.id,
                'login': vals.get('login'),
                'dialog_size': 'minimize',
                'notification_type': 'email',
                'sidebar_type': 'large',
                'chatter_position': 'side',
                'company_ids': [(4, res_company_id)]
            }
        )
        self.env['res.users'].browse(res_users.id)._change_password(vals.get('password'))
        self.env['res.groups'].browse(raw_role_ids).write(
            {
                "users": [(4, res_users.id)]
            }
        )
        admin_ids = list()
        self.env.cr.execute("select * from res_groups")
        # 获取查询结果
        res_groups_ids = self.env.cr.fetchall()
        for res_groups_id in res_groups_ids:
            if res_groups_id[1].get("en_US") == "Administrator":
                admin_ids.append(str(res_groups_id[0]))
        if admin_ids:
            del_sql = f"delete from res_groups_users_rel where uid={res_users.id} and gid in ({','.join(admin_ids)})"
            self.env.cr.execute(del_sql)
        vals['res_user_id'] = res_users.id
        vals['hr_depart_id'] = hr_depart_id
        vals['res_partner_id'] = partner.id
        vals['company_id'] = vals['res_company_id'] = res_company_id
        record = super(LoanSettingUsers, self).create(vals)
        self.env['collection.points'].sudo().create({
            'sequence': self.env['ir.sequence'].next_by_code('collection.points'),
            'user_id': record.id,
            'group_id': self.env.ref('loan_collection.loan_collector_group').id,
            'collection_stage_id': False,
            'department_id': hr_depart_id,
            'is_input': False,
            'loan_product_ids': self.env['loan.product'].sudo().search([]).ids,
            'is_input_select': 'stop',
            'active': record.has_group('loan_collection.loan_collector_group')
        })
        record.sudo().write({'is_collection': record.has_group('loan_collection.loan_collector_group')})
        return super(LoanSettingUsers, self).create(vals)

    def write(self, vals):
        if 'active' in vals and vals['active'] is False:
            self.env.cr.execute(
                "update res_partner set active='f' where id=%s", (self.res_partner_id.id,)
            )
            self.env.cr.execute(
                "update res_users set active='f' where id=%s", (self.res_user_id.id,)
            )
            return super(LoanSettingUsers, self).write({'active': False})
        elif 'active' in vals and vals['active'] is True:
            self.env.cr.execute(
                "update res_partner set active='t' where id=%s", (self.res_partner_id.id,)
            )
            self.env.cr.execute(
                "update res_users set active='t' where id=%s", (self.res_user_id.id,)
            )
            return super(LoanSettingUsers, self).write({'active': True})
        else:
            if "merchant_id" in vals:
                res_company_id = self.env['loan.settings.merchant'].browse([vals.get("merchant_id")]).company_id.id
                vals['company_id'] = vals['res_company_id'] = res_company_id
                self.env.cr.execute(
                    'delete from res_company_users_rel where cid=%s and user_id=%s',
                    (self.res_user_id.company_id.id, self.res_user_id.id)
                )
                self.env['res.users'].browse(self.res_user_id.id).write(
                    {
                        'company_id': res_company_id,
                        'company_ids': [(4, res_company_id)]
                    }
                )
            if "team_id" in vals:
                vals['hr_depart_id'] = self.env['loan.settings.team'].browse([vals.get("team_id")]).hr_depart_id.id
            if vals.get('name'):
                vals['complete_name'] = vals.get('name')
            role_ids = vals.get('role_ids', list()) or list()
            partner_kwargs = ModelKwargsConverter.get_res_partner_kwargs(vals=vals)
            if partner_kwargs:
                self.env['res.partner'].browse(self.res_partner_id.id).write(partner_kwargs)
            add_group_ids, del_group_ids = ModelKwargsConverter.parse_many2many_args(*role_ids)
            if add_group_ids:
                add_role_ids = self.env['loan.settings.role'].sudo().browse(add_group_ids)
                raw_role_ids = [role_id.res_groups_id.id for role_id in add_role_ids]
                self.env['res.groups'].browse(raw_role_ids).write(
                    {
                        "users": [(4, self.res_user_id.id)]
                    }
                )
            if del_group_ids:
                del_role_ids = self.env['loan.settings.role'].sudo().browse(del_group_ids)
                raw_role_ids = [role_id.res_groups_id.id for role_id in del_role_ids]
                self.env['res.groups'].browse(raw_role_ids).write(
                    {
                        "users": [(3, self.res_user_id.id)]
                    }
                )
            result = super(LoanSettingUsers, self).write(vals)
            for record in self:
                # 检查用户是否是催收员，并确保在正确的上下文中使用
                if record.has_group('loan_collection.loan_collector_group'):
                    is_collection_collector = True

                    # 使用 sudo 来确保我们具备足够的权限去访问其他模型
                    points_ids = record.env['collection.points'].sudo().search([('user_id', '=', record.res_user_id)])

                    # 更新分单管理的活动状态
                    for points_id in points_ids:
                        points_id.active = is_collection_collector
            # 调用父类的 write 方法，确保数据的正常更新
            return result

    # def unlink(self):
    #     self.env['res.partner'].sudo().search([('id', 'in', self.res_partner_id.id)]).unlink()
    #     删除对应用户分单管理
    # self.env['collection.points'].sudo().search([('user_id', 'in', self.ids)]).unlink()
    # return super(LoanSettingUsers, self).unlink()

    @api.depends('create_date')
    def _compute_formatted_create_date(self):
        # 将时间转换为用户时区
        user_tz = self.env.user.tz or 'UTC'
        for record in self:
            create_date = fields.Datetime.context_timestamp(self, record.create_date)
            record.formatted_create_date = create_date.strftime('%Y-%m-%d %H:%M:%S') if create_date else ''

    @api.depends('write_date')
    def _compute_formatted_write_date(self):
        # 将时间转换为用户时区
        user_tz = self.env.user.tz or 'UTC'
        for record in self:
            write_date = fields.Datetime.context_timestamp(self, record.write_date)
            record.formatted_write_date = write_date.strftime('%Y-%m-%d %H:%M:%S') if write_date else ''
