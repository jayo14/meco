"""discovery and canonical tokens

Revision ID: 002_discovery
Revises: 001_baseline
Create Date: 2026-11-20 15:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_discovery'
down_revision: Union[str, None] = '001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. tokens
    op.create_table(
        'tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('symbol', sa.String(length=64), nullable=True),
        sa.Column('decimals', sa.Integer(), nullable=True),
        sa.Column('total_supply', sa.BigInteger(), nullable=True),
        sa.Column('first_discovered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('first_discovery_source', sa.String(length=64), nullable=False),
        sa.Column('verification_status', sa.String(length=32), nullable=False, server_default='unverified'),
        sa.Column('metadata_uri', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tokens_mint_address'), 'tokens', ['mint_address'], unique=True)
    op.create_index(op.f('ix_tokens_first_discovered_at'), 'tokens', ['first_discovered_at'], unique=False)
    op.create_index(op.f('ix_tokens_first_discovery_source'), 'tokens', ['first_discovery_source'], unique=False)
    op.create_index(op.f('ix_tokens_verification_status'), 'tokens', ['verification_status'], unique=False)

    # 2. discovery_events
    op.create_table(
        'discovery_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=True),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False, server_default='token_created'),
        sa.Column('source_event_id', sa.String(length=255), nullable=True),
        sa.Column('signature', sa.String(length=128), nullable=True),
        sa.Column('slot', sa.BigInteger(), nullable=True),
        sa.Column('commitment', sa.String(length=32), nullable=True),
        sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_discovery_events_token_id'), 'discovery_events', ['token_id'], unique=False)
    op.create_index(op.f('ix_discovery_events_mint_address'), 'discovery_events', ['mint_address'], unique=False)
    op.create_index(op.f('ix_discovery_events_source'), 'discovery_events', ['source'], unique=False)
    op.create_index(op.f('ix_discovery_events_event_type'), 'discovery_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_discovery_events_source_event_id'), 'discovery_events', ['source_event_id'], unique=False)
    op.create_index(op.f('ix_discovery_events_signature'), 'discovery_events', ['signature'], unique=False)
    op.create_index(op.f('ix_discovery_events_source_timestamp'), 'discovery_events', ['source_timestamp'], unique=False)
    op.create_index(op.f('ix_discovery_events_received_at'), 'discovery_events', ['received_at'], unique=False)

    # 3. token_sources
    op.create_table(
        'token_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=False),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('source_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_id', 'source', name='uq_token_source'),
    )
    op.create_index(op.f('ix_token_sources_token_id'), 'token_sources', ['token_id'], unique=False)
    op.create_index(op.f('ix_token_sources_source'), 'token_sources', ['source'], unique=False)
    op.create_index(op.f('ix_token_sources_first_seen_at'), 'token_sources', ['first_seen_at'], unique=False)

    # 4. discovery_checkpoints
    op.create_table(
        'discovery_checkpoints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=False),
        sa.Column('last_signature', sa.String(length=128), nullable=True),
        sa.Column('last_slot', sa.BigInteger(), nullable=True),
        sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_discovery_checkpoints_source'), 'discovery_checkpoints', ['source'], unique=True)

    # 5. stream_health
    op.create_table(
        'stream_health',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='disconnected'),
        sa.Column('last_connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_disconnected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reconnect_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('events_received', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('valid_events', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('invalid_events', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duplicate_events', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('new_tokens_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('processing_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_processing_latency_ms', sa.Float(), nullable=True),
        sa.Column('last_source_latency_ms', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_stream_health_source'), 'stream_health', ['source'], unique=True)
    op.create_index(op.f('ix_stream_health_status'), 'stream_health', ['status'], unique=False)


def downgrade() -> None:
    op.drop_table('stream_health')
    op.drop_table('discovery_checkpoints')
    op.drop_table('token_sources')
    op.drop_table('discovery_events')
    op.drop_table('tokens')
