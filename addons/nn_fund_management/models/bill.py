# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class FundBill(models.Model):
    _name = 'fund.bill'
    _description = 'Fund Bill'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Bill Number', default='/', readonly=True, copy=False)
    requisition_id = fields.Many2one(
        'fund.requisition', 
        string='Fund Requisition', 
        required=True, 
        domain="[('state', '=', 'approved')]",
        tracking=True
    )
    
    project_id = fields.Many2one('fund.project', related='requisition_id.project_id', string='Project', readonly=True, store=True)
    expense_head_id = fields.Many2one('fund.expense.head', related='requisition_id.expense_head_id', string='Expense Head', readonly=True, store=True)
    currency_id = fields.Many2one('res.currency', related='requisition_id.currency_id', string='Currency', readonly=True, store=True)
    
    amount = fields.Monetary(string='Bill Amount', required=True, currency_field='currency_id', tracking=True)
    date = fields.Date(string='Bill Date', required=True, default=fields.Date.context_today, tracking=True)
    vendor = fields.Char(string='Vendor / Beneficiary', required=True, tracking=True)
    ref = fields.Char(string='Vendor Invoice Ref', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', readonly=True, tracking=True, copy=False)
    
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        default=lambda self: self.env.company, 
        required=True
    )

    @api.constrains('requisition_id')
    def _check_requisition_state(self):
        for bill in self:
            if bill.requisition_id and bill.requisition_id.state != 'approved':
                raise ValidationError(_("Only approved requisitions can be linked to bills. Requisition %s is in state '%s'.") % (
                    bill.requisition_id.name, bill.requisition_id.state
                ))

    @api.constrains('amount', 'requisition_id')
    def _check_amount(self):
        for bill in self:
            if bill.amount <= 0:
                raise ValidationError(_("The bill amount must be greater than zero."))
            if bill.requisition_id:
                # Calculate the maximum allowed amount.
                # If the current bill is already posted, we should include its amount in the limit.
                limit = bill.requisition_id.remaining_billable_amount
                if bill.state == 'posted':
                    limit += bill.amount
                
                if bill.amount > limit:
                    raise ValidationError(_("Bill amount (%s) exceeds the remaining billable amount (%s) of requisition '%s'.") % (
                        bill.amount, limit, bill.requisition_id.name
                    ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('fund.bill.sequence') or '/'
        return super(FundBill, self).create(vals_list)

    def action_post(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Only draft bills can be posted."))
            
        # Re-check limit before posting
        limit = self.requisition_id.remaining_billable_amount
        if self.amount > limit:
            raise ValidationError(_("Cannot post bill. Amount (%s) exceeds the remaining billable amount (%s) of requisition '%s'.") % (
                self.amount, limit, self.requisition_id.name
            ))

        self.state = 'posted'
        
        # Log to chatter
        self.message_post(body=_("Bill of %s %s was posted by %s.") % (self.amount, self.currency_id.symbol, self.env.user.name))
        return True

    def action_cancel(self):
        self.ensure_one()
        if self.state not in ['draft', 'posted']:
            raise UserError(_("You cannot cancel a bill in this state."))
            
        # Only admin or finance user can cancel approved/posted bills
        if self.state == 'posted' and not self.env.user.has_group('nn_fund_management.group_fund_admin') and not self.env.user.has_group('nn_fund_management.group_finance_user'):
            raise UserError(_("Only Finance Users or Fund Administrators can cancel a posted bill."))

        self.state = 'cancelled'
        self.message_post(body=_("Bill cancelled. Billed amount of %s %s has been returned to requisition's remaining balance.") % (
            self.amount, self.currency_id.symbol
        ))
        return True
