# Project System — Demo Phase 1

Ứng dụng web nội bộ quản lý dự án cho Phòng Dự án (Django + PostgreSQL), phiên bản demo **Phase 1 – Core Project System**.

> ⚠️ Toàn bộ dữ liệu trong demo là **dữ liệu mẫu**. Phase 1 **không** kết nối OplaCRM hay MISA. Trạng thái mua hàng/thanh toán trong hệ thống **không phải** trạng thái phê duyệt chính thức trên MISA.

Bối cảnh nghiệp vụ và nguyên tắc: xem [CLAUDE.md](CLAUDE.md). Kiến trúc: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Câu hỏi mở và giả định: [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md).

## Phase 1 gồm những gì

| Chức năng | Trạng thái |
|---|---|
| Đăng nhập, phân quyền theo vai trò (Group) và theo dự án | ✅ |
| Danh sách / chi tiết / tạo / sửa dự án, thành viên dự án | ✅ |
| Hồ sơ bàn giao từ Sales (nhập tay), tiếp nhận, tạo dự án từ bàn giao (tối đa 1 dự án/bàn giao) | ✅ |
| Biên bản kickoff, thông tin hợp đồng, tài liệu (chỉ metadata + vị trí lưu, không upload file) | ✅ |
| Mốc tiến độ, công việc, giao việc, cập nhật trạng thái công việc | ✅ |
| Lịch sử cập nhật tiến độ (chỉ thêm, không sửa/xoá), vấn đề/rủi ro | ✅ |
| Theo dõi đề nghị mua hàng / thanh toán + lịch sử trạng thái có nguồn | ✅ |
| Dashboard Quản lý dự án, trang "Việc của tôi" cho thành viên | ✅ |
| Nhật ký thay đổi (AuditLog) cho các thay đổi quan trọng | ✅ |
| Lệnh tạo dữ liệu mẫu, test tự động | ✅ |
| Tích hợp OplaCRM (Phase 2), MISA (Phase 3) | ❌ chưa làm — chờ cấp quyền |

## Yêu cầu

- Docker Desktop (đã bật). Không cần cài Python trên máy.

## Chạy local

```bash
# 1. Tạo file cấu hình local từ mẫu, rồi sửa giá trị
cp .env.example .env
#    - DJANGO_SECRET_KEY: chuỗi ngẫu nhiên dài
#    - POSTGRES_PASSWORD và mật khẩu trong DATABASE_URL: đặt giống nhau
#    - DEMO_USER_PASSWORD: mật khẩu cho các tài khoản demo

# 2. Build và chạy (web tự chạy migrate khi khởi động)
docker compose up --build

# 3. (Terminal khác) Tạo dữ liệu mẫu và tài khoản demo
docker compose exec web python manage.py seed_demo_data
#    Tạo lại từ đầu:  docker compose exec web python manage.py seed_demo_data --reset

# 4. (Tuỳ chọn) Tạo tài khoản quản trị để vào /admin/
docker compose exec web python manage.py createsuperuser
```

Mở <http://localhost:8000>. Kiểm tra tình trạng: <http://localhost:8000/health/>.

**Tài khoản demo** (mật khẩu = `DEMO_USER_PASSWORD` trong `.env`):

| Tài khoản | Vai trò | Thấy gì |
|---|---|---|
| `pm.demo` | PROJECT_MANAGER | Tất cả dự án, dashboard, bàn giao, số tiền |
| `member.an`, `member.binh` | PROJECT_MEMBER | Chỉ dự án mình tham gia; cập nhật task của mình; không thấy số tiền |
| `finance.demo` | PROJECT_MEMBER + FINANCE_VIEWER | Như thành viên, nhưng thấy các trường tài chính |
| `sales.demo` | SALES_VIEWER | Chỉ xem hồ sơ bàn giao (không thấy giá trị bán — xem OPEN_QUESTIONS) |

## Lệnh thường dùng

```bash
docker compose exec web python manage.py test            # chạy toàn bộ test
docker compose exec web python manage.py makemigrations  # sau khi sửa model
docker compose exec web python manage.py migrate
docker compose down          # dừng
docker compose down -v       # dừng và XOÁ dữ liệu Postgres local
```

Nếu `docker compose build` báo `additional privileges requested: pass "--allow=fs.read=Dockerfile"` (gặp khi chạy từ Git Bash trên Windows), hãy chạy lệnh từ PowerShell, hoặc build trực tiếp: `docker build -t dashboard_demo-web .`.

## Biến môi trường

Xem [.env.example](.env.example). Không commit `.env`. Các biến `OPLACRM_*` và `MISA_*` chưa được dùng ở Phase 1 và phải để trống cho tới khi công ty/nhà cung cấp cấp quyền.

## Cấu trúc thư mục

```text
config/            settings, urls, wsgi
apps/
  core/            TrackedModel, AuditLog, StatusEntryBase, health check, helper form/template
  accounts/        User, vai trò (roles.py), đăng nhập
  projects/        Project, SalesHandover, Member, Kickoff, Contract, Document,
                   Milestone, Task, ProgressUpdate, Issue; permissions.py, services.py
  procurement/     PurchaseRequest, PurchaseItem, PurchaseStatusEntry
  payments/        PaymentRequest, PaymentStatusEntry
  dashboard/       Dashboard PM, Việc của tôi, lệnh seed_demo_data
templates/         Django templates (Bootstrap 5)
docs/              ARCHITECTURE.md, OPEN_QUESTIONS.md
```

## Quy ước

- Thảo luận nghiệp vụ bằng tiếng Việt; tên class, hàm, trường DB và module bằng tiếng Anh. Giao diện người dùng dùng tiếng Việt.
- Kiểm tra quyền luôn đi qua `apps/accounts/roles.py` và `apps/projects/permissions.py`, không đặt quy tắc quyền rải rác trong view/template.
- Mọi thay đổi trạng thái task đều đi qua `services.change_task_status` để luôn sinh `ProgressUpdate`.
- Khi thêm dependency, ghi lý do trong PR.
