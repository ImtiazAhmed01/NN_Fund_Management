# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class FundRequisition(models.Model):
    _name = 'fund.requisition'
    _description = 'Fund Requisition'
    _order = 'request_date desc, id desc'
    _inherit = ['fund.approval.mixin', 'mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Requisition Number', default='/', readonly=True, copy=False)
    
    project_id = fields.Many2one('fund.project', string='Project', tracking=True)
    expense_head_id = fields.Many2one('fund.expense.head', string='Expense Head', tracking=True)
    
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency', 
        default=lambda self: self.env.company.currency_id, 
        required=True
    )
    
    amount = fields.Monetary(string='Requested Amount', required=True, currency_field='currency_id', tracking=True)
    purpose = fields.Text(string='Purpose', required=True)
    required_date = fields.Date(string='Required Date', required=True, tracking=True)
    
    attachment_ids = fields.Many2many(
        'ir.attachment', 
        'fund_requisition_attachment_rel', 
        'requisition_id', 'attachment_id', 
        string='Supporting Attachments'
    )
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        default=lambda self: self.env.company, 
        required=True
    )

    bill_ids = fields.One2many('fund.bill', 'requisition_id', string='Bills')

    spent_amount = fields.Monetary(
        string='Total Spent Amount', 
        compute='_compute_bill_balances', 
        currency_field='currency_id',
        store=True,
        readonly=True
    )
    remaining_billable_amount = fields.Monetary(
        string='Remaining Billable Amount', 
        compute='_compute_bill_balances', 
        currency_field='currency_id',
        store=True,
        readonly=True
    )

    @api.constrains('project_id', 'expense_head_id')
    def _check_project_or_expense_head(self):
        for rec in self:
            if not rec.project_id and not rec.expense_head_id:
                raise ValidationError(_("You must select either a Project or an Expense Head."))
            if rec.project_id and rec.expense_head_id:
                raise ValidationError(_("A requisition must use either a Project or an Expense Head, not both."))

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("The requisition amount must be greater than zero."))

    @api.depends('amount', 'state', 'bill_ids.amount', 'bill_ids.state')
    def _compute_bill_balances(self):
        for req in self:
            spent_amount = sum(req.bill_ids.filtered(lambda b: b.state == 'posted').mapped('amount'))
            
            # Remaining is only calculated if approved.
            if req.state == 'approved':
                remaining_billable_amount = max(0.0, req.amount - spent_amount)
            else:
                remaining_billable_amount = 0.0
                
            req.update({
                'spent_amount': spent_amount,
                'remaining_billable_amount': remaining_billable_amount
            })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('fund.requisition.sequence') or '/'
        return super(FundRequisition, self).create(vals_list)

    def _check_before_submit(self):
        super()._check_before_submit()
        if self.project_id:
            avail = self.project_id.available_fund
            if self.amount > avail:
                raise ValidationError(_("Requested amount (%s) exceeds available balance (%s) of project '%s'.") % (
                    self.amount, avail, self.project_id.name
                ))
        elif self.expense_head_id:
            avail = self.expense_head_id.available_fund
            if self.amount > avail:
                raise ValidationError(_("Requested amount (%s) exceeds available balance (%s) of expense head '%s'.") % (
                    self.amount, avail, self.expense_head_id.name
                ))

    def _log_approval_action(self, level, action, comment, amount=0.0, fund_account_id=None, project_id=None, expense_head_id=None):
        super()._log_approval_action(
            level=level,
            action=action,
            comment=comment,
            amount=self.amount,
            fund_account_id=None,
            project_id=self.project_id.id,
            expense_head_id=self.expense_head_id.id
        )

    def action_close(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_("Only approved requisitions can be closed."))
        
        self.state = 'closed'
        self._log_approval_action('User', 'close', _("Requisition closed. Remaining unspent balance released."))
        self.message_post(body=_("Requisition closed. Unused amount of %s %s was released back to the available balance.") % (
            self.remaining_billable_amount,
            self.currency_id.symbol
        ))
        return True

    def _on_approve(self):
        self.message_post(body=_("Requisition of %s %s was approved and reserved for bills.") % (
            self.amount, self.currency_id.symbol
        ))

    def _on_reject(self):
        self.message_post(body=_("Requisition rejected. Funds released."))

    def _on_cancel(self):
        self.message_post(body=_("Requisition cancelled. Funds released."))
