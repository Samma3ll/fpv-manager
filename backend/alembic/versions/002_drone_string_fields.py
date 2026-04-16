"""Alter Drone model: frame_size and prop_size to String.

Revision ID: 002_drone_string_fields
Revises: 001_initial
Create Date: 2026-04-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_drone_string_fields'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade: Change frame_size and prop_size from Float to String."""
    # Drop the constraints/indexes if needed
    op.alter_column('drones', 'frame_size',
                    existing_type=sa.Float(),
                    type_=sa.String(50),
                    nullable=True)
    op.alter_column('drones', 'prop_size',
                    existing_type=sa.Float(),
                    type_=sa.String(50),
                    nullable=True)


def downgrade() -> None:
    """Downgrade: Revert frame_size and prop_size back to Float."""
    op.alter_column('drones', 'frame_size',
                    existing_type=sa.String(50),
                    type_=sa.Float(),
                    nullable=True)
    op.alter_column('drones', 'prop_size',
                    existing_type=sa.String(50),
                    type_=sa.Float(),
                    nullable=True)
