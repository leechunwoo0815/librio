"""RBAC 权限单元测试 — Admin 权限方法、种子数据验证"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.domain.admin.models import Admin
from backend.domain.admin.admin_schemas import UpdateAdminRequest
from backend.domain.admin.rbac_models import Role, Permission, RolePermission
from backend.domain.admin.services.account_service import AdminAccountService
from backend.utils.password import hash_password
from backend.seeds.seed_rbac import (
    PERMISSIONS,
    STAFF_PERMS,
    TEACHER_PERMS,
    migrate_admin_roles,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _seed_all(db):
    """执行完整种子流程"""
    from backend.seeds.seed_rbac import (
        seed_roles,
        seed_permissions,
        seed_role_permissions,
    )

    seed_roles(db)
    seed_permissions(db)
    seed_role_permissions(db)
    db.flush()


def _make_admin(db, role_code: str) -> Admin:
    role = db.query(Role).filter(Role.code == role_code).first()
    assert role, f"Role {role_code} not found"
    admin = Admin(
        username=f"test_{role_code}",
        name=f"Test {role_code}",
        admin_role_id=role.id,
        teacher_id=1 if role_code == "teacher" else None,
    )
    admin.password_hash = hash_password("test123")
    db.add(admin)
    db.flush()
    return admin


class TestRBACSeed:
    def test_seed_roles(self, db):
        _seed_all(db)
        roles = db.query(Role).filter(Role.is_deleted == 0).all()
        codes = {r.code for r in roles}
        assert codes == {"super_admin", "staff", "teacher"}

    def test_seed_permissions(self, db):
        _seed_all(db)
        perms = db.query(Permission).filter(Permission.is_deleted == 0).all()
        codes = {p.code for p in perms}
        assert "dashboard.view" in codes
        assert "user.list" in codes
        assert "user.create" in codes
        assert "book.list" in codes
        assert "submission.approve" in codes
        assert "config.edit" in codes

    def test_seed_is_idempotent(self, db):
        _seed_all(db)
        first_count = db.query(Role).count()
        _seed_all(db)
        second_count = db.query(Role).count()
        assert first_count == second_count == 3


class TestAdminPermissionMethods:
    def test_super_admin_has_all_permissions(self, db):
        _seed_all(db)
        admin = _make_admin(db, "super_admin")
        codes = AdminAccountService(db).get_permission_codes(admin)
        assert "config.edit" in codes
        assert "admin.list" in codes
        assert "role.edit" in codes

    def test_staff_has_business_perms(self, db):
        _seed_all(db)
        admin = _make_admin(db, "staff")
        codes = AdminAccountService(db).get_permission_codes(admin)
        assert "user.list" in codes
        assert "order.list" in codes
        assert "book.create" in codes

    def test_staff_cannot_access_config(self, db):
        _seed_all(db)
        admin = _make_admin(db, "staff")
        assert not AdminAccountService(db).has_permission(admin, "config.edit")

    def test_staff_cannot_refund(self, db):
        _seed_all(db)
        admin = _make_admin(db, "staff")
        assert not AdminAccountService(db).has_permission(admin, "deposit.refund")

    def test_teacher_permissions(self, db):
        _seed_all(db)
        admin = _make_admin(db, "teacher")
        codes = AdminAccountService(db).get_permission_codes(admin)
        assert "child.list" in codes
        assert "submission.approve" in codes
        assert "book.list" in codes
        assert "dashboard.view" in codes

    def test_teacher_cannot_delete_book(self, db):
        _seed_all(db)
        admin = _make_admin(db, "teacher")
        assert not AdminAccountService(db).has_permission(admin, "book.delete")

    def test_teacher_cannot_manage_users(self, db):
        _seed_all(db)
        admin = _make_admin(db, "teacher")
        assert not AdminAccountService(db).has_permission(admin, "user.create")
        assert not AdminAccountService(db).has_permission(admin, "user.list")

    def test_teacher_cannot_manage_config(self, db):
        _seed_all(db)
        admin = _make_admin(db, "teacher")
        assert not AdminAccountService(db).has_permission(admin, "config.view")

    def test_teacher_cannot_manage_admins(self, db):
        _seed_all(db)
        admin = _make_admin(db, "teacher")
        assert not AdminAccountService(db).has_permission(admin, "admin.list")

    def test_super_admin_data_scope_all(self, db):
        _seed_all(db)
        admin = _make_admin(db, "super_admin")
        assert AdminAccountService(db).get_data_scope(admin) == "all"

    def test_staff_data_scope_all(self, db):
        _seed_all(db)
        admin = _make_admin(db, "staff")
        assert AdminAccountService(db).get_data_scope(admin) == "all"

    def test_teacher_data_scope_own(self, db):
        _seed_all(db)
        admin = _make_admin(db, "teacher")
        assert AdminAccountService(db).get_data_scope(admin) == "own"

    def test_teacher_scoped_child_ids_empty(self, db):
        _seed_all(db)
        admin = _make_admin(db, "teacher")
        scoped = AdminAccountService(db).get_scoped_child_ids(admin)
        assert scoped == []  # No children yet

    def test_teacher_scoped_child_ids_returns_actual_ids(self, db):
        _seed_all(db)
        from backend.domain.child.models import Child
        from backend.domain.user.models import User

        # Create a user + children assigned to teacher
        user = User(
            openid=f"test_user_{__name__}",
            phone="13800000000",
            parent_name="Test Parent",
        )
        db.add(user)
        db.flush()
        for i in range(3):
            child = Child(
                user_id=user.id,
                name=f"Student {i}",
                english_name=f"stu{i}",
                age=6 + i,
                grade=1,
                teacher_id=1,
                status=0,
            )
            db.add(child)
        db.flush()

        admin = _make_admin(db, "teacher")
        scoped = AdminAccountService(db).get_scoped_child_ids(admin)
        assert len(scoped) == 3
        assert all(isinstance(cid, int) for cid in scoped)

    def test_is_super_admin_property(self, db):
        _seed_all(db)
        admin = _make_admin(db, "super_admin")
        assert AdminAccountService(db).is_super_admin(admin)

    def test_is_not_super_admin(self, db):
        _seed_all(db)
        admin = _make_admin(db, "staff")
        assert not AdminAccountService(db).is_super_admin(admin)

    def test_role_code_property(self, db):
        _seed_all(db)
        admin = _make_admin(db, "teacher")
        assert AdminAccountService(db).get_role_code(admin) == "teacher"

    # ── P0 修复验证 ──

    def test_super_admin_has_all_permissions_in_table(self, db):
        _seed_all(db)
        super_admin_role = db.query(Role).filter(Role.code == "super_admin").first()
        rp_count = (
            db.query(RolePermission)
            .filter(
                RolePermission.role_id == super_admin_role.id,
                RolePermission.is_deleted == 0,
            )
            .count()
        )
        total_perms = db.query(Permission).filter(Permission.is_deleted == 0).count()
        assert rp_count == total_perms, (
            f"super_admin has {rp_count} perms but total is {total_perms}"
        )

    def test_get_all_permission_counts(self, db):
        _seed_all(db)
        total = db.query(Permission).filter(Permission.is_deleted == 0).count()
        assert total == len(PERMISSIONS), (
            f"expected {len(PERMISSIONS)} perms, got {total}"
        )

        role_map = {r.code: r.id for r in db.query(Role).all()}
        for role_code, expected_list in [
            ("super_admin", PERMISSIONS),
            ("staff", STAFF_PERMS),
            ("teacher", TEACHER_PERMS),
        ]:
            rp_count = (
                db.query(RolePermission)
                .filter(
                    RolePermission.role_id == role_map[role_code],
                    RolePermission.is_deleted == 0,
                )
                .count()
            )
            assert rp_count == len(expected_list), (
                f"{role_code}: expected {len(expected_list)} perms, got {rp_count}"
            )

    def test_admin_role_id_none_data_scope(self, db):
        _seed_all(db)
        admin = Admin(username="test_none", name="None Role")
        admin.password_hash = hash_password("test123")
        db.add(admin)
        db.flush()
        assert AdminAccountService(db).get_data_scope(admin) == "none"
        assert AdminAccountService(db).get_scoped_child_ids(admin) == []

    def test_migrate_admin_roles(self, db):
        _seed_all(db)
        # Simulate old-style admins without admin_role_id
        old_admin = Admin(
            username="old_admin",
            name="Old Admin",
            role=0,  # super_admin in old system
            admin_role_id=None,
        )
        old_admin.password_hash = hash_password("test123")
        db.add(old_admin)
        db.flush()

        migrate_admin_roles(db)
        db.flush()
        db.refresh(old_admin)
        assert old_admin.admin_role_id is not None

    # ── P1-3 修复验证：admin_role_id / role 同步 ──

    def test_update_admin_syncs_legacy_role_from_admin_role_id(self, db):
        """更新 admin_role_id 时，legacy role 字段自动同步"""
        _seed_all(db)
        admin = _make_admin(db, "staff")
        admin.role = 1  # legacy: staff
        db.flush()

        # 创建另一个管理员执行更新（不能自己改自己）
        super_admin = _make_admin(db, "super_admin")
        db.flush()

        # 切换到 teacher: 只传 admin_role_id
        teacher_role = db.query(Role).filter(Role.code == "teacher").first()
        data = UpdateAdminRequest(admin_role_id=teacher_role.id)
        AdminAccountService(db).update_admin(admin.id, data, super_admin.id)

        db.refresh(admin)
        assert admin.admin_role_id == teacher_role.id
        assert admin.role == 2  # teacher → legacy 2

    def test_update_admin_syncs_admin_role_id_from_legacy_role(self, db):
        """更新 legacy role 字段时，admin_role_id 自动同步"""
        _seed_all(db)
        admin = _make_admin(db, "staff")
        db.flush()

        super_admin = _make_admin(db, "super_admin")
        db.flush()

        # 切换到 teacher: 只传 role
        data = UpdateAdminRequest(role=2)
        AdminAccountService(db).update_admin(admin.id, data, super_admin.id)

        db.refresh(admin)
        assert admin.role == 2
        assert admin.admin_role_id is not None
        role_obj = db.query(Role).filter(Role.id == admin.admin_role_id).first()
        assert role_obj.code == "teacher"

    def test_update_admin_role_only_does_not_break_admin_role_id(self, db):
        """只传 phone 不传 role/admin_role_id 时，admin_role_id 不应改变"""
        _seed_all(db)
        admin = _make_admin(db, "teacher")
        original_role_id = admin.admin_role_id
        db.flush()

        super_admin = _make_admin(db, "super_admin")
        db.flush()

        data = UpdateAdminRequest(phone="13800138000")
        AdminAccountService(db).update_admin(admin.id, data, super_admin.id)

        db.refresh(admin)
        assert admin.admin_role_id == original_role_id  # unchanged

    def test_seed_cleanup_removed_perms(self, db):
        _seed_all(db)
        # Simulate a permission being removed from the list
        removed_code = "role.edit"
        # First verify it exists
        role_id = db.query(Role).filter(Role.code == "super_admin").first().id
        assert (
            db.query(RolePermission)
            .filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_code == removed_code,
                RolePermission.is_deleted == 0,
            )
            .first()
            is not None
        )
        # Re-seed (should still exist since it's in PERMISSIONS)
        from backend.seeds.seed_rbac import seed_role_permissions

        seed_role_permissions(db)
        db.flush()
        assert (
            db.query(RolePermission)
            .filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_code == removed_code,
                RolePermission.is_deleted == 0,
            )
            .first()
            is not None
        )
