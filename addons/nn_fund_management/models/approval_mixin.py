# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ResUsers(models.Model):
    _inherit = 'res.users'

    allow_self_approval = fields.Boolean(
        string='Allow Self Approval',
        help='If checked, this user can approve their own fund allocations/requisitions/transfers.',
        default=False
    )


class FundApprovalMixin(models.AbstractModel):
    _name = 'fund.approval.mixin'
    _description = 'Fund Approval Mixin'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Pending GM Approval'),
        ('gm_approved', 'Pending MD Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True, copy=False)

    requested_by = fields.Many2one(
        'res.users', 
        string='Requested By', 
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    request_date = fields.Date(
        string='Request Date', 
        default=fields.Date.context_today,
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    approval_history_ids = fields.One2many(
        'fund.approval.history', 
        'res_id', 
        string='Approval History',
        domain=lambda self: [('model_name', '=', self._name)],
        auto_join=True
    )

    # Helper method to log history
    def _log_approval_action(self, level, action, comment, amount=0.0, fund_account_id=None, project_id=None, expense_head_id=None):
        self.env['fund.approval.history'].create({
            'model_name': self._name,
            'res_id': self.id,
            'user_id': self.env.user.id,
            'action_date': fields.Datetime.now(),
            'action': action,
            'level': level,
            'comment': comment,
            'amount': amount,
            'fund_account_id': fund_account_id,
            'project_id': project_id,
            'expense_head_id': expense_head_id,
            'state_from': self.state,
        })

    def action_submit(self):
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_("You can only submit draft requests."))
        
        # Child classes will implement specific validations here (e.g. balance check)
        self._check_before_submit()
        
        self.state = 'submitted'
        self._log_approval_action('User', 'submit', _('Request submitted for approval.'))
        self._notify_approvers('submitted')
        return True

    def action_gm_approve(self, comment=False):
        self.ensure_one()
        if self.state != 'submitted':
            raise ValidationError(_("Request must be in 'Pending GM Approval' state."))
        
        # Check security: must be GM Approver
        if not self.env.user.has_group('nn_fund_management.group_gm_approver') and not self.env.user.has_group('nn_fund_management.group_fund_admin'):
            raise ValidationError(_("Only GM Approvers can perform GM approval."))
        
        # Check self-approval
        if self.requested_by == self.env.user:
            if not self.env.user.allow_self_approval and not self.env.user.has_group('nn_fund_management.group_fund_admin'):
                raise ValidationError(_("You cannot approve your own request unless specially authorized."))

        self._check_before_gm_approve()
        
        self.state = 'gm_approved'
        self._log_approval_action('GM', 'approve', comment or _('GM Approved.'))
        self._notify_approvers('gm_approved')
        return True

    def action_md_approve(self, comment=False):
        self.ensure_one()
        if self.state != 'gm_approved':
            raise ValidationError(_("Request must be in 'Pending MD Approval' state."))
        
        # Check security: must be MD Approver
        if not self.env.user.has_group('nn_fund_management.group_md_approver') and not self.env.user.has_group('nn_fund_management.group_fund_admin'):
            raise ValidationError(_("Only MD Approvers can perform MD approval."))
        
        # Check self-approval
        if self.requested_by == self.env.user:
            if not self.env.user.allow_self_approval and not self.env.user.has_group('nn_fund_management.group_fund_admin'):
                raise ValidationError(_("You cannot approve your own request unless specially authorized."))

        self._check_before_md_approve()
        
        # Execute post-approval logic (e.g., actual fund moves/updates)
        self._on_approve()
        
        self.state = 'approved'
        self._log_approval_action('MD', 'approve', comment or _('MD Approved. Request is now fully approved.'))
        return True

    def action_reject(self, comment=False):
        self.ensure_one()
        if self.state not in ['submitted', 'gm_approved']:
            raise ValidationError(_("You can only reject pending requests."))
        
        # Determine level based on current state
        level = 'GM' if self.state == 'submitted' else 'MD'
        
        # Check security
        if level == 'GM':
            if not self.env.user.has_group('nn_fund_management.group_gm_approver') and not self.env.user.has_group('nn_fund_management.group_fund_admin'):
                raise ValidationError(_("Only GM Approvers can reject this request at this stage."))
        else:
            if not self.env.user.has_group('nn_fund_management.group_md_approver') and not self.env.user.has_group('nn_fund_management.group_fund_admin'):
                raise ValidationError(_("Only MD Approvers can reject this request at this stage."))

        # Check self-approval
        if self.requested_by == self.env.user:
            if not self.env.user.allow_self_approval and not self.env.user.has_group('nn_fund_management.group_fund_admin'):
                raise ValidationError(_("You cannot reject/approve your own request unless specially authorized."))

        if not comment:
            raise ValidationError(_("Please provide a comment/reason for rejection."))

        self._on_reject()
        
        self.state = 'rejected'
        self._log_approval_action(level, 'reject', comment)
        return True

    def action_cancel(self):
        self.ensure_one()
        if self.state not in ['draft', 'submitted', 'gm_approved', 'approved']:
            raise ValidationError(_("You cannot cancel a request in this state."))
        
        # Check permissions: only authorized users can cancel approved transactions
        if self.state == 'approved' and not self.env.user.has_group('nn_fund_management.group_fund_admin') and not self.env.user.has_group('nn_fund_management.group_finance_user'):
            raise ValidationError(_("Only Finance Users or Fund Administrators can cancel an approved transaction."))
            
        self._on_cancel()
        
        self.state = 'cancelled'
        self._log_approval_action('User', 'cancel', _('Request cancelled.'))
        return True

    # Hooks for child classes
    def _check_before_submit(self):
        pass

    def _check_before_gm_approve(self):
        pass

    def _check_before_md_approve(self):
        pass

    def _on_approve(self):
        pass

    def _on_reject(self):
        pass

    def _on_cancel(self):
        pass

    def _notify_approvers(self, state):
        # Create an Odoo activity or notification for the approver group
        group_xml_id = 'group_gm_approver' if state == 'submitted' else 'group_md_approver'
        group = self.env.ref('nn_fund_management.%s' % group_xml_id)
        if group:
            for user in group.users:
                # Create activity for each user in the group
                try:
                    self.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary=_('Approval Required: %s') % (self.display_name or ''),
                        note=_('A request is pending your approval.'),
                        user_id=user.id
                    )
                except Exception:
                    pass # ignore if activity cannot be scheduled
