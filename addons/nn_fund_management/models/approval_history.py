# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class FundApprovalHistory(models.Model):
    _name = 'fund.approval.history'
    _description = 'Fund Approval History Log'
    _order = 'action_date desc'

    model_name = fields.Char(string='Related Model', required=True)
    res_id = fields.Integer(string='Related Record ID', required=True)
    user_id = fields.Many2one('res.users', string='Actor / Approver', required=True)
    action_date = fields.Datetime(string='Date & Time', default=fields.Datetime.now, required=True)
    action = fields.Selection([
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ('cancel', 'Cancelled')
    ], string='Action Taken', required=True)
    level = fields.Char(string='Approval Level', help="e.g. User, GM, MD")
    comment = fields.Text(string='Comments / Reason')
    
    # Financial fields for reporting/audit context
    amount = fields.Float(string='Amount')
    fund_account_id = fields.Many2one('fund.account', string='Related Fund Account')
    project_id = fields.Many2one('fund.project', string='Related Project')
    expense_head_id = fields.Many2one('fund.expense.head', string='Related Expense Head')
    state_from = fields.Char(string='Previous Status')
    
    # Reference document display
    ref_doc = fields.Char(string='Reference Document', compute='_compute_ref_doc')

    @api.depends('model_name', 'res_id')
    def _compute_ref_doc(self):
        for log in self:
            if log.model_name and log.res_id:
                try:
                    record = self.env[log.model_name].browse(log.res_id)
                    if record.exists():
                        log.ref_doc = record.display_name or f"{log.model_name},{log.res_id}"
                    else:
                        log.ref_doc = f"Deleted: {log.model_name}({log.res_id})"
                except Exception:
                    log.ref_doc = f"{log.model_name}({log.res_id})"
            else:
                log.ref_doc = '/'
