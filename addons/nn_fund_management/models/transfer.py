# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FundTransfer(models.Model):
    _name = 'fund.transfer'
    _description = 'Fund Transfer Request'
    _order = 'request_date desc, id desc'
    _inherit = ['fund.approval.mixin', 'mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Transfer Number', default='/', readonly=True, copy=False)
    
    src_project_id = fields.Many2one('fund.project', string='Source Project', tracking=True)
    src_expense_head_id = fields.Many2one('fund.expense.head', string='Source Expense Head', tracking=True)
    
    dest_project_id = fields.Many2one('fund.project', string='Destination Project', tracking=True)
    dest_expense_head_id = fields.Many2one('fund.expense.head', string='Destination Expense Head', tracking=True)
    
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency', 
        default=lambda self: self.env.company.currency_id, 
        required=True
    )
    
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id', tracking=True)
    reason = fields.Text(string='Reason', required=True)
    
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        default=lambda self: self.env.company, 
        required=True
    )

    @api.constrains('src_project_id', 'src_expense_head_id', 'dest_project_id', 'dest_expense_head_id')
    def _check_source_dest(self):
        for rec in self:
            # Source validations
            if not rec.src_project_id and not rec.src_expense_head_id:
                raise ValidationError(_("You must select a Source Project or Expense Head."))
            if rec.src_project_id and rec.src_expense_head_id:
                raise ValidationError(_("Source must be either a Project or an Expense Head, not both."))
            
            # Destination validations
            if not rec.dest_project_id and not rec.dest_expense_head_id:
                raise ValidationError(_("You must select a Destination Project or Expense Head."))
            if rec.dest_project_id and rec.dest_expense_head_id:
                raise ValidationError(_("Destination must be either a Project or an Expense Head, not both."))
            
            # Compare source and destination
            if rec.src_project_id and rec.dest_project_id and rec.src_project_id == rec.dest_project_id:
                raise ValidationError(_("Source and Destination projects cannot be the same."))
            if rec.src_expense_head_id and rec.dest_expense_head_id and rec.src_expense_head_id == rec.dest_expense_head_id:
                raise ValidationError(_("Source and Destination expense heads cannot be the same."))

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Transfer amount must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('fund.transfer.sequence') or '/'
        return super(FundTransfer, self).create(vals_list)

    def _check_before_submit(self):
        super()._check_before_submit()
        if self.src_project_id:
            avail = self.src_project_id.available_fund
            if self.amount > avail:
                raise ValidationError(_("Transfer amount (%s) exceeds available balance (%s) of source project '%s'.") % (
                    self.amount, avail, self.src_project_id.name
                ))
        elif self.src_expense_head_id:
            avail = self.src_expense_head_id.available_fund
            if self.amount > avail:
                raise ValidationError(_("Transfer amount (%s) exceeds available balance (%s) of source expense head '%s'.") % (
                    self.amount, avail, self.src_expense_head_id.name
                ))

    def _log_approval_action(self, level, action, comment, amount=0.0, fund_account_id=None, project_id=None, expense_head_id=None):
        super()._log_approval_action(
            level=level,
            action=action,
            comment=comment,
            amount=self.amount,
            fund_account_id=None,
            project_id=self.src_project_id.id or self.dest_project_id.id,
            expense_head_id=self.src_expense_head_id.id or self.dest_expense_head_id.id
        )

    def _on_approve(self):
        src_name = self.src_project_id.display_name if self.src_project_id else self.src_expense_head_id.display_name
        dest_name = self.dest_project_id.display_name if self.dest_project_id else self.dest_expense_head_id.display_name
        self.message_post(body=_("Transfer of %s %s from %s to %s was approved.") % (
            self.amount, self.currency_id.symbol, src_name, dest_name
        ))

    def _on_reject(self):
        self.message_post(body=_("Transfer rejected. Funds returned to source balance."))

    def _on_cancel(self):
        self.message_post(body=_("Transfer cancelled. Funds returned to source balance."))
