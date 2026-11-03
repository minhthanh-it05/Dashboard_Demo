# Kiến trúc — Phase 1–3 (demo)

> Đây là kiến trúc đề xuất cho demo, chưa phải kiến trúc được công ty phê duyệt. Chi tiết bối cảnh: [CLAUDE.md](../CLAUDE.md).

## 1. Tổng quan

- **Modular monolith Django** + PostgreSQL, chạy bằng Docker Compose (service `web` + `db`).
- Giao diện server-rendered: Django Templates + Bootstrap 5 (CDN jsdelivr, phiên bản cố định). Chart.js 4.4.1 chỉ dùng ở dashboard.
- **Chưa dùng HTMX ở Phase 1**: các form hiện tại đều là trang riêng, chưa có tương tác nào cần cập nhật một phần trang. Sẽ thêm khi có nhu cầu cụ thể.
- Dependency Python: `Django 5.2 (LTS)`, `psycopg 3`, `django-environ`, `requests` (HTTP client cho live adapter ở Phase 2/3).

## 2. Ranh giới nguồn dữ liệu (source of truth)

| Hệ thống | Sở hữu | Phase 1 |
|---|---|---|
| OplaCRM | Lead, Account, Opportunity, giá trị bán… | Không kết nối. Hồ sơ bàn giao nhập tay, `source_system = MANUAL` |
| MISA AMIS | Kế toán, phê duyệt mua hàng/thanh toán chính thức | Không kết nối. Trạng thái do người dùng ghi nhận, luôn kèm `status_source` |
| Ứng dụng này | Dự án, kế hoạch, mốc, task, tiến độ, vấn đề, thành viên, tiếp nhận bàn giao | Nguồn chính |

Các trường Sales cam kết (`SalesHandover.committed_*`) được **tách riêng** khỏi kế hoạch thực hiện của Project (`Project.planned_*`, milestone, task). Khi tạo dự án từ bàn giao, ngày cam kết chỉ được dùng làm giá trị gợi ý ban đầu.

## 3. Các app

| App | Trách nhiệm | Phụ thuộc |
|---|---|---|
| `core` | `TrackedModel` (created/updated by/at), `AuditLog`, `StatusEntryBase`, `SourceSystem`, `StatusSource`, health check, helper | — |
| `accounts` | `User` (custom), vai trò và hàm kiểm tra vai trò (`roles.py`) | core |
| `projects` | Dự án, bàn giao Sales, thành viên, kickoff, hợp đồng, tài liệu, mốc, task, tiến độ, vấn đề; `permissions.py`, `services.py` | core, accounts |
| `procurement` | Theo dõi đề nghị mua hàng | projects |
| `payments` | Theo dõi đề nghị thanh toán | projects, procurement |
| `integrations` | Hạ tầng tích hợp dùng chung: HTTP client, record chuẩn hoá, adapter OplaCRM/MISA (mock + live), `SyncRun`/`SyncState`, runner, trang trạng thái | core, accounts (**không** phụ thuộc app nghiệp vụ) |
| `sales` | Read model OplaCRM (Account, Opportunity); đồng bộ; Opportunity thắng → hồ sơ bàn giao | integrations, projects |
| `finance` | Snapshot công nợ/tồn kho từ MISA hoặc file CSV; lịch sử nhập | integrations |
| `dashboard` | Tổng hợp chỉ đọc; lệnh `seed_demo_data` | tất cả |

## 4. Mô hình dữ liệu

```text
SalesHandover 1 ─── 0..1 Project ──┬── * ProjectMember ── User
  (committed_*)        (planned_*) ├── * KickoffRecord
                                   ├── * ProjectDocument ── 0..* ProjectContract
                                   ├── * ProjectMilestone ── * ProjectTask
                                   ├── * ProjectTask ── * ProgressUpdate (append-only)
                                   ├── * ProgressUpdate (task = null → cập nhật chung)
                                   ├── * ProjectIssue (ISSUE / RISK)
                                   ├── * PurchaseRequest ──┬── * PurchaseItem
                                   │                       └── * PurchaseStatusEntry
                                   └── * PaymentRequest ──── * PaymentStatusEntry
                                          └── 0..1 PurchaseRequest
AuditLog → bất kỳ đối tượng nào (content_type + object_id)
```

Điểm chính:

- **ID:** `Project.id` là UUID; `Project.code` là mã dễ đọc tự sinh `PRJ-YYYY-NNN`. Đề nghị mua hàng và thanh toán tự sinh `PR-YYYY-NNN` và `PAY-YYYY-NNN` nếu để trống. Định dạng mã chưa được xác nhận.
- **Chống trùng bàn giao:** unique `(source_system, external_opportunity_id)` khi mã không rỗng; `Project.handover` là OneToOne nên mỗi bàn giao tạo được tối đa một dự án. Việc tạo dự án khoá dòng handover bằng `select_for_update`.
- **Lịch sử:** `ProgressUpdate` và `*StatusEntry` chỉ thêm, không sửa; admin cũng để chỉ đọc. Mọi thay đổi trạng thái task đi qua `services.change_task_status`, luôn sinh một `ProgressUpdate` (trạng thái trước → sau) và một `AuditLog`.
- **Tiến độ:** **không có công thức.** Màn hình hiển thị % gần nhất do người dùng báo cáo cho cấp dự án (ProgressUpdate có `task = null`) và ghi rõ đây là số tự báo cáo.
- **Trạng thái mua hàng/thanh toán:** là nhãn text tự do, không mã hoá chuỗi phê duyệt. `status_source` gồm `DEMO`, `INTERNAL`, `MISA_REFERENCED`; giá trị `MISA_REFERENCED` bắt buộc có bằng chứng. Người dùng không chọn được `DEMO`.
- **Tài liệu:** chỉ lưu metadata và vị trí file (link hoặc đường dẫn), không upload.
- **Dữ liệu mẫu:** `is_demo_data` trên Project, SalesHandover, PurchaseRequest và PaymentRequest; banner "DỮ LIỆU MẪU" bật bằng `DEMO_MODE`.

## 5. Phân quyền

Thực thi ở backend, qua `apps/accounts/roles.py` (vai trò) và `apps/projects/permissions.py` (theo đối tượng).

| Hành động | PROJECT_MANAGER | PROJECT_MEMBER | SALES_VIEWER | FINANCE_VIEWER |
|---|---|---|---|---|
| Xem dự án | Tất cả | Dự án mình tham gia/quản lý | — | (theo vai trò khác) |
| Tạo/sửa dự án, thành viên, mốc, task, kickoff, hợp đồng, tài liệu | ✅ | ❌ | ❌ | ❌ |
| Đổi trạng thái task | Mọi task | Task được giao cho mình | ❌ | — |
| Gửi cập nhật tiến độ | ✅ | ✅ (chỉ chọn được task của mình) | ❌ | — |
| Báo cáo vấn đề / sửa vấn đề | ✅ / mọi vấn đề | ✅ / vấn đề mình báo cáo hoặc được giao | ❌ | — |
| Tạo/sửa đề nghị mua hàng/thanh toán, ghi nhận trạng thái | ✅ | ❌ (chỉ xem) | ❌ | — |
| Xem/nhập hồ sơ bàn giao | Xem + nhập + tiếp nhận | ❌ | Chỉ xem | — |
| Xem trường tài chính (giá trị bán, giá trị HĐ, đơn giá, số tiền) | ✅ | ❌ | ❌ | ✅ |
| Dashboard PM | ✅ | ❌ (dùng "Việc của tôi") | ❌ | ❌ |
| Xem cơ hội OplaCRM (mirror) | ✅ | ❌ | ✅ (không thấy giá trị) | — |
| Xem dữ liệu tài chính (công nợ, tồn kho) | ✅ | ❌ | ❌ | ✅ |
| Nhập file CSV tài chính | ❌ | ❌ | ❌ | ✅ |
| Xem trang đồng bộ / chạy đồng bộ | Xem | ❌ | ❌ | ❌ |

SYSTEM_ADMIN: xem trang đồng bộ và **chạy** job đồng bộ; không xem được dữ liệu dự án hay tài chính (trừ khi có thêm vai trò khác).

- Dự án mà người dùng không được xem trả về **404**, không phải 403, để không lộ việc dự án đó tồn tại.
- Trường tài chính bị **loại khỏi form** (`ScopedModelForm.finance_fields`) và không được render cho người không có quyền, nên dữ liệu không rời server.
- Superuser được coi như PROJECT_MANAGER.

Toàn bộ chính sách trên là **giả định cho demo**; xem [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## 6. Dashboard

- **Dashboard PM:** số dự án theo trạng thái (biểu đồ), dự án cần chú ý (*quy tắc demo*: quá hạn kế hoạch / có task quá hạn / có vấn đề Cao trở lên đang mở), task quá hạn, mốc trong 14 ngày tới, vấn đề đang mở, cập nhật gần đây, bàn giao đang chờ, đề nghị mua hàng/thanh toán đang theo dõi (sắp xếp theo lần ghi nhận cũ nhất).
- **Chưa hiển thị tổng hợp tài chính**, vì chưa có nguồn đáng tin cậy.
- **Việc của tôi:** task đang mở, quá hạn, đến hạn trong 7 ngày, task đang làm nhưng chưa cập nhật trong 7 ngày (*quy tắc demo*), vấn đề được giao, dự án của tôi.
- Các ngưỡng nằm ở đầu `apps/dashboard/views.py`.

## 7. Tích hợp (Phase 2/3) — đã chuẩn bị, đang chạy MÔ PHỎNG

Chưa có quyền truy cập API, nên Phase 2/3 chỉ dựng hạ tầng và chạy với **dữ liệu mô phỏng**. Không có dòng code nào gọi tới OplaCRM hay MISA thật.

### 7.1 Luồng dữ liệu

```text
            ┌──────────── apps/integrations ─────────────┐
 mode=mock  │ MockProvider ── simulated_data/*.json      │
 mode=live  │ LiveProvider ── JsonHttpClient ── vendor   │──► records.py (DTO nội bộ)
            └────────────────────────────────────────────┘          │
                                                                    ▼
   run_sync() ─ ghi SyncRun / SyncState ◄── sync_fn(context) trong app nghiệp vụ
                                                │
                      ┌─────────────────────────┴────────────────────┐
                 apps/sales                                     apps/finance
     upsert SalesAccount/Opportunity                 store_snapshot → FinanceImportBatch
     Won → SalesHandover PENDING                     (+ import CSV theo mẫu đề xuất)
```

- **Record chuẩn hoá** (`integrations/records.py`) là hợp đồng giữa adapter và app nghiệp vụ. Đây là định dạng **của mình**, không phải schema của nhà cung cấp. Dữ liệu mô phỏng cũng dùng định dạng này để không "bịa" schema của vendor.
- **Chế độ** cấu hình riêng cho từng hệ thống: `OPLACRM_MODE`, `MISA_MODE` = `mock` (mặc định) | `live` | `disabled`.
- **Hướng phụ thuộc:** `integrations` không import app nghiệp vụ. Job đồng bộ được đăng ký vào `integrations.jobs` trong `AppConfig.ready()` của `sales` và `finance`.

### 7.2 Độ tin cậy

- `JsonHttpClient`: có timeout; retry có giới hạn với backoff mũ khi gặp timeout/lỗi kết nối/HTTP 429/5xx (tôn trọng `Retry-After`); không retry lỗi 4xx; có khoảng nghỉ tối thiểu giữa các request (MISA chưa công bố rate limit). Log chỉ ghi method, path và loại lỗi, **không** ghi header, body hay token.
- `run_sync`: luôn ghi một `SyncRun` (đọc/tạo/cập nhật/không đổi/lỗi, kèm danh sách lỗi và cảnh báo). Lỗi bất ngờ chỉ ghi chi tiết vào log máy chủ, không vào DB.
- **Idempotent:** `upsert` chỉ ghi khi giá trị thực sự đổi. Mỗi bản ghi chạy trong savepoint riêng, nên một bản ghi lỗi không làm hỏng cả lô.
- **Con trỏ incremental** (`SyncState.cursor`) chỉ tiến khi lượt chạy **thành công hoàn toàn**. Lượt "thành công một phần" sẽ đọc lại ở lần sau.
- Snapshot tài chính: lô mới thay thế lô cũ (`is_current`, unique theo loại dữ liệu), nên chạy lại không nhân đôi dữ liệu. Import CSV là tất cả hoặc không gì cả, và chặn file trùng nội dung bằng SHA-256.

### 7.3 Quy tắc sở hữu dữ liệu

- Opportunity **thắng** → tạo `SalesHandover` ở trạng thái `PENDING` với `source_system = OPLACRM`, không bao giờ tự tạo Project.
- Các trường `committed_*` của bàn giao chỉ cập nhật theo OplaCRM khi bàn giao còn `PENDING`/`NEEDS_INFO`. Sau khi Project đã chấp nhận hoặc từ chối, khác biệt chỉ được ghi thành **cảnh báo** trong `SyncRun`, không ghi đè.
- Dữ liệu Sales mirror và snapshot tài chính là chỉ đọc (admin cũng không cho sửa).
- Số dư công nợ là **theo đối tượng**, không gắn dự án.

### 7.4 MISA ACT client (`integrations/misa/act_client.py`)

Viết theo ghi chú của nhóm (CLAUDE.md §5.2), **chưa kiểm chứng** với tài liệu hay tenant thật:

- Chỉ cho gọi các action đọc (`READ_ACTIONS`). `save`, `delete`, `set_option`… bị chặn trước khi gửi request.
- Parse envelope `Success/ErrorCode/ErrorMessage/Data/CustomData`; giải mã `Data` lần hai nếu là chuỗi JSON.
- Token được cache tới gần hạn (lề 10 phút), gửi qua header `X-MISA-AccessToken`; phân trang `skip/take` (tối đa 100).
- `LiveMisaProvider` từ chối chạy (`ROW_SCHEMA_CONFIRMED = False`) **trước khi** gọi mạng, cho tới khi xác nhận được schema dòng dữ liệu.

### 7.5 Việc còn lại khi được cấp quyền

| Hệ thống | Việc cần làm |
|---|---|
| OplaCRM | Xác nhận xác thực, endpoint, phân trang, trường incremental và stage "Won" → viết `LiveOplaCRMProvider` (map vào `AccountRecord`/`OpportunityRecord`) → chạy thử trên sandbox → bật `OPLACRM_MODE=live`. Webhook chỉ làm sau khi vendor xác nhận sự kiện, chữ ký và retry. |
| MISA | Xác nhận API áp dụng (AMISKT hay ACT), schema dòng của `get_list_acc_obj_debt` / `get_list_inventory_balance` → viết `_map_*_row`, đặt `ROW_SCHEMA_CONFIRMED = True` → chạy thử. Incremental (`last_sync_time`, các endpoint `*_delete`) và callback (chữ ký HMAC) làm sau khi MISA xác nhận. |
| Lập lịch | Hiện đồng bộ chạy bằng management command hoặc nút bấm. Khi triển khai, cần chọn scheduler (cron / Task Scheduler / Celery beat) và thêm cơ chế khoá chống chạy chồng. |
