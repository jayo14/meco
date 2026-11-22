"""autonomous paper trading engine schema

Revision ID: 007_autonomous_paper_trading
Revises: 006_evidence_based_decision_engine
Create Date: 2026-11-22 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '007_autonomous_paper_trading'
down_revision: str | None = '006_evidence_based_decision_engine'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. paper_positions
    op.create_table(
        'paper_positions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('proposal_id', sa.String(length=36), nullable=False),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=True),
        sa.Column('strategy_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('entry_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('capital_committed', sa.Float(), nullable=False),
        sa.Column('current_mark_price', sa.Float(), nullable=False),
        sa.Column('unrealised_pnl_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('realised_pnl_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_fees_paid_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('exit_conditions', sa.JSON(), nullable=False),
        sa.Column('peak_price', sa.Float(), nullable=False),
        sa.Column('max_favourable_excursion_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('max_adverse_excursion_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('exit_reason', sa.String(length=64), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_paper_positions_mint_address'), 'paper_positions', ['mint_address'], unique=False)
    op.create_index(op.f('ix_paper_positions_proposal_id'), 'paper_positions', ['proposal_id'], unique=False)
    op.create_index(op.f('ix_paper_positions_strategy_id'), 'paper_positions', ['strategy_id'], unique=False)
    op.create_index(op.f('ix_paper_positions_status'), 'paper_positions', ['status'], unique=False)
    op.create_index(op.f('ix_paper_positions_entry_time'), 'paper_positions', ['entry_time'], unique=False)
    op.create_index(op.f('ix_paper_positions_token_id'), 'paper_positions', ['token_id'], unique=False)

    # 2. paper_orders
    op.create_table(
        'paper_orders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('position_id', sa.String(length=36), nullable=False),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('side', sa.String(length=16), nullable=False),
        sa.Column('order_type', sa.String(length=32), nullable=False, server_default='market'),
        sa.Column('requested_size_usd', sa.Float(), nullable=False),
        sa.Column('executed_size_usd', sa.Float(), nullable=False),
        sa.Column('executed_price', sa.Float(), nullable=False),
        sa.Column('executed_quantity', sa.Float(), nullable=False),
        sa.Column('total_fees_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='completed'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['position_id'], ['paper_positions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_paper_orders_position_id'), 'paper_orders', ['position_id'], unique=False)
    op.create_index(op.f('ix_paper_orders_mint_address'), 'paper_orders', ['mint_address'], unique=False)
    op.create_index(op.f('ix_paper_orders_side'), 'paper_orders', ['side'], unique=False)

    # 3. paper_proposals
    op.create_table(
        'paper_proposals',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('mint_address', sa.String(length=64), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=True),
        sa.Column('strategy_id', sa.String(length=64), nullable=False),
        sa.Column('strategy_version', sa.String(length=32), nullable=False, server_default='1.0.0'),
        sa.Column('decision_id', sa.String(length=36), nullable=True),
        sa.Column('proposed_entry_price', sa.Float(), nullable=False),
        sa.Column('proposed_position_size_usd', sa.Float(), nullable=False),
        sa.Column('expected_slippage_pct', sa.Float(), nullable=False, server_default='1.5'),
        sa.Column('max_acceptable_price_impact_pct', sa.Float(), nullable=False, server_default='3.0'),
        sa.Column('exit_conditions', sa.JSON(), nullable=False),
        sa.Column('risk_assessment', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('proposal_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('proposal_expiration', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['decision_id'], ['token_decisions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_paper_proposals_mint_address'), 'paper_proposals', ['mint_address'], unique=False)
    op.create_index(op.f('ix_paper_proposals_token_id'), 'paper_proposals', ['token_id'], unique=False)
    op.create_index(op.f('ix_paper_proposals_strategy_id'), 'paper_proposals', ['strategy_id'], unique=False)
    op.create_index(op.f('ix_paper_proposals_status'), 'paper_proposals', ['status'], unique=False)

    # 4. portfolio_snapshots
    op.create_table(
        'portfolio_snapshots',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('starting_capital', sa.Float(), nullable=False),
        sa.Column('available_capital', sa.Float(), nullable=False),
        sa.Column('reserved_capital', sa.Float(), nullable=False),
        sa.Column('open_positions_value', sa.Float(), nullable=False),
        sa.Column('realised_pnl', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('unrealised_pnl', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_fees', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('net_equity', sa.Float(), nullable=False),
        sa.Column('peak_equity', sa.Float(), nullable=False),
        sa.Column('current_drawdown_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('open_positions_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('exposure_by_token', sa.JSON(), nullable=True),
        sa.Column('exposure_by_strategy', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_portfolio_snapshots_timestamp'), 'portfolio_snapshots', ['timestamp'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_portfolio_snapshots_timestamp'), table_name='portfolio_snapshots')
    op.drop_table('portfolio_snapshots')

    op.drop_index(op.f('ix_paper_proposals_status'), table_name='paper_proposals')
    op.drop_index(op.f('ix_paper_proposals_strategy_id'), table_name='paper_proposals')
    op.drop_index(op.f('ix_paper_proposals_token_id'), table_name='paper_proposals')
    op.drop_index(op.f('ix_paper_proposals_mint_address'), table_name='paper_proposals')
    op.drop_table('paper_proposals')

    op.drop_index(op.f('ix_paper_orders_side'), table_name='paper_orders')
    op.drop_index(op.f('ix_paper_orders_mint_address'), table_name='paper_orders')
    op.drop_index(op.f('ix_paper_orders_position_id'), table_name='paper_orders')
    op.drop_table('paper_orders')

    op.drop_index(op.f('ix_paper_positions_token_id'), table_name='paper_positions')
    op.drop_index(op.f('ix_paper_positions_entry_time'), table_name='paper_positions')
    op.drop_index(op.f('ix_paper_positions_status'), table_name='paper_positions')
    op.drop_index(op.f('ix_paper_positions_strategy_id'), table_name='paper_positions')
    op.drop_index(op.f('ix_paper_positions_proposal_id'), table_name='paper_positions')
    op.drop_index(op.f('ix_paper_positions_mint_address'), table_name='paper_positions')
    op.drop_table('paper_positions')
