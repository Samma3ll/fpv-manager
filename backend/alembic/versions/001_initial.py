"""Create initial schema for FPV Manager.

Revision ID: 001_initial
Revises: 
Create Date: 2026-04-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial database schema."""
    
    # Create Drone table
    op.create_table(
        'drones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('frame_size', sa.Float(), nullable=True),
        sa.Column('motor_kv', sa.Integer(), nullable=True),
        sa.Column('prop_size', sa.Float(), nullable=True),
        sa.Column('weight_g', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_drones_id', 'drones', ['id'], unique=False)
    op.create_index('ix_drones_name', 'drones', ['name'], unique=False)

    # Create BlackboxLog table
    op.create_table(
        'blackbox_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('drone_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('flight_date', sa.DateTime(), nullable=True),
        sa.Column('duration_s', sa.Float(), nullable=True),
        sa.Column('log_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('betaflight_version', sa.String(length=50), nullable=True),
        sa.Column('craft_name', sa.String(length=255), nullable=True),
        sa.Column('pid_roll', sa.Float(), nullable=True),
        sa.Column('pid_pitch', sa.Float(), nullable=True),
        sa.Column('pid_yaw', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['drone_id'], ['drones.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_path')
    )
    op.create_index('ix_blackbox_logs_id', 'blackbox_logs', ['id'], unique=False)
    op.create_index('ix_blackbox_logs_drone_id', 'blackbox_logs', ['drone_id'], unique=False)
    op.create_index('ix_blackbox_logs_status', 'blackbox_logs', ['status'], unique=False)
    op.create_index('ix_blackbox_logs_flight_date', 'blackbox_logs', ['flight_date'], unique=False)

    # Create LogAnalysis table
    op.create_table(
        'log_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('log_id', sa.Integer(), nullable=False),
        sa.Column('module', sa.String(length=100), nullable=False),
        sa.Column('result_json', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['log_id'], ['blackbox_logs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_log_analyses_id', 'log_analyses', ['id'], unique=False)
    op.create_index('ix_log_analyses_log_id', 'log_analyses', ['log_id'], unique=False)
    op.create_index('ix_log_analyses_module', 'log_analyses', ['module'], unique=False)

    # Create Module table
    op.create_table(
        'modules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('module_type', sa.String(length=50), nullable=False),
        sa.Column('config_json', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_modules_id', 'modules', ['id'], unique=False)
    op.create_index('ix_modules_name', 'modules', ['name'], unique=False)
    op.create_index('ix_modules_enabled', 'modules', ['enabled'], unique=False)


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('modules')
    op.drop_table('log_analyses')
    op.drop_table('blackbox_logs')
    op.drop_table('drones')
