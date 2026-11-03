# Kiến trúc — Phase 1

> Đây là kiến trúc đề xuất cho demo, chưa phải kiến trúc được công ty phê duyệt. Chi tiết bối cảnh: [CLAUDE.md](../CLAUDE.md).

## 1. Tổng quan

- **Modular monolith Django** + PostgreSQL, chạy bằng Docker Compose (service `web` + `db`).
- Giao diện server-rendered: Django Templates + Bootstrap 5 (CDN jsdelivr, phiên bản cố định). Chart.js 4.4.1 chỉ dùng ở dashboard.
- **Chưa dùng HTMX ở Phase 1**: các form hiện tại đều là trang riêng, chưa có tương tác nào cần cập nhật một phần trang. Sẽ thêm khi có nhu cầu cụ thể.
- Dependency Python: `Django 5.2 (LTS)`, `psycopg 3`, `django-environ`.

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
| `dashboard` | Tổng hợp chỉ đọc; lệnh `seed_demo_data` | tất cả |

Các app `sales/`, `finance/`, `integrations/` **chưa tạo**; sẽ thêm ở Phase 2/3.

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

- Dự án mà người dùng không được xem trả về **404**, không phải 403, để không lộ việc dự án đó tồn tại.
- Trường tài chính bị **loại khỏi form** (`ScopedModelForm.finance_fields`) và không được render cho người không có quyền, nên dữ liệu không rời server.
- Superuser được coi như PROJECT_MANAGER.

Toàn bộ chính sách trên là **giả định cho demo**; xem [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## 6. Dashboard

- **Dashboard PM:** số dự án theo trạng thái (biểu đồ), dự án cần chú ý (*quy tắc demo*: quá hạn kế hoạch / có task quá hạn / có vấn đề Cao trở lên đang mở), task quá hạn, mốc trong 14 ngày tới, vấn đề đang mở, cập nhật gần đây, bàn giao đang chờ, đề nghị mua hàng/thanh toán đang theo dõi (sắp xếp theo lần ghi nhận cũ nhất).
- **Chưa hiển thị tổng hợp tài chính**, vì chưa có nguồn đáng tin cậy.
- **Việc của tôi:** task đang mở, quá hạn, đến hạn trong 7 ngày, task đang làm nhưng chưa cập nhật trong 7 ngày (*quy tắc demo*), vấn đề được giao, dự án của tôi.
- Các ngưỡng nằm ở đầu `apps/dashboard/views.py`.

## 7. Hướng mở rộng (Phase 2/3)

- Thêm app `integrations/` chứa client/adapter OplaCRM và MISA, tách hoàn toàn khỏi view/model, cùng `SyncState`/`SyncLog`.
- OplaCRM Opportunity Won → tạo `SalesHandover` ở trạng thái PENDING với `source_system = OPLACRM`. **Không** tự tạo Project.
- MISA: đọc dữ liệu chỉ đọc vào các bảng snapshot riêng trong app `finance/`; chỉ thêm giá trị `status_source` kiểu "MISA_API" khi trạng thái thực sự đọc được từ API.
