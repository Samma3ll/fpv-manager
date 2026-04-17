"""Add picture_path to drones table.

Revision ID: 004_add_drone_picture_path
Revises: 003_add_analysis_modules
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "004_add_drone_picture_path"
down_revision = "003_add_analysis_modules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add picture_path column to drones table."""
    op.add_column("drones", sa.Column("picture_path", sa.String(length=512), nullable=True))


def downgrade() -> None:
    """Remove picture_path column from drones table."""
    op.drop_column("drones", "picture_path")
