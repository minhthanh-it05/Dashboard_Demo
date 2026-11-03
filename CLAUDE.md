# CLAUDE.md — Project Context & Development Instructions

> **Project:** Internal Project Management & Cross-Department Information System  
> **Status:** Proposed architecture / Demo preparation  
> **Primary users:** Project Department Manager and Project Department members  
> **Technology direction:** Python, Django, PostgreSQL  
> **Important:** This document describes the team's current proposal and research notes. It is **not** an approved company architecture or a confirmed statement of every business process/API capability.

---

## 1. Instructions for Claude Code

You are assisting a five-person development team to design and build a demo for an internal business system. Treat this document as the initial project brief, not as permission to implement every feature immediately.

### 1.1 How to work

1. **Inspect the existing repository before changing anything.** Identify existing code, framework, dependencies, database setup, conventions, and unfinished work. Do not overwrite or replace existing work without explaining why.
2. **Work incrementally.** The first target is a working Project Management MVP using demo data. Integrations with OplaCRM and MISA should be added in separate steps after the core workflow works.
3. **Do not invent external API behavior.** Use only confirmed documentation/configuration. If an endpoint, field, authentication flow, webhook event, or permission is not confirmed, isolate it behind an adapter/interface and mark it TODO. Do not fabricate a live integration.
4. **Do not connect to production systems without explicit authorization.** Use mock data, fixtures, or an approved sandbox until the company and vendors authorize access.
5. **Do not hard-code secrets.** Use environment variables and `.env.example`. Never commit API keys, access codes, tokens, passwords, customer data, financial data, or private files.
6. **Prefer read-only integration initially.** Do not call MISA write endpoints or create/update records in OplaCRM/MISA unless a later requirement explicitly authorizes it.
7. **Preserve source-of-truth boundaries.** OplaCRM remains the Sales source; MISA remains the official accounting/approval source; the new application manages Project operational data. Do not silently overwrite data owned by another source.
8. **Keep financial information protected.** Enforce authorization in backend views/services/querysets, not only by hiding UI elements. Apply least privilege.
9. **Use clear migrations, validation, error handling, logs, tests, and documentation.** Sync jobs must be idempotent and safe to retry.
10. **Explain assumptions.** When requirements are unclear, state the assumption in code comments or documentation and record it in `docs/OPEN_QUESTIONS.md`. Do not present an assumption as a confirmed company rule.

### 1.2 Before implementing a task

- Summarize the relevant current structure and the intended change.
- Identify any assumptions and dependencies.
- Implement only the requested scope.
- Run relevant tests/checks and report their results honestly.
- Update documentation where behavior, schema, setup, or assumptions change.

### 1.3 Preferred language and style

- Discuss requirements with the team in Vietnamese unless asked otherwise.
- Use English for class names, function names, database fields, API identifiers, and technical module names.
- Prefer readable, maintainable code over clever abstractions.
- Avoid premature microservices, Kafka, Kubernetes, or complex distributed infrastructure for the demo.

---

## 2. Business Goal

Build an internal web application that consolidates selected information from three business domains:

1. **Sales** — data originates from OplaCRM.
2. **Finance/Accounting** — data originates from MISA AMIS, subject to the actual API permissions and available endpoints.
3. **Project** — currently tracked mainly through individual Excel/Word files; the proposed application will provide the central Project Management module.

The main users of the resulting dashboard/application are:

- Project Department Manager / Project Director (exact role names and responsibilities to be confirmed).
- Project Department members.

The system is more than a read-only dashboard. It is expected to let Project users manage project records, timelines, tasks, progress, issues, documents, and selected purchase/payment tracking information. The dashboard is a presentation layer over this operational system.

### 2.1 Business outcomes sought

- Give Project users one consistent place to view project information.
- Receive relevant Sales information when an Opportunity is won and handed over.
- Let Project Managers plan timelines, milestones, and tasks.
- Let Project members update task progress and issues.
- Track purchase requests and payment-request status without replacing MISA's official approval process.
- Display selected Finance information only where the source and project association are reliable.
- Give the Project Manager an overview of current projects, risks, overdue tasks, upcoming milestones, and permitted financial summaries.

---

## 3. Proposed Architecture

### 3.1 Architectural style

Use a **Modular Monolithic Django application** backed by PostgreSQL.

A single deployable application is preferred for the demo. Organize code by business module and isolate external integrations behind adapters. Do not begin with microservices.

### 3.2 Proposed technology stack

| Layer | Proposed technology | Notes |
|---|---|---|
| Language | Python | Main development language |
| Web/backend | Django | Authentication, ORM, forms, permissions, admin, server-rendered views |
| Frontend | Django Templates + Bootstrap + HTMX | Sufficient for initial tables, forms, filters, and dashboard interactions |
| Database | PostgreSQL | Central operational database |
| ORM/migrations | Django ORM / Django Migrations | Schema and migration management |
| Charts | Chart.js | Initial dashboard visualizations |
| External HTTP | Python HTTP client (e.g. `requests` or `httpx`) | Wrap calls inside provider adapters |
| Scheduled sync | Django management commands + scheduler | Start simple; document the scheduler used |
| Async jobs (later) | Celery + Redis | Add only when job volume/retry needs justify it |
| Local environment | Docker Compose | App + PostgreSQL for repeatable development |
| Version control | Git | GitHub may host the repository |

These are proposed choices. If the repository already has a reasonable stack, inspect it and explain any proposed changes before replacing it.

### 3.3 Logical architecture

```text
OplaCRM                         MISA AMIS                         Project users/files
(Sales source)                  (Finance source)                  (Excel / Word today)
    |                                |                                    |
    | REST API                       | ACT Open API / possible            | CSV/XLSX import
    | Webhook (if confirmed)         | other MISA API / CSV               | Django forms
    +----------------+---------------+------------------------------------+
                     |
              Python Integration Layer
       +-------------+---------------+----------------+
       | OplaCRM adapter              | MISA adapter   | File import
       | Auth / pagination / mapping  | Auth / mapping | Validation
       +-------------+---------------+----------------+
                     |
              PostgreSQL Central DB
       +-------------+---------------+----------------+
       | Sales mirror                 | Finance data   | Project records
       | External IDs                 | Source/time    | Tasks/progress
       +-------------+---------------+----------------+
                     |
              Django Web Application
       +-------------+---------------+----------------+
       | Project Management           | Dashboard      |
       | Handover / Documents         | RBAC / Audit   |
       | Purchase / Payment tracking  | Sync status    |
       +-----------------------------+
                     |
           Project Manager / Project Members
```

### 3.4 Source-of-truth boundaries

- **OplaCRM:** authoritative source for Sales-owned data such as Leads, Accounts, Contacts, Opportunities, Sales stages, Sales owner, and product records where available.
- **MISA AMIS:** authoritative source for accounting records and official purchase/payment approvals. The system may only store/read the subset allowed by API/export and company permissions.
- **Python application:** proposed source of truth for new Project operational data such as project timeline, milestones, tasks, progress updates, issues, project membership, and internal handover acceptance.
- **PostgreSQL:** central application database and synchronized read model. It does not replace OplaCRM or MISA as their respective official systems.

Do not allow a sync from OplaCRM or MISA to overwrite Project-owned fields such as execution progress, task status, or PM assignments unless an explicit mapping/ownership rule says so.

---

## 4. Business Process Notes (Current Understanding)

The following process is reconstructed from interviews/notes and must be treated as **tentative** until confirmed by department heads.

### 4.1 Sales to Project handover

1. Sales pursues a bid/opportunity and records information in OplaCRM.
2. When the opportunity is won and the project is ready to be handed over, Sales transfers information to Project.
3. Candidate handover information includes project/customer scope, scale, promised timeline, BOQ/work quantity, selling price, goods/products, and other commercial details.
4. Project checks the handover information and may request missing information.
5. Project organizes a kickoff with relevant departments to communicate and align on the project.
6. Project prepares the customer contract based on information handed over from Sales. Exact contract review/signature responsibility is not confirmed.

Important data ownership distinction:

- Sales should provide the **commercially agreed scope and commitments** (what was sold/promised, approved BOQ/quotation, selling price, customer, promised dates).
- Project should validate/accept the handover and create the **execution plan** (detailed timeline, milestones, tasks, staff assignment, delivery/acceptance plan).
- Scale, schedule, and work quantity may appear in both domains, but their meaning differs: Sales provides contractual/quoted commitments; Project creates the detailed execution breakdown. Keep separate fields where needed rather than treating them as a single value.

### 4.2 Project planning and tracking

- The Project Manager/Head creates a project timeline.
- Project members currently maintain separate progress files, generally using Excel/Word.
- There is no confirmed centralized Project application currently in use.
- The proposed application should centralize project, timeline, milestone, task, progress update, issue, and document information.
- The actual progress calculation method (manual percentage, milestone weighted percentage, task completion ratio, or another method) is not confirmed. Do not assume a formula is approved.

### 4.3 Purchase process (tentative)

Current interview notes indicate:

- Project searches for suppliers and coordinates purchasing.
- The purchase process reportedly does not require a separate Accounting confirmation step before management approval.
- The approval chain was recorded as: Sales → Sales Manager → Project Manager → Project Director → MISA.

This sequence and the meaning of the roles/steps need confirmation. Do not implement an approval engine that treats this as final policy.

### 4.4 Payment process (tentative)

Current interview notes indicate the payment process includes:

Project Director → Accounting → Directors → MISA.

The exact director roles, order, approval rules, thresholds, rejection/revision paths, and final status source must be confirmed.

**Design principle:** MISA remains the official approval/accounting system. The Python application should initially track purchase/payment request metadata and status only. Do not recreate or bypass official approval in Python. Do not claim a request is approved/paid unless that status is confirmed by an authorized source or user update with clear provenance.

### 4.5 Completion, delivery, acceptance

Project appears to manage goods, delivery, and acceptance documents. The exact end-to-end closeout process, acceptance conditions, and project completion authority are not yet confirmed. Model these flexibly and record them as open questions.

---

## 5. External Systems and API Research Notes

All items in this section are based on the team's current research notes. Verify against current vendor documentation and the company's actual tenant/contract before enabling production integration.

### 5.1 OplaCRM

Official documentation identified by the team:

- API documentation: <https://doc-api.oplacrm.com/>
- Pricing: <https://oplacrm.com/opla-pricing/>
- Integration overview: <https://oplacrm.com/integration/>

#### API areas identified

The public API documentation includes or appears to include resources for:

- Accounts
- Contacts
- Leads
- Opportunities
- Sales Process / stages
- Employee
- Products
- Other catalog resources (for example suppliers/sites/unit of measure), subject to endpoint details and access

Opportunity data of interest may include: opportunity ID/name, amount, open date, expected/actual close date, stage, owner, and stage history/logs. Verify exact field names and response schema in the current API docs.

The team has identified Scale and Enterprise as the plans that include API access in public plan information. However, the following are **not confirmed**:

- Whether the company's tenant has API enabled.
- Whether the displayed Scale price is per seat or per organization in the applicable quote.
- Number of included users/seats and maximum seats.
- Additional seat pricing and minimum seat count.
- API rate limits, access scopes, pagination limits for every endpoint.
- Availability of quotation, BOQ, contract, activity, and file attachment endpoints.
- Exact Webhook events, retry policy, signature/security mechanism, and availability on Scale.

Do not assume that every resource shown in public docs is enabled for the company's subscription.

#### Proposed integration

- Start read-only.
- Build an `OplaCRMClient` and `OplaCRMAdapter` isolated from Django views/models.
- Implement pagination, timeout, retry with backoff for transient errors, rate-limit handling, structured error logging, and idempotent upsert.
- Initially use a scheduled polling command. Add Webhook only after vendor confirms exact event behavior and account access.
- If Webhook is implemented, treat it as an event notification; fetch/verify the current record through the API where possible. Keep periodic reconciliation to recover missed events.
- Store external IDs and sync timestamps.

Potential internal commands (names are illustrative):

```bash
python manage.py sync_oplacrm_accounts
python manage.py sync_oplacrm_opportunities
```

### 5.2 MISA AMIS Accounting — ACT Open API notes

The team found the MISA Developer Portal product page:

- <https://developer.misa.vn/products-openapi/AMISKT>

The user also supplied a detailed endpoint summary for the ACT Open API with production base URL:

- `https://actapp.misa.vn`

**Important distinction:** Do not assume the Developer Portal AMISKT API and the ACT Open API described below are the same API generation, same authentication mechanism, same endpoint set, or same permission model. Compare the detailed AMISKT documentation with ACT Open API documentation and ask MISA to confirm which API applies to the company's subscription. Keep their clients/authentication separate if needed.

#### ACT Open API endpoint notes supplied by the team

| Function | Method | Path / endpoint note | Direction |
|---|---|---|---|
| Connect / obtain token | POST | `/api/oauth/actopen/connect` | Authentication |
| Save proposed voucher/dictionary | POST | `/apir/sync/actopen/save` (third-party notes also mention `save_dictionary`) | Write |
| Delete proposed voucher | DELETE | `/apir/sync/actopen/delete` | Write |
| Set connection options | POST | `/apir/sync/actopen/set_option` | Write/configuration |
| Read dictionaries | POST | `/apir/sync/actopen/get_dictionary` | Read |
| Read deleted dictionaries | POST | `.../get_dictionary_delete` | Read |
| Read receivable/payable balances | POST | `.../get_list_acc_obj_debt` | Read |
| Read deleted debt rows | POST | `.../get_list_acc_obj_debt_delete` | Read |
| Read inventory balance by warehouse | POST | `.../get_list_inventory_balance` | Read |
| Read deleted inventory rows | POST | `.../get_list_inventory_balance_delete` | Read |
| Read company information | POST | `.../get_company_info` | Read |
| Read system options | POST | `.../get_option` | Read |
| Asynchronous callback | POST | Callback URL hosted by partner | Callback |

For `get_dictionary`, the team's notes state: `data_type = 1` customers, `2` goods/materials, `3` warehouses. Confirm exact schemas and all supported values against the full vendor documentation before coding.

#### ACT API limitations identified by the team

The current ACT API summary does **not** identify read endpoints for:

- Full list of accounting vouchers/documents.
- Detailed sales invoices.
- Cash receipt/payment vouchers.
- Detailed transaction ledger/book entries.
- Lookup by business document code.
- Updating an existing customer or product record through the read API.

The read capabilities identified are dictionaries, receivable/payable balances, inventory balance, company info, and system options.

Do not build the Finance dashboard assuming that invoice-level, payment-level, or voucher-level data is available from these ACT endpoints.

#### ACT API request/response/auth notes supplied by the team

- Reads use POST with JSON body; there are no GET methods in the endpoint list supplied.
- Delete is DELETE; documentation examples reportedly include a request body. Verify client/library behavior and the vendor's exact requirement before production.
- Common response: `Success`, `ErrorCode`, `ErrorMessage`, `Data`, `CustomData`.
- `Data` may be a JSON-encoded string requiring a second parse. Implement defensive parsing and schema validation.
- `CustomData` may contain values such as `LastSyncTime` for incremental synchronization.
- Connect response may include `access_token`, `tenant_code`, `app_name`, `expired_time`, `expired_time_ticks`.
- Callback may include `success`, `error_code`, `error_message`, `signature`, `app_id`, `org_company_code`, `data_type`, `data`.
- Team notes state callback signature is HMAC-SHA256 using `app_id` as key. Verify the precise signing/canonicalization scheme with MISA before accepting callbacks in production.
- Authentication notes: obtain `app_id` from MISA; the company's AMIS administrator obtains/configures `access_code` in the product's API connection settings; connect using `app_id`, `access_code`, and `org_company_code`; subsequent requests send token in `X-MISA-AccessToken` header.
- Token lifetime is stated as 12 hours; use returned expiry fields and refresh before expiry. Handle authentication failures safely.
- Pagination uses `skip`/`take`, with `take` maximum 100 according to the team's notes.
- Incremental sync uses `last_sync_time` where supported.
- No official rate limit was found in the team's research. Do not invent one; ask MISA and implement conservative configurable throttling.
- Team notes indicate save limits of 100 vouchers or 200 dictionaries per request. These write endpoints are out of initial scope.
- A third-party observation reportedly found requests of around 5,000 rows may time out; treat this as an unverified observation, not an official vendor limit.

#### MISA integration policy for initial demo

- Prefer **read-only** integration.
- Initially implement only the read endpoints that are confirmed and authorized.
- Do not use `/save`, `/delete`, or `/set_option` in the demo unless there is explicit written approval and a separate requirement.
- Build an import mechanism for approved Finance Excel/CSV reports as a fallback for information missing from ACT API.
- Mark source/provenance on every Finance record: API, imported file, or manual user entry.
- Store import batch ID, source filename, imported by, import time, data period, and validation result.
- Do not infer that customer-level debt belongs to an individual project. Only associate it with a project when a reliable project/document mapping exists.

#### Questions to resolve with MISA

1. Does the company's specific AMIS Accounting subscription permit ACT Open API access?
2. Does using the Developer Portal AMISKT Open API require separate registration, activation, or a paid add-on?
3. Are there API endpoints for invoice list/detail, payment status, cash receipts/payments, and vouchers that are not included in the ACT endpoint list?
4. Is MISA meInvoice a separate API/source for official invoice data?
5. What are official rate limits, data limits, and callback guarantees?
6. Is there a sandbox/test tenant and a read-only permission model?

### 5.3 Project current data source

- No centralized Project Management application has been confirmed.
- Project members currently use separate Excel/Word files to track progress.
- The proposed Django application should become the centralized operational tool for new Project records.
- Import old files only after inspecting their structure and agreeing a standard template. Do not make assumptions about spreadsheet columns.
- Do not treat Word/Excel files as automatically authoritative unless Project leadership confirms that.

---

## 6. Proposed Functional Modules

The first demo should focus on the Project workflow. Modules below are a target design; implement only as requested and validate each with demo data.

### 6.1 User and access management

Suggested roles:

- `PROJECT_MANAGER` / `PROJECT_HEAD`: see all projects; manage project plan, assignment, and dashboard.
- `PROJECT_MEMBER`: see projects assigned to them; update assigned tasks, progress, and issues.
- `SALES_VIEWER`: view approved Sales handover fields related to projects.
- `FINANCE_VIEWER`: view Finance fields specifically authorized for them.
- `SYSTEM_ADMIN`: manage users, configuration, integrations, and logs.

Role names and access policy require company confirmation. Apply object-level/project-level authorization in backend code. Apply field-level restrictions to financial values where required.

### 6.2 Sales handover

- Store imported/source Opportunity ID and Account ID.
- Show Sales-provided customer, deal, selling value, promised period, product/scope, and available quotation/BOQ data.
- Allow Project to mark handover as pending, needs information, accepted, or rejected (labels are proposed; confirm later).
- Keep Sales-originated fields distinct from Project execution fields.
- Prevent duplicate Project creation for the same external Opportunity unless explicitly allowed.

### 6.3 Project management

Potential core entities:

- Project
- Project member
- Kickoff record/minutes
- Contract metadata and documents
- Timeline
- Milestone
- Task
- Progress update history
- Issue/risk
- Project document

Suggested project status values for the demo only:

`PENDING_HANDOVER`, `READY`, `IN_PROGRESS`, `ON_HOLD`, `COMPLETED`, `CANCELLED`.

Do not enforce these as final company statuses before confirmation.

Progress calculation is **not yet defined**. Do not hard-code that project progress equals the simple percentage of completed tasks. Support storing progress updates and leave formula configurable or explicitly labeled as demo logic.

### 6.4 Purchase tracking

Initial purpose: record and display the purchase process associated with a Project, not to replace MISA approvals.

Potential data:

- Purchase request number and Project ID.
- Requester and request date.
- Supplier.
- Items, quantities, unit costs, estimated total.
- Supporting quotations/documents.
- Approval stage/status and source of status.
- Order/delivery status if Project confirms need.

The actual approval chain is tentative. Keep workflow configuration flexible; do not hard-code an unconfirmed chain into application logic.

### 6.5 Payment tracking

Initial purpose: track a payment request and its progress, not perform accounting or payment execution.

Potential data:

- Payment request number and Project ID.
- Supplier/payee.
- Amount and currency.
- Reason/payment milestone.
- Supporting documents.
- Project Director confirmation, Accounting review, director approval stages (tentative).
- Final payment status and evidence/source.

The actual approval process and ability to sync statuses from MISA are not confirmed. Use demo/manual status only when clearly identified as such. Do not claim it is the official MISA status.

### 6.6 Finance display

- Display only finance fields that the company authorizes.
- Distinguish customer-level balances from project-level financials.
- Display source and last-sync/import time.
- If invoice data is imported from CSV, retain import provenance and validation status.
- Never fabricate invoice/document data from debt balances.

### 6.7 Dashboard

Potential Project Manager dashboard:

- Total projects by status.
- Projects in progress/on hold/completed.
- Projects at risk or overdue.
- Upcoming milestones.
- Overdue/open tasks.
- Recent progress updates and issues.
- Pending handovers.
- Purchase requests waiting for a status update.
- Payment requests waiting for a status update.
- Permitted financial summary where the source is reliable.

Potential Project Member view:

- My assigned projects.
- My open/overdue tasks.
- Upcoming deadlines.
- Tasks needing progress updates.
- Issues assigned to me.

All demo metrics must use clearly labeled sample data until real integrations are authorized.

---

## 7. Proposed Data Modeling Principles

Do not create one huge `projects` table containing every field. Separate entities and define ownership clearly.

Potential Django apps:

```text
apps/
  accounts/       # users, roles, profile, authorization
  sales/          # read models synchronized from OplaCRM
  finance/        # MISA snapshots and finance imports
  projects/       # projects, handovers, timelines, tasks, progress, issues
  procurement/    # purchase request tracking
  payments/       # payment request tracking
  documents/      # document metadata and controlled file storage
  dashboard/      # dashboard views and aggregations
  integrations/   # OplaCRM/MISA clients, adapters, sync states, logs
```

Potential core entities/tables (adapt to actual requirements after inspection):

- `Project`
- `SalesHandover`
- `ExternalIDMapping`
- `ProjectMember`
- `KickoffRecord`
- `ProjectContract`
- `ProjectTimeline`
- `ProjectMilestone`
- `ProjectTask`
- `ProgressUpdate`
- `ProjectIssue`
- `ProjectDocument`
- `PurchaseRequest`
- `PurchaseItem`
- `PurchaseApprovalStatus`
- `PaymentRequest`
- `PaymentApprovalStatus`
- `FinanceDebtSnapshot`
- `FinanceInventorySnapshot`
- `FinanceImportBatch`
- `SyncState`
- `SyncLog`
- `AuditLog`

### 7.1 IDs and mapping

- Generate an internal `project_id` (UUID or a controlled human-readable project code; decide and document one approach).
- Store external IDs from OplaCRM and MISA separately.
- A Project may be linked to one or more external Sales records only if business rules permit; confirm cardinality.
- A customer may have multiple projects. Never join only by customer name.
- Do not associate customer-level MISA debt with a particular Project without a reliable mapping.

### 7.2 Data provenance

For imported/synchronized information, track at least:

- `source_system` (e.g. `OPLACRM`, `MISA_ACT_API`, `FINANCE_CSV`, `MANUAL`).
- `external_id` where applicable.
- `last_synced_at` or `imported_at`.
- `source_updated_at` if supplied by source.
- `import_batch_id` for files.
- `created_by` / `updated_by` for internal updates.

### 7.3 Audit and history

- Keep progress updates as history records; do not only overwrite one percentage field.
- Record who changed important project/task/approval-tracking fields and when.
- Store previous/new status where appropriate.
- Do not store sensitive credentials or unnecessary financial payloads in logs.

---

## 8. Security, Privacy, and Reliability Requirements

1. Use `.env` for local secrets and provide `.env.example` with placeholder variable names only.
2. Do not commit `.env`, uploaded business files, credentials, API responses containing personal/financial data, or production datasets.
3. Use separate integration credentials where available; request least-privilege/read-only scopes.
4. Validate webhook signatures before processing. Do not accept callback payloads solely because they reach the endpoint.
5. For webhooks, implement idempotency/deduplication and a recovery/reconciliation sync.
6. For API sync jobs, add timeouts, controlled retries, pagination, rate-limit handling, and visible sync status.
7. Never log access tokens, access codes, client secrets, full bank details, or unnecessary personal data.
8. Use HTTPS in deployed environments. Restrict upload types and sizes; scan/validate files as appropriate.
9. Enforce authorization at backend level for projects and finance fields.
10. Maintain audit logs for important internal changes.
11. Use sample/anonymous data for demos. Production data requires explicit approval.
12. Keep MISA as the official approval/accounting system; the proposed app does not execute payments or replace accounting approval.

---

## 9. Suggested Demo Roadmap

### Phase 1 — Core Project System (first priority)

Build a complete, usable vertical slice with sample data:

1. Django project, PostgreSQL, local Docker Compose setup.
2. Login and basic role-based access.
3. Project list, project details, create/edit project.
4. Sales handover form using sample/manual data.
5. Kickoff record and contract metadata/document reference.
6. Timeline and milestone management.
7. Task assignment and task status.
8. Progress update history and issues.
9. Basic purchase/payment tracking records (no real MISA approval integration).
10. Project Manager dashboard and Project Member view.
11. Tests, sample fixtures, README setup instructions.

### Phase 2 — OplaCRM integration

Only after credentials/sandbox and API scope are authorized:

1. Build isolated client and adapter.
2. Implement read-only Accounts/Contacts/Leads/Opportunities/Employees/Products that are needed.
3. Implement pagination and incremental sync only where supported/documented.
4. Map Opportunity Won to a pending handover; do not auto-create a final Project without Project acceptance.
5. Add sync logs and reconciliation.
6. Assess Webhook after vendor confirms supported events and signature/retry behavior.

### Phase 3 — MISA Finance integration

Only after MISA confirms the applicable API, subscription permissions, and sandbox/authorized tenant:

1. Confirm whether AMISKT Developer Open API and ACT Open API are distinct and which applies.
2. Implement a separate adapter/authentication flow for the approved API.
3. Read only confirmed dictionaries/debt/inventory/company data.
4. Implement validated CSV/XLSX import for approved reports not available through API.
5. Add data provenance, duplicate checks, reconciliation, and import history.
6. Do not implement write endpoints unless a separately approved requirement exists.

### Phase 4 — Hardening and deployment

- Permission review with department heads.
- Data quality and duplicate handling.
- Security review.
- Backup and restore test.
- Error monitoring and sync failure alerts.
- Deployment environment, HTTPS, secret management, scheduled jobs.
- User acceptance testing with Project team.

---

## 10. Open Questions — Must Not Be Assumed

Maintain/update `docs/OPEN_QUESTIONS.md` as these items are resolved.

### Sales / OplaCRM

- Which OplaCRM plan and seats does the company currently have?
- Is API access enabled on the actual tenant?
- What is the included seat count, maximum seat count, and additional-seat pricing?
- Are quotation, BOQ, contract, activity, and file endpoints available?
- What are API rate limits and supported incremental-sync fields?
- Which Webhook events are supported on the company's plan? What signature/retry guarantees exist?

### Finance / MISA

- Which exact AMIS product/module and subscription is used?
- Does the subscription allow the ACT Open API?
- Is the Developer Portal AMISKT API separate from ACT Open API? Which API should be used?
- Are invoice, voucher, receipt/payment, and payment-status read endpoints available through another MISA product/API?
- Is meInvoice used, and can its official API provide invoice details?
- What are the official API rate limits and data permissions?
- Can MISA provide a sandbox/test tenant and read-only application access?
- What Finance reports can Accounting export to CSV/XLSX, and who owns the export/import process?

### Project business process

- What exact fields are mandatory in Sales handover?
- Who validates/accepts handover?
- What are official project statuses and completion criteria?
- Who owns the timeline and how is it approved?
- How are task progress and overall project progress calculated?
- What are the exact procurement approval steps, thresholds, and rejection paths?
- What are the exact payment approval steps and director roles?
- Who prepares/reviews/signs the customer contract?
- How are delivery, acceptance, and project closeout handled?
- What file templates are currently used and can they be standardized?
- Is there a common Project ID across OplaCRM, MISA, contracts, purchases, and acceptance records?

### Access and operations

- Which users need access and which fields are sensitive?
- Should Project Members see all projects or only assigned projects?
- Which finance fields can Project Manager and Project Members see?
- What freshness is required: event-driven, every few minutes, hourly, or daily?
- Where will the app be hosted and who approves the hosting/security model?

---

## 11. First Actions for Claude Code When the Repository Is Opened

Do not immediately generate the entire application. Start with repository discovery and a small, reviewable plan.

1. Inspect the repository and report what already exists.
2. Check whether a `README.md`, `pyproject.toml`, `requirements.txt`, Docker files, Django project, or database schema already exists.
3. Identify missing setup and documentation.
4. Propose a short implementation plan for **Phase 1 only**.
5. If the repository is empty and the team asks to start, scaffold Django + PostgreSQL + Docker Compose with a minimal health check and a basic accounts/project module; do not implement external APIs yet.
6. Create/update:
   - `README.md` — local setup, environment variables, migrations, running tests.
   - `docs/ARCHITECTURE.md` — architecture and source-of-truth boundaries.
   - `docs/OPEN_QUESTIONS.md` — unresolved business/vendor/API questions.
   - `.env.example` — placeholder configuration only.
7. Before adding a dependency, explain why it is needed. Keep the initial dependency set small.

### Suggested `.env.example` keys (placeholders only)

```dotenv
DJANGO_SECRET_KEY=replace-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://app:password@db:5432/project_system

# OplaCRM - leave blank until vendor/company authorizes access
OPLACRM_BASE_URL=
OPLACRM_API_TOKEN=
OPLACRM_CLIENT_ID=
OPLACRM_CLIENT_SECRET=

# MISA ACT Open API - leave blank until MISA/company authorizes access
MISA_ACT_BASE_URL=https://actapp.misa.vn
MISA_APP_ID=
MISA_ACCESS_CODE=
MISA_ORG_COMPANY_CODE=

# File storage / uploads
MEDIA_ROOT=media
```

Do not assume every listed OplaCRM credential is required; use only the authentication fields documented for the actual OplaCRM integration. Do not expose secrets to browser code.

---

## 12. Definition of a Successful First Demo

The first demo is successful when, using clearly labeled sample data:

- A user can log in.
- A Project Manager can create a project and assign members.
- The project can reference a Sales handover record.
- The Project Manager can create milestones and tasks.
- A Project Member can update assigned task status and submit progress updates/issues.
- The system preserves progress history and records who made changes.
- Purchase/payment tracking records can be associated with a project without pretending to perform official MISA approval.
- The Project Manager dashboard summarizes projects, statuses, upcoming/overdue work, and open issues.
- Project Members see only the projects/tasks permitted by their role.
- The application runs locally through documented setup steps and has basic automated tests.
- No production API, financial data, or customer data is used without explicit authorization.

---

## 13. Final Guiding Principles

- Build the Project workflow first; integrate external systems incrementally.
- Use OplaCRM for Sales-owned information, MISA for official accounting, and Python for Project operational management.
- Do not invent API endpoints or infer unavailable invoice-level data from customer-level debt balances.
- Do not confuse Sales commitments with Project execution plans.
- Do not let the new system silently replace official MISA approval processes.
- Keep all unresolved assumptions visible and easy to revise after the kick-off.
- Optimize for a clear, demonstrable, secure MVP rather than a prematurely complex enterprise architecture.
