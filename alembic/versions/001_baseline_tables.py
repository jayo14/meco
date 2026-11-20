"""baseline tables

Revision ID: 001_baseline
Revises: 
Create Date: 2026-11-20 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'signals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('message_created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('market_status', sa.String(length=32), nullable=True),
        sa.Column('validation_status', sa.String(length=32), nullable=True),
        sa.Column('source_name', sa.String(length=255), nullable=True),
        sa.Column('source_username', sa.String(length=255), nullable=True),
        sa.Column('token_address', sa.String(length=64), nullable=False),
        sa.Column('slippage', sa.Float(), nullable=True),
        sa.Column('decimals', sa.Integer(), nullable=True),
        sa.Column('supply', sa.BigInteger(), nullable=True),
        sa.Column('pair_address', sa.String(length=128), nullable=True),
        sa.Column('dex_id', sa.String(length=64), nullable=True),
        sa.Column('price_usd', sa.Float(), nullable=True),
        sa.Column('liquidity_usd', sa.Float(), nullable=True),
        sa.Column('volume_5m', sa.Float(), nullable=True),
        sa.Column('volume_1h', sa.Float(), nullable=True),
        sa.Column('volume_24h', sa.Float(), nullable=True),
        sa.Column('buys_5m', sa.Integer(), nullable=True),
        sa.Column('sells_5m', sa.Integer(), nullable=True),
        sa.Column('price_change_5m', sa.Float(), nullable=True),
        sa.Column('price_change_1h', sa.Float(), nullable=True),
        sa.Column('price_change_24h', sa.Float(), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('fdv', sa.Float(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_signals_chat_id'), 'signals', ['chat_id'], unique=False)
    op.create_index(op.f('ix_signals_market_status'), 'signals', ['market_status'], unique=False)
    op.create_index(op.f('ix_signals_message_created_at'), 'signals', ['message_created_at'], unique=False)
    op.create_index(op.f('ix_signals_received_at'), 'signals', ['received_at'], unique=False)
    op.create_index(op.f('ix_signals_token_address'), 'signals', ['token_address'], unique=False)
    op.create_index(op.f('ix_signals_validation_status'), 'signals', ['validation_status'], unique=False)

    op.create_table(
        'market_observations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('signal_id', sa.Integer(), nullable=False),
        sa.Column('token_address', sa.String(length=64), nullable=False),
        sa.Column('pair_address', sa.String(length=128), nullable=True),
        sa.Column('dex_id', sa.String(length=64), nullable=True),
        sa.Column('observation_status', sa.String(length=32), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('target_seconds', sa.Integer(), nullable=False),
        sa.Column('seconds_since_signal', sa.Integer(), nullable=False),
        sa.Column('price_usd', sa.Float(), nullable=True),
        sa.Column('liquidity_usd', sa.Float(), nullable=True),
        sa.Column('volume_5m', sa.Float(), nullable=True),
        sa.Column('buys_5m', sa.Integer(), nullable=True),
        sa.Column('sells_5m', sa.Integer(), nullable=True),
        sa.Column('price_change_5m', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['signal_id'], ['signals.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('signal_id', 'target_seconds', name='uq_market_observation_signal_target'),
    )
    op.create_index(op.f('ix_market_observations_observation_status'), 'market_observations', ['observation_status'], unique=False)
    op.create_index(op.f('ix_market_observations_observed_at'), 'market_observations', ['observed_at'], unique=False)
    op.create_index(op.f('ix_market_observations_signal_id'), 'market_observations', ['signal_id'], unique=False)
    op.create_index(op.f('ix_market_observations_token_address'), 'market_observations', ['token_address'], unique=False)

    op.create_table(
        'market_pair_observations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('signal_id', sa.Integer(), nullable=False),
        sa.Column('token_address', sa.String(length=64), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('target_seconds', sa.Integer(), nullable=False),
        sa.Column('seconds_since_signal', sa.Integer(), nullable=False),
        sa.Column('pair_address', sa.String(length=128), nullable=False),
        sa.Column('dex_id', sa.String(length=64), nullable=False),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('base_token_address', sa.String(length=64), nullable=True),
        sa.Column('base_token_name', sa.String(length=255), nullable=True),
        sa.Column('base_token_symbol', sa.String(length=64), nullable=True),
        sa.Column('quote_token_address', sa.String(length=64), nullable=True),
        sa.Column('quote_token_name', sa.String(length=255), nullable=True),
        sa.Column('quote_token_symbol', sa.String(length=64), nullable=True),
        sa.Column('price_native', sa.Float(), nullable=True),
        sa.Column('price_usd', sa.Float(), nullable=True),
        sa.Column('liquidity_usd', sa.Float(), nullable=True),
        sa.Column('volume_5m', sa.Float(), nullable=True),
        sa.Column('volume_1h', sa.Float(), nullable=True),
        sa.Column('volume_6h', sa.Float(), nullable=True),
        sa.Column('volume_24h', sa.Float(), nullable=True),
        sa.Column('buys_5m', sa.Integer(), nullable=True),
        sa.Column('sells_5m', sa.Integer(), nullable=True),
        sa.Column('price_change_5m', sa.Float(), nullable=True),
        sa.Column('price_change_1h', sa.Float(), nullable=True),
        sa.Column('price_change_6h', sa.Float(), nullable=True),
        sa.Column('price_change_24h', sa.Float(), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('fdv', sa.Float(), nullable=True),
        sa.Column('pair_created_at', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['signal_id'], ['signals.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_market_pair_observations_observed_at'), 'market_pair_observations', ['observed_at'], unique=False)
    op.create_index(op.f('ix_market_pair_observations_pair_address'), 'market_pair_observations', ['pair_address'], unique=False)
    op.create_index(op.f('ix_market_pair_observations_signal_id'), 'market_pair_observations', ['signal_id'], unique=False)
    op.create_index(op.f('ix_market_pair_observations_target_seconds'), 'market_pair_observations', ['target_seconds'], unique=False)
    op.create_index(op.f('ix_market_pair_observations_token_address'), 'market_pair_observations', ['token_address'], unique=False)


def downgrade() -> None:
    op.drop_table('market_pair_observations')
    op.drop_table('market_observations')
    op.drop_table('signals')
