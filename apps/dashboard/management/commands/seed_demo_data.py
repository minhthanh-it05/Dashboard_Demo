"""Create clearly-labelled sample data for local demos.

Every customer/supplier name here is fictional and every record is flagged
`is_demo_data=True`. Never run against a production database.
"""

import os
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts import roles
from apps.core.models import StatusSource
from apps.payments.models import PaymentRequest, PaymentStatusEntry
from apps.procurement.models import PurchaseItem, PurchaseRequest, PurchaseStatusEntry
from apps.projects.models import (
    ContractStatus,
    DocumentType,
    HandoverStatus,
    IssueKind,
    IssueStatus,
    KickoffRecord,
    MilestoneStatus,
    Priority,
    ProgressUpdate,
    Project,
    ProjectContract,
    ProjectDocument,
    ProjectIssue,
    ProjectMember,
    ProjectMilestone,
    ProjectStatus,
    ProjectTask,
    SalesHandover,
    Severity,
    TaskStatus,
)

DEMO_USERS = [
    # username, first, last, roles
    ("pm.demo", "Quản lý", "Dự án (Demo)", [roles.PROJECT_MANAGER]),
    ("member.an", "An", "Nguyễn (Demo)", [roles.PROJECT_MEMBER]),
    ("member.binh", "Bình", "Trần (Demo)", [roles.PROJECT_MEMBER]),
    ("sales.demo", "Sales", "Viewer (Demo)", [roles.SALES_VIEWER]),
    ("finance.demo", "Finance", "Viewer (Demo)", [roles.FINANCE_VIEWER, roles.PROJECT_MEMBER]),
]


class Command(BaseCommand):
    help = "Tạo dữ liệu mẫu (đánh dấu is_demo_data) và tài khoản demo cho môi trường local."

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Mật khẩu cho tài khoản demo (mặc định: biến DEMO_USER_PASSWORD).")
        parser.add_argument("--reset", action="store_true", help="Xoá dữ liệu mẫu cũ trước khi tạo lại.")
        parser.add_argument("--force", action="store_true", help="Cho phép chạy khi DEBUG=False.")

    def handle(self, *args, password=None, reset=False, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError("DEBUG=False: từ chối tạo dữ liệu mẫu. Dùng --force nếu chắc chắn đây là môi trường demo.")
        password = password or os.environ.get("DEMO_USER_PASSWORD")
        if not password:
            raise CommandError("Cần --password hoặc biến môi trường DEMO_USER_PASSWORD.")

        with transaction.atomic():
            users = self._ensure_users(password)
            if reset:
                self._delete_demo_data()
            elif Project.objects.filter(is_demo_data=True).exists():
                self.stdout.write(self.style.WARNING("Đã có dữ liệu mẫu; bỏ qua. Dùng --reset để tạo lại."))
                return
            self._create_demo_data(users)

        self.stdout.write(self.style.SUCCESS("Đã tạo dữ liệu mẫu. Tài khoản: " + ", ".join(u[0] for u in DEMO_USERS)))

    def _ensure_users(self, password):
        User = get_user_model()
        users = {}
        for username, first, last, role_names in DEMO_USERS:
            user, _ = User.objects.get_or_create(username=username, defaults={"first_name": first, "last_name": last})
            user.set_password(password)
            user.save()
            user.groups.set([Group.objects.get_or_create(name=r)[0] for r in role_names])
            users[username] = user
        return users

    def _delete_demo_data(self):
        PaymentRequest.objects.filter(is_demo_data=True).delete()
        PurchaseRequest.objects.filter(is_demo_data=True).delete()
        Project.objects.filter(is_demo_data=True).delete()
        SalesHandover.objects.filter(is_demo_data=True).delete()

    def _create_demo_data(self, users):
        pm, an, binh, finance = users["pm.demo"], users["member.an"], users["member.binh"], users["finance.demo"]
        today = timezone.localdate()

        def d(days):
            return today + timedelta(days=days)

        # --- Handovers -----------------------------------------------------
        accepted = SalesHandover.objects.create(
            external_opportunity_id="DEMO-OPP-001",
            customer_name="Công ty Mẫu Alpha (DEMO)",
            deal_name="Hệ thống camera nhà xưởng (DEMO)",
            sales_owner_name="Sales Mẫu",
            committed_value=Decimal("1250000000"),
            committed_start_date=d(-45),
            committed_end_date=d(60),
            committed_scope="Cung cấp và lắp đặt 120 camera, 1 trung tâm giám sát. (Dữ liệu mẫu)",
            boq_reference="BOQ-DEMO-001",
            status=HandoverStatus.ACCEPTED,
            review_note="Đủ thông tin để triển khai.",
            reviewed_by=pm,
            reviewed_at=timezone.now() - timedelta(days=40),
            is_demo_data=True,
            created_by=pm,
        )
        SalesHandover.objects.create(
            external_opportunity_id="DEMO-OPP-002",
            customer_name="Công ty Mẫu Beta (DEMO)",
            deal_name="Nâng cấp mạng văn phòng (DEMO)",
            sales_owner_name="Sales Mẫu",
            committed_value=Decimal("380000000"),
            committed_start_date=d(10),
            committed_end_date=d(70),
            committed_scope="Thay thế switch lõi và Wi-Fi 3 tầng. (Dữ liệu mẫu)",
            status=HandoverStatus.PENDING,
            is_demo_data=True,
            created_by=pm,
        )
        SalesHandover.objects.create(
            external_opportunity_id="DEMO-OPP-003",
            customer_name="Công ty Mẫu Gamma (DEMO)",
            deal_name="Phòng họp trực tuyến (DEMO)",
            committed_value=Decimal("210000000"),
            status=HandoverStatus.NEEDS_INFO,
            review_note="Thiếu BOQ chi tiết và ngày bàn giao cam kết.",
            reviewed_by=pm,
            reviewed_at=timezone.now() - timedelta(days=2),
            is_demo_data=True,
            created_by=pm,
        )

        # --- Projects ------------------------------------------------------
        p1 = Project.objects.create(
            name="Hệ thống camera nhà xưởng (DEMO)",
            customer_name="Công ty Mẫu Alpha (DEMO)",
            description="Dự án mẫu tạo từ bàn giao DEMO-OPP-001.",
            status=ProjectStatus.IN_PROGRESS,
            manager=pm,
            planned_start_date=d(-40),
            planned_end_date=d(50),
            handover=accepted,
            is_demo_data=True,
            created_by=pm,
        )
        p2 = Project.objects.create(
            name="Triển khai phần mềm kho (DEMO)",
            customer_name="Công ty Mẫu Delta (DEMO)",
            status=ProjectStatus.IN_PROGRESS,
            manager=pm,
            planned_start_date=d(-90),
            planned_end_date=d(-5),
            is_demo_data=True,
            created_by=pm,
        )
        p3 = Project.objects.create(
            name="Bảo trì hạ tầng định kỳ (DEMO)",
            customer_name="Công ty Mẫu Epsilon (DEMO)",
            status=ProjectStatus.READY,
            manager=pm,
            planned_start_date=d(7),
            planned_end_date=d(120),
            is_demo_data=True,
            created_by=pm,
        )
        for project, user, role in [
            (p1, an, "Kỹ thuật triển khai"),
            (p1, binh, "Mua hàng"),
            (p1, finance, "Theo dõi tài chính"),
            (p2, binh, "Triển khai phần mềm"),
            (p3, an, "Kỹ thuật"),
        ]:
            ProjectMember.objects.create(project=project, user=user, project_role=role, created_by=pm)

        # --- Records -------------------------------------------------------
        KickoffRecord.objects.create(
            project=p1,
            meeting_date=d(-38),
            location="Phòng họp tầng 3 (DEMO)",
            attendees="Project, Sales, Kế toán, Kho",
            minutes="Thống nhất phạm vi, mốc khảo sát và lịch giao hàng. (Dữ liệu mẫu)",
            follow_up="Sales gửi bản BOQ cuối cùng.",
            created_by=pm,
        )
        contract_doc = ProjectDocument.objects.create(
            project=p1,
            doc_type=DocumentType.CONTRACT,
            title="Hợp đồng mẫu Alpha (DEMO)",
            external_reference=r"\\fileserver\demo\alpha\hop-dong.pdf",
            created_by=pm,
        )
        ProjectContract.objects.create(
            project=p1,
            contract_number="HD-DEMO-001",
            title="Hợp đồng cung cấp và lắp đặt camera (DEMO)",
            status=ContractStatus.SIGNED,
            signed_date=d(-35),
            contract_value=Decimal("1250000000"),
            document=contract_doc,
            created_by=pm,
        )

        # --- Plan ----------------------------------------------------------
        m1 = ProjectMilestone.objects.create(
            project=p1, name="Khảo sát xong", due_date=d(-20), status=MilestoneStatus.DONE, completed_date=d(-22), sort_order=1
        )
        m2 = ProjectMilestone.objects.create(
            project=p1, name="Giao hàng thiết bị", due_date=d(7), status=MilestoneStatus.IN_PROGRESS, sort_order=2
        )
        ProjectMilestone.objects.create(project=p1, name="Nghiệm thu", due_date=d(50), sort_order=3)
        m4 = ProjectMilestone.objects.create(
            project=p2, name="Go-live", due_date=d(-5), status=MilestoneStatus.IN_PROGRESS, sort_order=1
        )
        ProjectMilestone.objects.create(project=p3, name="Kickoff", due_date=d(10), sort_order=1)

        def task(project, title, assignee, due, status=TaskStatus.TODO, milestone=None, priority=Priority.MEDIUM):
            return ProjectTask.objects.create(
                project=project,
                milestone=milestone,
                title=title,
                assignee=assignee,
                start_date=d(-30),
                due_date=due,
                status=status,
                priority=priority,
                completed_at=timezone.now() if status == TaskStatus.DONE else None,
                created_by=pm,
            )

        t1 = task(p1, "Khảo sát mặt bằng", an, d(-25), TaskStatus.DONE, m1)
        t2 = task(p1, "Đặt hàng camera và đầu ghi", binh, d(3), TaskStatus.IN_PROGRESS, m2, Priority.HIGH)
        task(p1, "Lập bản vẽ đi dây", an, d(-2), TaskStatus.IN_PROGRESS, m2, Priority.HIGH)
        task(p1, "Chuẩn bị hồ sơ nghiệm thu", an, d(45))
        t5 = task(p2, "Đào tạo người dùng kho", binh, d(-8), TaskStatus.BLOCKED, m4, Priority.HIGH)
        task(p2, "Chuyển dữ liệu tồn kho", binh, d(-3), TaskStatus.IN_PROGRESS, m4)
        task(p3, "Lập lịch bảo trì quý", an, d(12))

        # --- Progress history ---------------------------------------------
        ProgressUpdate.objects.create(
            project=p1, task=t1, author=an, percent=100, note="Đã khảo sát xong.",
            status_from=TaskStatus.IN_PROGRESS, status_to=TaskStatus.DONE,
        )
        ProgressUpdate.objects.create(project=p1, task=t2, author=binh, percent=40, note="Đã nhận báo giá 2 NCC.")
        ProgressUpdate.objects.create(project=p1, author=pm, percent=35, note="Tiến độ chung do PM đánh giá. (Dữ liệu mẫu)")
        stale = ProgressUpdate.objects.create(project=p2, task=t5, author=binh, note="Chờ khách hàng xếp lịch đào tạo.")
        ProgressUpdate.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(days=10))
        ProgressUpdate.objects.create(project=p2, author=pm, percent=70, note="Tiến độ chung do PM đánh giá. (Dữ liệu mẫu)")

        # --- Issues --------------------------------------------------------
        ProjectIssue.objects.create(
            project=p1, task=t2, kind=IssueKind.RISK, title="NCC có thể giao trễ 1 tuần",
            severity=Severity.MEDIUM, assignee=binh, reported_by=binh, created_by=binh,
        )
        ProjectIssue.objects.create(
            project=p2, task=t5, kind=IssueKind.ISSUE, title="Khách hàng chưa bố trí người học",
            severity=Severity.HIGH, status=IssueStatus.IN_PROGRESS, assignee=pm, reported_by=binh, created_by=binh,
        )

        # --- Purchase / payment tracking ----------------------------------
        pr = PurchaseRequest.objects.create(
            project=p1, title="Mua camera và đầu ghi", requester=binh, request_date=d(-10),
            supplier_name="Nhà cung cấp Mẫu A (DEMO)", is_demo_data=True, created_by=binh,
        )
        PurchaseItem.objects.create(purchase_request=pr, description="Camera IP 4MP", quantity=120, unit="cái", unit_cost=Decimal("2500000"))
        PurchaseItem.objects.create(purchase_request=pr, description="Đầu ghi 64 kênh", quantity=2, unit="bộ", unit_cost=Decimal("45000000"))
        PurchaseStatusEntry.objects.create(
            purchase_request=pr, status_label="Đã gửi PM xem xét", status_source=StatusSource.DEMO,
            evidence_note="Dữ liệu mẫu – không phải trạng thái MISA.", recorded_by=binh,
        )
        pr2 = PurchaseRequest.objects.create(
            project=p2, title="Mua máy quét mã vạch", requester=binh, request_date=d(-20),
            supplier_name="Nhà cung cấp Mẫu B (DEMO)", is_demo_data=True, created_by=binh,
        )
        PurchaseItem.objects.create(purchase_request=pr2, description="Máy quét mã vạch", quantity=10, unit="cái", unit_cost=Decimal("3200000"))

        pay = PaymentRequest.objects.create(
            project=p1, payee_name="Nhà cung cấp Mẫu A (DEMO)", amount=Decimal("150000000"),
            reason="Tạm ứng 50% đơn hàng camera (Dữ liệu mẫu)", purchase_request=pr, requester=pm,
            request_date=d(-5), is_demo_data=True, created_by=pm,
        )
        PaymentStatusEntry.objects.create(
            payment_request=pay, status_label="Project Director đã xem", status_source=StatusSource.DEMO,
            evidence_note="Dữ liệu mẫu – không phải trạng thái MISA.", recorded_by=pm,
        )
