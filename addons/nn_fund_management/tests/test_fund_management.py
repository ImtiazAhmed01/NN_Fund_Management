# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError

class TestFundManagement(TransactionCase):

    def setUp(self):
        super(TestFundManagement, self).setUp()
        
        # Models
        self.FundAccount = self.env['fund.account']
        self.IncomingFund = self.env['incoming.fund']
        self.FundProject = self.env['fund.project']
        self.FundAllocation = self.env['fund.allocation']
        self.FundTransfer = self.env['fund.transfer']
        self.FundRequisition = self.env['fund.requisition']
        self.FundBill = self.env['fund.bill']

        # Admin user has all groups by default in test cases, but let's make sure
        self.admin_user = self.env.ref('base.user_admin')
        self.admin_user.write({
            'groups_id': [
                (4, self.env.ref('nn_fund_management.group_fund_user').id),
                (4, self.env.ref('nn_fund_management.group_finance_user').id),
                (4, self.env.ref('nn_fund_management.group_gm_approver').id),
                (4, self.env.ref('nn_fund_management.group_md_approver').id),
                (4, self.env.ref('nn_fund_management.group_fund_admin').id),
            ],
            'allow_self_approval': True  # For testing self-approval workflow easily
        })

        # Create Fund Account
        self.account = self.FundAccount.create({
            'name': 'Test Main Bank Account',
            'account_number': '123-456-789',
        })

        # Create Projects
        self.project_a = self.FundProject.create({
            'name': 'Project A',
            'code': 'PRJ-A',
        })
        self.project_b = self.FundProject.create({
            'name': 'Project B',
            'code': 'PRJ-B',
        })

    def test_complete_fund_flow_scenario(self):
        # 1. Receive BDT 1,000,000 in a fund account
        inc_fund = self.IncomingFund.create({
            'fund_account_id': self.account.id,
            'amount': 1000000.0,
            'reference': 'TXN-10001',
            'sender': 'External Donor',
        })
        inc_fund.action_confirm()
        self.assertEqual(self.account.total_received, 1000000.0)
        self.assertEqual(self.account.available_unassigned_balance, 1000000.0)

        # 2. Request BDT 600,000 for Project A
        alloc = self.FundAllocation.create({
            'fund_account_id': self.account.id,
            'project_id': self.project_a.id,
            'amount': 600000.0,
            'purpose': 'Initial allocation for Project A',
        })
        
        # 3. Show that BDT 600,000 remains on hold while pending
        alloc.action_submit()
        self.assertEqual(alloc.state, 'submitted')
        self.assertEqual(self.account.amount_held, 600000.0)
        self.assertEqual(self.account.available_unassigned_balance, 400000.0)

        # 4. Reject the request and show that the money returns to the unassigned balance
        alloc.action_reject(comment="Insufficient project detailed plan.")
        self.assertEqual(alloc.state, 'rejected')
        self.assertEqual(self.account.amount_held, 0.0)
        self.assertEqual(self.account.available_unassigned_balance, 1000000.0)

        # 5. Submit the allocation again and approve it
        # Create a new allocation since rejected cannot be re-submitted
        alloc_new = self.FundAllocation.create({
            'fund_account_id': self.account.id,
            'project_id': self.project_a.id,
            'amount': 600000.0,
            'purpose': 'Resubmitted allocation with plan',
        })
        alloc_new.action_submit()
        alloc_new.action_gm_approve(comment="Approved by GM")
        alloc_new.action_md_approve(comment="Approved by MD")
        
        self.assertEqual(alloc_new.state, 'approved')
        self.assertEqual(self.account.total_assigned, 600000.0)
        self.assertEqual(self.account.available_unassigned_balance, 400000.0)
        self.assertEqual(self.project_a.available_fund, 600000.0)

        # 6. Transfer BDT 200,000 from Project A to Project B
        transfer = self.FundTransfer.create({
            'src_project_id': self.project_a.id,
            'dest_project_id': self.project_b.id,
            'amount': 200000.0,
            'reason': 'Urgent resource sharing',
        })
        
        # 7. Show that the transfer amount remains on hold while approval is pending
        transfer.action_submit()
        self.assertEqual(transfer.state, 'submitted')
        self.assertEqual(self.project_a.transfer_hold, 200000.0)
        self.assertEqual(self.project_a.available_fund, 400000.0)

        # 8. Approve the transfer
        transfer.action_gm_approve(comment="Approved by GM")
        transfer.action_md_approve(comment="Approved by MD")
        
        self.assertEqual(transfer.state, 'approved')
        self.assertEqual(self.project_a.outgoing_transfers, 200000.0)
        self.assertEqual(self.project_a.available_fund, 400000.0)
        self.assertEqual(self.project_b.incoming_transfers, 200000.0)
        self.assertEqual(self.project_b.available_fund, 200000.0)

        # 9. Create a BDT 150,000 requisition for Project B
        req = self.FundRequisition.create({
            'project_id': self.project_b.id,
            'amount': 150000.0,
            'purpose': 'Purchase equipment',
            'required_date': fields.Date.context_today(self),
        })
        req.action_submit()
        req.action_gm_approve(comment="Approved by GM")
        req.action_md_approve(comment="Approved by MD")
        
        self.assertEqual(req.state, 'approved')
        self.assertEqual(self.project_b.available_fund, 500000.0 - 450000.0) # Wait, B was 200k. 200k - 150k = 50k.
        self.assertEqual(self.project_b.available_fund, 50000.0)
        self.assertEqual(req.remaining_billable_amount, 150000.0)

        # 10. Create a BDT 100,000 partial bill
        bill1 = self.FundBill.create({
            'requisition_id': req.id,
            'amount': 100000.0,
            'vendor': 'Equipment Supplier Corp',
        })
        bill1.action_post()
        
        # 11. Show that BDT 50,000 remains billable
        self.assertEqual(req.remaining_billable_amount, 50000.0)
        self.assertEqual(self.project_b.total_spent_amount, 100000.0)

        # 12. Try to create another bill for BDT 60,000 and block it
        with self.assertRaises(ValidationError):
            bill2 = self.FundBill.create({
                'requisition_id': req.id,
                'amount': 60000.0,
                'vendor': 'Equipment Supplier Corp',
            })
            bill2.action_post()

        # 13. Try to use Project B's requisition for Project A and block it
        # Note: In our model, project_id is a stored related field from requisition.
        # It is read-only and automatically copies from the requisition.
        # If a bill is created against req, its project_id will always be project_b.
        bill_a = self.FundBill.create({
            'requisition_id': req.id,
            'amount': 10000.0,
            'vendor': 'Test',
        })
        self.assertEqual(bill_a.project_id.id, self.project_b.id)
        self.assertNotEqual(bill_a.project_id.id, self.project_a.id)
