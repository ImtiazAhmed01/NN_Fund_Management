# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class IncomingFund(models.Model):
    _name = 'incoming.fund'
    _description = 'Incoming Fund'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Transaction Code', default='/', readonly=True, copy=False)
    fund_account_id = fields.Many2one('fund.account', string='Fund Account', required=True, tracking=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, tracking=True)
    
    currency_id = fields.Many2one('res.currency', related='fund_account_id.currency_id', readonly=True, store=True)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id', tracking=True)
    
    reference = fields.Char(string='Transaction Reference', required=True, tracking=True)
    sender = fields.Char(string='Sender / Source', required=True, tracking=True)
    description = fields.Text(string='Description')
    
    attachment_ids = fields.Many2many(
        'ir.attachment', 
        'incoming_fund_attachment_rel', 
        'fund_id', 'attachment_id', 
        string='Attachments'
    )
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        default=lambda self: self.env.company, 
        required=True
    )
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed')
    ], string='Status', default='draft', readonly=True, tracking=True, copy=False)

    @api.constrains('amount')
    def _check_amount(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_("The incoming fund amount must be greater than zero."))

    @api.constrains('reference', 'fund_account_id')
    def _check_unique_reference(self):
        for record in self:
            if record.reference and record.fund_account_id:
                domain = [
                    ('reference', '=', record.reference),
                    ('fund_account_id', '=', record.fund_account_id.id),
                    ('id', '!=', record.id)
                ]
                duplicate = self.search(domain, limit=1)
                if duplicate:
                    raise ValidationError(_("The transaction reference '%s' is already used in fund account '%s'.") % (record.reference, record.fund_account_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('incoming.fund.sequence') or '/'
        return super(IncomingFund, self).create(vals_list)

    def action_confirm(self):
        self.ensure_one()
        if self.status != 'draft':
            raise UserError(_("Only draft incoming funds can be confirmed."))
            
        # Security check: Only finance users or administrators can confirm
        if not self.env.user.has_group('nn_fund_management.group_finance_user') and not self.env.user.has_group('nn_fund_management.group_fund_admin'):
            raise UserError(_("Only authorized Finance Users or Fund Administrators can confirm incoming funds."))

        self.status = 'confirmed'
        
        # Log to chatter
        self.message_post(body=_("Incoming fund of %s %s was confirmed by %s.") % (self.amount, self.currency_id.symbol, self.env.user.name))
        return True
