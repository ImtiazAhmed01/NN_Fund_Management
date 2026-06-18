# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FundProject(models.Model):
    _name = 'fund.project'
    _description = 'Fund Project'
    _order = 'name asc'

    name = fields.Char(string='Project Name', required=True)
    code = fields.Char(string='Project Code', required=True)
    
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

    allocation_ids = fields.One2many('fund.allocation', 'project_id', string='Allocations')
    incoming_transfer_ids = fields.One2many('fund.transfer', 'dest_project_id', string='Incoming Transfers Link')
    outgoing_transfer_ids = fields.One2many('fund.transfer', 'src_project_id', string='Outgoing Transfers Link')
    requisition_ids = fields.One2many('fund.requisition', 'project_id', string='Requisitions')

    total_allocated = fields.Monetary(
        string='Total Allocated Fund', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True,
        readonly=True
    )
    available_fund = fields.Monetary(
        string='Available Fund', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True,
        readonly=True
    )
    requisition_hold = fields.Monetary(
        string='Requisition Hold', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True,
        readonly=True
    )
    transfer_hold = fields.Monetary(
        string='Transfer Hold', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True,
        readonly=True
    )
    approved_unspent = fields.Monetary(
        string='Approved but Unspent Amount', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True,
        readonly=True
    )
    total_spent_amount = fields.Monetary(
        string='Total Spent Amount', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True,
        readonly=True
    )
    incoming_transfers = fields.Monetary(
        string='Incoming Transfers', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True,
        readonly=True
    )
    outgoing_transfers = fields.Monetary(
        string='Outgoing Transfers', 
        compute='_compute_balances', 
        currency_field='currency_id',
        store=True,
        readonly=True
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)', 'The project code must be unique per company!')
    ]

    @api.constrains('available_fund')
    def _check_negative_balance(self):
        for project in self:
            if project.available_fund < 0:
                raise ValidationError(_("Negative balance is not allowed. Project '%s' would have a negative available fund of %s.") % (project.name, project.available_fund))

    @api.depends(
        'allocation_ids.amount', 'allocation_ids.state',
        'incoming_transfer_ids.amount', 'incoming_transfer_ids.state',
        'outgoing_transfer_ids.amount', 'outgoing_transfer_ids.state',
        'requisition_ids.amount', 'requisition_ids.state', 
        'requisition_ids.remaining_billable_amount', 'requisition_ids.spent_amount'
    )
    def _compute_balances(self):
        for project in self:
            # 1. Total Allocated
            total_allocated = sum(project.allocation_ids.filtered(lambda a: a.state == 'approved').mapped('amount'))
            
            # 2. Incoming Transfers
            incoming_transfers = sum(project.incoming_transfer_ids.filtered(lambda t: t.state == 'approved').mapped('amount'))
            
            # 3. Outgoing Transfers
            outgoing_transfers = sum(project.outgoing_transfer_ids.filtered(lambda t: t.state == 'approved').mapped('amount'))
            
            # 4. Transfer Hold
            transfer_hold = sum(project.outgoing_transfer_ids.filtered(lambda t: t.state in ['submitted', 'gm_approved']).mapped('amount'))
            
            # 5. Requisition Hold
            requisition_hold = sum(project.requisition_ids.filtered(lambda r: r.state in ['submitted', 'gm_approved']).mapped('amount'))
            
            # 6. Spent Amount
            total_spent_amount = sum(project.requisition_ids.mapped('spent_amount'))
            
            # 7. Approved but Unspent
            approved_unspent = sum(project.requisition_ids.filtered(lambda r: r.state == 'approved').mapped('remaining_billable_amount'))
            
            # Available Fund Formula
            available_fund = total_allocated + incoming_transfers - outgoing_transfers - transfer_hold - requisition_hold - approved_unspent - total_spent_amount
            
            project.update({
                'total_allocated': total_allocated,
                'incoming_transfers': incoming_transfers,
                'outgoing_transfers': outgoing_transfers,
                'transfer_hold': transfer_hold,
                'requisition_hold': requisition_hold,
                'total_spent_amount': total_spent_amount,
                'approved_unspent': approved_unspent,
                'available_fund': available_fund
            })

    def name_get(self):
        result = []
        for project in self:
            name = f"[{project.code}] {project.name}"
            result.append((project.id, name))
        return result
