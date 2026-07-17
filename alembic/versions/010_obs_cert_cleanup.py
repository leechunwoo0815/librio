"""010 新增观察期报告/晋级证书表，删除废弃表

Revision ID: 010_obs_cert_cleanup
Revises: 7641c1e2bb62 (008_reading_submission_wordcount)
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa

revision = "010_obs_cert_cleanup"
down_revision = "7641c1e2bb62"
branch_labels = None
depends_on = None


def upgrade():
    # 新增观察期报告表
    op.create_table(
        "observation_report",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "child_id",
            sa.BigInteger(),
            sa.ForeignKey("child.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("total_books_read", sa.Integer(), server_default="0"),
        sa.Column("total_words_read", sa.Integer(), server_default="0"),
        sa.Column("total_reading_minutes", sa.Integer(), server_default="0"),
        sa.Column("quizzes_attempted", sa.Integer(), server_default="0"),
        sa.Column("quizzes_passed", sa.Integer(), server_default="0"),
        sa.Column("current_level", sa.String(50), nullable=True),
        sa.Column("teacher_comment", sa.Text(), nullable=True),
        sa.Column("teacher_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.SmallInteger(), server_default="1"),
        sa.Column("observation_start", sa.DateTime(), nullable=True),
        sa.Column("observation_end", sa.DateTime(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("create_time", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("update_time", sa.DateTime(), server_default=sa.func.now()),
    )

    # 新增晋级证书表
    op.create_table(
        "level_certificate",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "child_id",
            sa.BigInteger(),
            sa.ForeignKey("child.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "level_id", sa.BigInteger(), sa.ForeignKey("level.id"), nullable=False
        ),
        sa.Column("level_name", sa.String(50), nullable=False),
        sa.Column("child_name", sa.String(50), nullable=False),
        sa.Column("child_english_name", sa.String(50), nullable=True),
        sa.Column("badge_emoji", sa.String(10), nullable=True),
        sa.Column("certificate_no", sa.String(50), nullable=True, unique=True),
        sa.Column("create_time", sa.DateTime(), server_default=sa.func.now()),
    )

    # 删除废弃表
    op.drop_table("borrow")
    op.drop_table("reservation")
    op.drop_table("collection")


def downgrade():
    op.drop_table("level_certificate")
    op.drop_table("observation_report")
