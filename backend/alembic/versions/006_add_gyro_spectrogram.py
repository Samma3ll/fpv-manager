"""Add gyro_spectrogram analysis module.

Revision ID: 006_add_gyro_spectrogram
Revises: 005_module_plugin_fields
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa

revision = "006_add_gyro_spectrogram"
down_revision = "005_module_plugin_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Register the 'gyro_spectrogram' analysis module in the database.
    
    Inserts a row into the `modules` table describing the Gyro Spectrogram analysis (name `gyro_spectrogram`, display name `Gyro Spectrogram`, description, enabled flag `true`, module_type `analysis`, analysis_task `analyze_log_gyro_spectrogram`, frontend_route `gyro_spectrogram`, and empty `config_json`). If a module with the same name already exists, no changes are made.
    """
    op.execute("""
        INSERT INTO modules (name, display_name, description, enabled, module_type, analysis_task, frontend_route, config_json, created_at)
        VALUES (
            'gyro_spectrogram',
            'Gyro Spectrogram',
            'Time-frequency spectrogram and heatmap for gyroscope data with filtered/unfiltered toggle',
            true,
            'analysis',
            'analyze_log_gyro_spectrogram',
            'gyro_spectrogram',
            '{}',
            NOW()
        )
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    """
    Remove the 'gyro_spectrogram' module entry from the modules table.
    
    Executes a SQL DELETE that removes any rows in the `modules` table where `name = 'gyro_spectrogram'`.
    """
    op.execute("DELETE FROM modules WHERE name = 'gyro_spectrogram'")
