"""token intelligence and enrichment schema

Revision ID: 003_token_intelligence
Revises: 002_discovery
Create Date: 2026-11-20 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_token_intelligence'
down_revision: Union[str, None] = '002_discovery'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add lifecycle_state and enrichment columns to tokens
    op.add_column('tokens', sa.Column('lifecycle_state', sa.String(length=32), nullable=False, server_default='discovered'))
    op.add_column('tokens', sa.Column('risk_score', sa.Float(), nullable=True))
    op.add_column('tokens', sa.Column('last_enriched_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_tokens_lifecycle_state'), 'tokens', ['lifecycle_state'], unique=False)

    # 2. enrichment_tasks
    op.create_table(
        'enrichment_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=False),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('task_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('lock_token', sa.String(length=64), nullable=True),
        sa.Column('lock_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_enrichment_tasks_token_id'), 'enrichment_tasks', ['token_id'], unique=False)
    op.create_index(op.f('ix_enrichment_tasks_mint_address'), 'enrichment_tasks', ['mint_address'], unique=False)
    op.create_index(op.f('ix_enrichment_tasks_task_type'), 'enrichment_tasks', ['task_type'], unique=False)
    op.create_index(op.f('ix_enrichment_tasks_status'), 'enrichment_tasks', ['status'], unique=False)
    op.create_index(op.f('ix_enrichment_tasks_scheduled_at'), 'enrichment_tasks', ['scheduled_at'], unique=False)
    op.create_index(op.f('ix_enrichment_tasks_lock_expires_at'), 'enrichment_tasks', ['lock_expires_at'], unique=False)

    # 3. token_security_profiles
    op.create_table(
        'token_security_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=False),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('token_program', sa.String(length=64), nullable=False),
        sa.Column('mint_authority', sa.String(length=64), nullable=True),
        sa.Column('is_mintable', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('freeze_authority', sa.String(length=64), nullable=True),
        sa.Column('is_freezable', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('permanent_delegate', sa.String(length=64), nullable=True),
        sa.Column('metadata_update_authority', sa.String(length=64), nullable=True),
        sa.Column('is_mutable', sa.Boolean(), nullable=True),
        sa.Column('has_transfer_fee', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('transfer_fee_basis_points', sa.Integer(), nullable=True),
        sa.Column('is_lp_burned_or_locked', sa.Boolean(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('risk_factors', sa.JSON(), nullable=True),
        sa.Column('verified_facts', sa.JSON(), nullable=True),
        sa.Column('raw_onchain_data', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_id', name='uq_security_token_id'),
    )
    op.create_index(op.f('ix_token_security_profiles_token_id'), 'token_security_profiles', ['token_id'], unique=True)
    op.create_index(op.f('ix_token_security_profiles_mint_address'), 'token_security_profiles', ['mint_address'], unique=False)

    # 4. token_metadata_records
    op.create_table(
        'token_metadata_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=False),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('symbol', sa.String(length=64), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image_uri', sa.Text(), nullable=True),
        sa.Column('metadata_uri', sa.Text(), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('telegram', sa.String(length=255), nullable=True),
        sa.Column('twitter', sa.String(length=255), nullable=True),
        sa.Column('discord', sa.String(length=255), nullable=True),
        sa.Column('launchpad', sa.String(length=64), nullable=True),
        sa.Column('is_uri_fetched', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('uri_fetch_error', sa.Text(), nullable=True),
        sa.Column('raw_offchain_metadata', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_id', name='uq_metadata_token_id'),
    )
    op.create_index(op.f('ix_token_metadata_records_token_id'), 'token_metadata_records', ['token_id'], unique=True)
    op.create_index(op.f('ix_token_metadata_records_mint_address'), 'token_metadata_records', ['mint_address'], unique=False)

    # 5. token_holder_snapshots
    op.create_table(
        'token_holder_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=False),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('total_holders_count', sa.Integer(), nullable=True),
        sa.Column('top10_concentration_pct', sa.Float(), nullable=True),
        sa.Column('top20_concentration_pct', sa.Float(), nullable=True),
        sa.Column('deployer_address', sa.String(length=64), nullable=True),
        sa.Column('deployer_holding_pct', sa.Float(), nullable=True),
        sa.Column('top_holders', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_token_holder_snapshots_token_id'), 'token_holder_snapshots', ['token_id'], unique=False)
    op.create_index(op.f('ix_token_holder_snapshots_mint_address'), 'token_holder_snapshots', ['mint_address'], unique=False)
    op.create_index(op.f('ix_token_holder_snapshots_observed_at'), 'token_holder_snapshots', ['observed_at'], unique=False)

    # 6. token_market_snapshots
    op.create_table(
        'token_market_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=False),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('primary_pair_address', sa.String(length=128), nullable=True),
        sa.Column('primary_dex_id', sa.String(length=64), nullable=True),
        sa.Column('price_usd', sa.Float(), nullable=True),
        sa.Column('liquidity_usd', sa.Float(), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('fdv', sa.Float(), nullable=True),
        sa.Column('volume_5m', sa.Float(), nullable=True),
        sa.Column('volume_1h', sa.Float(), nullable=True),
        sa.Column('volume_24h', sa.Float(), nullable=True),
        sa.Column('buys_5m', sa.Integer(), nullable=True),
        sa.Column('sells_5m', sa.Integer(), nullable=True),
        sa.Column('price_change_5m', sa.Float(), nullable=True),
        sa.Column('price_change_1h', sa.Float(), nullable=True),
        sa.Column('price_change_24h', sa.Float(), nullable=True),
        sa.Column('pairs_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('earliest_pair_created_at', sa.BigInteger(), nullable=True),
        sa.Column('pool_age_seconds', sa.Integer(), nullable=True),
        sa.Column('pairs_data', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_token_market_snapshots_token_id'), 'token_market_snapshots', ['token_id'], unique=False)
    op.create_index(op.f('ix_token_market_snapshots_mint_address'), 'token_market_snapshots', ['mint_address'], unique=False)
    op.create_index(op.f('ix_token_market_snapshots_observed_at'), 'token_market_snapshots', ['observed_at'], unique=False)

    # 7. token_lifecycle_events
    op.create_table(
        'token_lifecycle_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=False),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('from_state', sa.String(length=32), nullable=True),
        sa.Column('to_state', sa.String(length=32), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('event_metadata', sa.JSON(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_token_lifecycle_events_token_id'), 'token_lifecycle_events', ['token_id'], unique=False)
    op.create_index(op.f('ix_token_lifecycle_events_mint_address'), 'token_lifecycle_events', ['mint_address'], unique=False)
    op.create_index(op.f('ix_token_lifecycle_events_to_state'), 'token_lifecycle_events', ['to_state'], unique=False)
    op.create_index(op.f('ix_token_lifecycle_events_occurred_at'), 'token_lifecycle_events', ['occurred_at'], unique=False)


def downgrade() -> None:
    op.drop_table('token_lifecycle_events')
    op.drop_table('token_market_snapshots')
    op.drop_table('token_holder_snapshots')
    op.drop_table('token_metadata_records')
    op.drop_table('token_security_profiles')
    op.drop_table('enrichment_tasks')
    op.drop_index(op.f('ix_tokens_lifecycle_state'), table_name='tokens')
    op.drop_column('tokens', 'last_enriched_at')
    op.drop_column('tokens', 'risk_score')
    op.drop_column('tokens', 'lifecycle_state')
