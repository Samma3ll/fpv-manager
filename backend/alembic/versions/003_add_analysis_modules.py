"""Add analysis module registry

Revision ID: 003_add_analysis_modules
Revises: 002_drone_string_fields
Create Date: 2026-04-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_add_analysis_modules'
down_revision = '002_drone_string_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add analysis modules to registry."""
    # Use raw SQL to insert with NOW() function for created_at
    op.execute("""
        INSERT INTO modules (name, display_name, description, enabled, module_type, config_json, created_at)
        VALUES
        ('step_response', 'Step Response Analysis', 'Analyze quad response to stick inputs: rise time, overshoot, settling time, ringing', true, 'analysis', '{}', NOW()),
        ('fft_noise', 'FFT Noise Analysis', 'Frequency domain analysis: resonance peaks, noise floor, energy distribution', true, 'analysis', '{}', NOW()),
        ('pid_error', 'PID Error Tracking', 'Measure PID control error: RMS, max error, error drift, percentiles', true, 'analysis', '{}', NOW()),
        ('motor_analysis', 'Motor Output Analysis', 'Analyze motor performance: balance, imbalance, resonance, synchronization', true, 'analysis', '{}', NOW()),
        ('tune_score', 'Tune Quality Score', 'Overall PID tune quality score (0-100) based on all analyses', true, 'analysis', '{}', NOW())
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    """Remove analysis modules from registry."""
    op.execute(
        "DELETE FROM modules WHERE name IN ('step_response', 'fft_noise', 'pid_error', 'motor_analysis', 'tune_score') AND module_type = 'analysis'"
    )