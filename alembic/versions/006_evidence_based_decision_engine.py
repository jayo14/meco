"""evidence-based decision engine schema

Revision ID: 006_evidence_based_decision_engine
Revises: 005_specialist_agents_and_investigations
Create Date: 2026-11-22 08:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '006_evidence_based_decision_engine'
down_revision: str | None = '005_specialist_agents_and_investigations'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. token_decisions
    op.create_table(
        'token_decisions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=True),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=True),
        sa.Column('outcome', sa.String(length=64), nullable=False),
        sa.Column('reasoning_summary', sa.Text(), nullable=False),
        sa.Column('dimension_scores', sa.JSON(), nullable=False),
        sa.Column('hard_risk_violations', sa.JSON(), nullable=True),
        sa.Column('supporting_evidence', sa.JSON(), nullable=True),
        sa.Column('contradictory_evidence', sa.JSON(), nullable=True),
        sa.Column('risk_factors', sa.JSON(), nullable=True),
        sa.Column('missing_information', sa.JSON(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('decision_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expiration_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('engine_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('scoring_config_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('explanation', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['investigation_id'], ['token_investigations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_token_decisions_token_id'), 'token_decisions', ['token_id'], unique=False)
    op.create_index(op.f('ix_token_decisions_mint_address'), 'token_decisions', ['mint_address'], unique=False)
    op.create_index(op.f('ix_token_decisions_investigation_id'), 'token_decisions', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_token_decisions_outcome'), 'token_decisions', ['outcome'], unique=False)
    op.create_index(op.f('ix_token_decisions_decision_timestamp'), 'token_decisions', ['decision_timestamp'], unique=False)
    op.create_index(op.f('ix_token_decisions_expiration_time'), 'token_decisions', ['expiration_time'], unique=False)
    op.create_index(op.f('ix_token_decisions_is_active'), 'token_decisions', ['is_active'], unique=False)
    op.create_index('ix_token_decisions_mint_outcome', 'token_decisions', ['mint_address', 'outcome'], unique=False)
    op.create_index('ix_token_decisions_active_exp', 'token_decisions', ['is_active', 'expiration_time'], unique=False)

    # 2. decision_scoring_configs
    op.create_table(
        'decision_scoring_configs',
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config_hash', sa.String(length=64), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('version'),
    )
    op.create_index(op.f('ix_decision_scoring_configs_config_hash'), 'decision_scoring_configs', ['config_hash'], unique=False)

    # 3. decision_reassessments
    op.create_table(
        'decision_reassessments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('trigger_type', sa.String(length=64), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('delta_metrics', sa.JSON(), nullable=True),
        sa.Column('is_emergency', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('should_reassess', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_decision_reassessments_mint_address'), 'decision_reassessments', ['mint_address'], unique=False)
    op.create_index(op.f('ix_decision_reassessments_trigger_type'), 'decision_reassessments', ['trigger_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_decision_reassessments_trigger_type'), table_name='decision_reassessments')
    op.drop_index(op.f('ix_decision_reassessments_mint_address'), table_name='decision_reassessments')
    op.drop_table('decision_reassessments')

    op.drop_index(op.f('ix_decision_scoring_configs_config_hash'), table_name='decision_scoring_configs')
    op.drop_table('decision_scoring_configs')

    op.drop_index('ix_token_decisions_active_exp', table_name='token_decisions')
    op.drop_index('ix_token_decisions_mint_outcome', table_name='token_decisions')
    op.drop_index(op.f('ix_token_decisions_is_active'), table_name='token_decisions')
    op.drop_index(op.f('ix_token_decisions_expiration_time'), table_name='token_decisions')
    op.drop_index(op.f('ix_token_decisions_decision_timestamp'), table_name='token_decisions')
    op.drop_index(op.f('ix_token_decisions_outcome'), table_name='token_decisions')
    op.drop_index(op.f('ix_token_decisions_investigation_id'), table_name='token_decisions')
    op.drop_index(op.f('ix_token_decisions_mint_address'), table_name='token_decisions')
    op.drop_index(op.f('ix_token_decisions_token_id'), table_name='token_decisions')
    op.drop_table('token_decisions')
