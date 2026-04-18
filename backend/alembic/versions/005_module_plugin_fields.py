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
    """
    Add nullable plugin-related columns to the `modules` table, backfill values for existing modules, and insert disabled placeholder rows for future modules.
    
    Adds `analysis_task` and `frontend_route` (both VARCHAR(255), nullable) to the `modules` table. Backfills those fields for existing modules:
    - step_response -> analysis_task='analyze_log_step_response', frontend_route='step_response'
    - fft_noise -> analysis_task='analyze_log_fft', frontend_route='fft_noise'
    - pid_error -> analysis_task='analyze_log_pid_error', frontend_route='pid_error'
    - motor_analysis -> analysis_task='analyze_log_motor', frontend_route='motor_analysis'
    - tune_score -> analysis_task=NULL, frontend_route='tune_score'
    
    Inserts disabled placeholder modules if they do not already exist: `video`, `betaflight_backup`, and `gps_track` (each with `enabled=false`, `analysis_task=NULL`, `config_json='{}'`, and `created_at` set to the current time).
    """
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
    """
    Remove seeded future module rows and drop plugin-related columns from the modules table.
    
    Deletes rows from `modules` with names 'video', 'betaflight_backup', and 'gps_track', then drops the `frontend_route` and `analysis_task` columns.
    """
    op.execute(
        "DELETE FROM modules WHERE name IN ('video', 'betaflight_backup', 'gps_track')"
    )
    op.drop_column("modules", "frontend_route")
    op.drop_column("modules", "analysis_task")
