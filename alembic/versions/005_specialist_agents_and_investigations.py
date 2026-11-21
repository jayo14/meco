"""specialist agents and token investigations schema

Revision ID: 005_specialist_agents_and_investigations
Revises: 004_social_intelligence
Create Date: 2026-11-21 21:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '005_specialist_agents_and_investigations'
down_revision: str | None = '004_social_intelligence'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. token_investigations
    op.create_table(
        'token_investigations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=True),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('trigger', sa.String(length=64), nullable=False, server_default='manual'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('requested_agents', sa.JSON(), nullable=True),
        sa.Column('completed_agents', sa.JSON(), nullable=True),
        sa.Column('failed_agents', sa.JSON(), nullable=True),
        sa.Column('verdict', sa.JSON(), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completion_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_token_investigations_token_id'), 'token_investigations', ['token_id'], unique=False)
    op.create_index(op.f('ix_token_investigations_mint_address'), 'token_investigations', ['mint_address'], unique=False)
    op.create_index(op.f('ix_token_investigations_trigger'), 'token_investigations', ['trigger'], unique=False)
    op.create_index(op.f('ix_token_investigations_status'), 'token_investigations', ['status'], unique=False)
    op.create_index('ix_token_investigations_mint_status', 'token_investigations', ['mint_address', 'status'], unique=False)

    # 2. agent_investigation_results
    op.create_table(
        'agent_investigation_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('agent_name', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('execution_state', sa.JSON(), nullable=True),
        sa.Column('findings', sa.JSON(), nullable=True),
        sa.Column('evidence_references', sa.JSON(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('insufficient_evidence', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('unanswered_questions', sa.JSON(), nullable=True),
        sa.Column('hard_risks', sa.JSON(), nullable=True),
        sa.Column('soft_warnings', sa.JSON(), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('model_provider', sa.String(length=64), nullable=True),
        sa.Column('model_name', sa.String(length=64), nullable=True),
        sa.Column('prompt_version', sa.String(length=32), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('execution_duration_ms', sa.Integer(), nullable=True),
        sa.Column('raw_output', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['investigation_id'], ['token_investigations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('investigation_id', 'agent_name', name='uq_investigation_agent'),
    )
    op.create_index(op.f('ix_agent_investigation_results_investigation_id'), 'agent_investigation_results', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_agent_investigation_results_agent_name'), 'agent_investigation_results', ['agent_name'], unique=False)
    op.create_index(op.f('ix_agent_investigation_results_status'), 'agent_investigation_results', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_agent_investigation_results_status'), table_name='agent_investigation_results')
    op.drop_index(op.f('ix_agent_investigation_results_agent_name'), table_name='agent_investigation_results')
    op.drop_index(op.f('ix_agent_investigation_results_investigation_id'), table_name='agent_investigation_results')
    op.drop_table('agent_investigation_results')

    op.drop_index('ix_token_investigations_mint_status', table_name='token_investigations')
    op.drop_index(op.f('ix_token_investigations_status'), table_name='token_investigations')
    op.drop_index(op.f('ix_token_investigations_trigger'), table_name='token_investigations')
    op.drop_index(op.f('ix_token_investigations_mint_address'), table_name='token_investigations')
    op.drop_index(op.f('ix_token_investigations_token_id'), table_name='token_investigations')
    op.drop_table('token_investigations')
