"""Add flight_summary operational analysis module.

Revision ID: 007_add_flight_summary
Revises: 006_add_gyro_spectrogram
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa

revision = "007_add_flight_summary"
down_revision = "006_add_gyro_spectrogram"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO modules (name, display_name, description, enabled, module_type, analysis_task, frontend_route, config_json, created_at)
        VALUES (
            'flight_summary',
            'Flight Summary',
            'Integrated flight operational insights: battery sag, current draw, GPS speed/altitude profile, throttle zones',
            true,
            'analysis',
            'analyze_log_flight_summary',
            'flight_summary',
            '{}',
            NOW()
        )
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM modules WHERE name = 'flight_summary'")
