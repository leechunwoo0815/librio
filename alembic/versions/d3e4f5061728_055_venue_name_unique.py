"""055 venue.name 唯一约束（F-091）

存量已核查无重名（开发库 GROUP BY name HAVING COUNT>1 为空），
应用层 create_venue 已加查重（ConflictError），DB unique 为兜底。

Revision ID: d3e4f5061728
Revises: c2d3e4f50617
Create Date: 2026-08-09
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d3e4f5061728"
down_revision = "c2d3e4f50617"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_venue_name", "venue", ["name"])


def downgrade() -> None:
    op.drop_constraint("uq_venue_name", "venue", type_="unique")
