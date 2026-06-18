# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class FundAccount(models.Model):
    _name = 'fund.account'
    _description = 'Fund Account'
    _order = 'name asc'

    name = fields.Char(string='Account Name', required=True)
    account_number = fields.Char(string='Account Number', required=True)
    
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency', 
        default=lambda self: self.env.company.currency_id, 
        required=True
    )
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        default=lambda self: self.env.company, 
        required=True
    )

    incoming_fund_ids = fields.One2many('incoming.fund', 'fund_account_id', string='Incoming Funds')
    allocation_ids = fields.One2many('fund.allocation', 'fund_account_id', string='Allocations')

    total_received = fields.Monetary(
        string='Total Received', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True
    )
    available_unassigned_balance = fields.Monetary(
        string='Available Unassigned Balance', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True
    )
    amount_held = fields.Monetary(
        string='Amount Currently on Hold', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True
    )
    total_assigned = fields.Monetary(
        string='Total Assigned Amount', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True
    )

    _sql_constraints = [
        ('account_uniq', 'unique(name, account_number, company_id)', 'The fund account name and account number must be unique per company!')
    ]

    @api.depends(
        'incoming_fund_ids.amount', 'incoming_fund_ids.status',
        'allocation_ids.amount', 'allocation_ids.state'
    )
    def _compute_balances(self):
        for account in self:
            # 1. Total Received (Only Confirmed incoming funds)
            total_received = sum(account.incoming_fund_ids.filtered(lambda f: f.status == 'confirmed').mapped('amount'))
            
            # 2. Total Assigned (Only Approved allocations)
            total_assigned = sum(account.allocation_ids.filtered(lambda a: a.state == 'approved').mapped('amount'))
            
            # 3. Amount Held (Allocations submitted or GM approved, but not yet approved or rejected)
            amount_held = sum(account.allocation_ids.filtered(lambda a: a.state in ['submitted', 'gm_approved']).mapped('amount'))
            
            # 4. Available Unassigned Balance
            available_unassigned_balance = total_received - total_assigned - amount_held
            
            account.update({
                'total_received': total_received,
                'total_assigned': total_assigned,
                'amount_held': amount_held,
                'available_unassigned_balance': available_unassigned_balance
            })

    def name_get(self):
        result = []
        for account in self:
            name = f"{account.name} ({account.account_number})"
            result.append((account.id, name))
        return result
