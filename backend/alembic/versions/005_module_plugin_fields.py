"""Add analysis_task and frontend_route to modules, seed future module stubs.

Revision ID: 005_module_plugin_fields
Revises: 004_add_drone_picture_path
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "005_module_plugin_fields"
down_revision = "004_add_drone_picture_path"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add plugin architecture columns and seed future module stubs."""
    # Add new columns
    op.add_column("modules", sa.Column("analysis_task", sa.String(length=255), nullable=True))
    op.add_column("modules", sa.Column("frontend_route", sa.String(length=255), nullable=True))

    # Backfill existing analysis modules with their task names and frontend routes
    op.execute("""
        UPDATE modules SET analysis_task = 'analyze_log_step_response', frontend_route = 'step_response'
        WHERE name = 'step_response'
    """)
    op.execute("""
        UPDATE modules SET analysis_task = 'analyze_log_fft', frontend_route = 'fft_noise'
        WHERE name = 'fft_noise'
    """)
    op.execute("""
        UPDATE modules SET analysis_task = 'analyze_log_pid_error', frontend_route = 'pid_error'
        WHERE name = 'pid_error'
    """)
    op.execute("""
        UPDATE modules SET analysis_task = 'analyze_log_motor', frontend_route = 'motor_analysis'
        WHERE name = 'motor_analysis'
    """)
    op.execute("""
        UPDATE modules SET analysis_task = NULL, frontend_route = 'tune_score'
        WHERE name = 'tune_score'
    """)

    # Seed future module stubs (disabled by default)
    op.execute("""
        INSERT INTO modules (name, display_name, description, enabled, module_type, analysis_task, frontend_route, config_json, created_at)
        VALUES
        ('video', 'DVR Video', 'Attach DVR footage to a flight log', false, 'storage', NULL, 'video', '{}', NOW()),
        ('betaflight_backup', 'Betaflight Backup', 'Store and diff Betaflight CLI dumps per drone', false, 'utility', NULL, 'betaflight_backup', '{}', NOW()),
        ('gps_track', 'GPS Track', 'GPX map view for GPS-equipped quads', false, 'utility', NULL, 'gps_track', '{}', NOW())
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    """Remove plugin architecture columns and future module stubs."""
    op.execute(
        "DELETE FROM modules WHERE name IN ('video', 'betaflight_backup', 'gps_track')"
    )
    op.drop_column("modules", "frontend_route")
    op.drop_column("modules", "analysis_task")
