# NN Fund Management Module

A custom Odoo module designed for comprehensive management of incoming funds, project/expense head allocations, requisitions, vendor billing controls, and fund transfers. The module features a configurable multi-level approval workflow with General Manager (GM) and Managing Director (MD) stages, automatic balance calculations, server-side validation rules, and detailed audit history tracking.

---

## 1. Module Specifications
* **Odoo Version**: `17.0` (Community & Enterprise compatible)
* **Required Dependencies**: `base`, `mail` (No heavy external accounting dependencies)
* **Docker Support**: Built-in containerized architecture using Docker Compose

---

## 2. Architecture & Design Decisions

### Model Structure
* **Fund Account (`fund.account`)**: Configurable bank/cash accounts that track received funds, assigned funds, held funds, and available unassigned balances.
* **Incoming Fund (`incoming.fund`)**: Records source transactions, requiring unique references per account and confirmation by Finance Users.
* **Fund Project (`fund.project`) & Expense Head (`fund.expense.head`)**: Destinations for allocated funds. They track allocations, transfers, requisitions, and expenditures dynamically with real-time balance calculations.
* **Fund Allocation (`fund.allocation`)**: Request to move money from a Fund Account to a Project or Expense Head.
* **Fund Requisition (`fund.requisition`)**: Request to reserve/withdraw money from a Project/Expense Head.
* **Fund Transfer (`fund.transfer`)**: Enables transfers between Projects and Expense Heads (e.g. Project-to-Project, Project-to-Expense Head, etc.).
* **Fund Bill (`fund.bill`)**: Requisition-linked vendor billing control. Ensures total billing doesn't exceed approved requisitions.
* **Approval History (`fund.approval.history`)**: Centralized log model tracking actions, actors, states, dates, and comments.

### Key Logic
* **Approval Workflow Mixin (`fund.approval.mixin`)**: A reusable abstract mixin that implements the state machine, security checks, and audit logging for allocations, requisitions, and transfers.
* **No Double Spending**: Implemented via state-based field recalculations and strict server-side submission/approval constraints that block requests if the source balance is insufficient.

---

## 3. Installation Instructions

### Option A: Running with Docker (Recommended)
1. Ensure you have Docker and Docker Compose installed.
2. In the root directory of the project, run:
   ```bash
   docker-compose up -d
   ```
3. Odoo will start and automatically initialize a database named `odoo_db` and install the `nn_fund_management` module.
4. Access Odoo at `http://localhost:8069` using credentials:
   * **Database**: `odoo_db`
   * **Username**: `admin`
   * **Password**: `admin`

### Option B: Manual Installation
1. Copy the `addons/nn_fund_management` folder to your Odoo `custom_addons` directory.
2. Ensure the Odoo service is configured to look in that directory.
3. Restart Odoo.
4. Activate Developer Mode, go to **Apps** -> **Update Apps List**, search for `NN Fund Management`, and click **Install**.

---

## 4. Configuration Steps

### 1. User Security Setup
Assign users to the corresponding groups in **Settings** -> **Users & Companies** -> **Users**:
* **Fund User**: Can create, view, and submit requests (Allocations, Requisitions, Transfers).
* **Finance User**: Can confirm incoming funds, post/cancel bills, and edit master accounts/projects.
* **GM Approver**: Can approve requests at the GM Level.
* **MD Approver**: Can approve requests at the MD Level.
* **Fund Administrator**: Full access over configuration and overrides.

### 2. Specially Authorized Self-Approval
If a user should be allowed to approve their own requests (e.g. CEO or Owner), open their user card and check the **Allow Self Approval** box.

---

## 5. Testing Instructions

To run the automated test suite verifying the whole workflow:
```bash
docker-compose exec web odoo --test-enable --stop-after-init -d odoo_db -i nn_fund_management
```
The test suite executes the exact 13-step demonstration scenario described in the technical assessment.

---

## 6. Assumptions and Known Limitations

### Assumptions
* A project and an expense head represent separate allocation contexts; a single allocation, requisition, or transfer belongs to either a Project or an Expense Head, but never both.
* The system is multi-company enabled; each record is scoped to its company, and users cannot access records belonging to unauthorized companies.

### Known Limitations
* **Custom Bill Model**: A self-contained custom bill model is implemented to run without dependencies on standard Odoo accounting (`account`). If required, this can be integrated directly with standard Odoo Vendor Bills (`account.move`).
* **Email Integration**: The bank email parsing integration (bonus feature) is not included in the main source package to ensure clean sandbox execution without needing email server configurations.
