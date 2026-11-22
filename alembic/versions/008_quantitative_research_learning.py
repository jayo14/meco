"""quantitative research learning and backtesting schema

Revision ID: 008_quantitative_research_learning
Revises: 007_autonomous_paper_trading
Create Date: 2026-11-22 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '008_quantitative_research_learning'
down_revision: str | None = '007_autonomous_paper_trading'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. research_datasets
    op.create_table(
        'research_datasets',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('feature_columns', sa.JSON(), nullable=False),
        sa.Column('time_window_start', sa.String(length=64), nullable=False),
        sa.Column('time_window_end', sa.String(length=64), nullable=False),
        sa.Column('sha256_hash', sa.String(length=64), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_research_datasets_sha256', 'research_datasets', ['sha256_hash'], unique=False)

    # 2. model_artifacts
    op.create_table(
        'model_artifacts',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('model_family', sa.String(length=64), nullable=False),
        sa.Column('hyperparameters', sa.JSON(), nullable=False),
        sa.Column('feature_columns', sa.JSON(), nullable=False),
        sa.Column('trained_dataset_hash', sa.String(length=64), nullable=False),
        sa.Column('in_sample_metrics', sa.JSON(), nullable=False),
        sa.Column('out_of_sample_metrics', sa.JSON(), nullable=False),
        sa.Column('is_champion', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # 3. strategy_versions
    op.create_table(
        'strategy_versions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('associated_model_id', sa.String(length=64), nullable=True),
        sa.Column('associated_model_version', sa.String(length=32), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_locked', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # 4. research_experiments
    op.create_table(
        'research_experiments',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('experiment_name', sa.String(length=128), nullable=False),
        sa.Column('hypothesis', sa.Text(), nullable=False),
        sa.Column('dataset_manifest_hash', sa.String(length=64), nullable=True),
        sa.Column('strategy_key', sa.String(length=64), nullable=True),
        sa.Column('model_key', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='configured'),
        sa.Column('in_sample_report', sa.JSON(), nullable=True),
        sa.Column('out_of_sample_report', sa.JSON(), nullable=True),
        sa.Column('backtest_report', sa.JSON(), nullable=True),
        sa.Column('execution_notes', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # 5. promotion_audit_records
    op.create_table(
        'promotion_audit_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('candidate_id', sa.String(length=64), nullable=False),
        sa.Column('candidate_version', sa.String(length=32), nullable=False),
        sa.Column('prior_champion_id', sa.String(length=64), nullable=True),
        sa.Column('prior_champion_version', sa.String(length=32), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('approval_reason', sa.Text(), nullable=False),
        sa.Column('approved_by', sa.String(length=64), nullable=False),
        sa.Column('evaluation_summary', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('promotion_audit_records')
    op.drop_table('research_experiments')
    op.drop_table('strategy_versions')
    op.drop_table('model_artifacts')
    op.drop_table('research_datasets')
