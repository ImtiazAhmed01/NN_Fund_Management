# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FundAllocation(models.Model):
    _name = 'fund.allocation'
    _description = 'Fund Allocation Request'
    _order = 'request_date desc, id desc'
    _inherit = ['fund.approval.mixin', 'mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Request Number', default='/', readonly=True, copy=False)
    fund_account_id = fields.Many2one('fund.account', string='Fund Account', required=True, tracking=True)
    
    project_id = fields.Many2one('fund.project', string='Project', tracking=True)
    expense_head_id = fields.Many2one('fund.expense.head', string='Expense Head', tracking=True)
    
    currency_id = fields.Many2one('res.currency', related='fund_account_id.currency_id', readonly=True, store=True)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id', tracking=True)
    purpose = fields.Text(string='Purpose', required=True)
    
    attachment_ids = fields.Many2many(
        'ir.attachment', 
        'fund_allocation_attachment_rel', 
        'allocation_id', 'attachment_id', 
        string='Supporting Attachments'
    )
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        default=lambda self: self.env.company, 
        required=True
    )

    @api.constrains('project_id', 'expense_head_id')
    def _check_project_or_expense_head(self):
        for rec in self:
            if not rec.project_id and not rec.expense_head_id:
                raise ValidationError(_("You must select either a Project or an Expense Head."))
            if rec.project_id and rec.expense_head_id:
                raise ValidationError(_("An allocation request must use either a Project or an Expense Head, not both."))

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("The allocation amount must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('fund.allocation.sequence') or '/'
        return super(FundAllocation, self).create(vals_list)

    def _check_before_submit(self):
        super()._check_before_submit()
        # Ensure account has enough available unassigned balance
        if self.amount > self.fund_account_id.available_unassigned_balance:
            raise ValidationError(_("Requested amount (%s) exceeds the available unassigned balance (%s) of fund account '%s'.") % (
                self.amount, self.fund_account_id.available_unassigned_balance, self.fund_account_id.name
            ))

    def _log_approval_action(self, level, action, comment, amount=0.0, fund_account_id=None, project_id=None, expense_head_id=None):
        # Always inject the current record details
        super()._log_approval_action(
            level=level,
            action=action,
            comment=comment,
            amount=self.amount,
            fund_account_id=self.fund_account_id.id,
            project_id=self.project_id.id,
            expense_head_id=self.expense_head_id.id
        )

    def _on_approve(self):
        # On MD approval, write to chatter
        self.message_post(body=_("Allocation request of %s %s to %s was approved and assigned.") % (
            self.amount, 
            self.currency_id.symbol, 
            self.project_id.display_name if self.project_id else self.expense_head_id.display_name
        ))

    def _on_reject(self):
        self.message_post(body=_("Allocation request rejected. Funds returned to unassigned balance."))

    def _on_cancel(self):
        self.message_post(body=_("Allocation request cancelled. Funds returned to unassigned balance."))
