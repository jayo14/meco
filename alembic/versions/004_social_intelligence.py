"""social intelligence and narrative discovery schema

Revision ID: 004_social_intelligence
Revises: 003_token_intelligence
Create Date: 2026-11-20 16:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '004_social_intelligence'
down_revision: str | None = '003_token_intelligence'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. social_posts
    op.create_table(
        'social_posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('author_id', sa.String(length=255), nullable=False),
        sa.Column('author_username', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sanitized_content', sa.Text(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('likes_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reposts_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('replies_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('views_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('referenced_mints', sa.JSON(), nullable=True),
        sa.Column('referenced_symbols', sa.JSON(), nullable=True),
        sa.Column('urls', sa.JSON(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('raw_metadata', sa.JSON(), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'external_id', name='uq_social_posts_source_ext_id'),
    )
    op.create_index(op.f('ix_social_posts_source'), 'social_posts', ['source'], unique=False)
    op.create_index(op.f('ix_social_posts_external_id'), 'social_posts', ['external_id'], unique=False)
    op.create_index(op.f('ix_social_posts_author_id'), 'social_posts', ['author_id'], unique=False)
    op.create_index(op.f('ix_social_posts_published_at'), 'social_posts', ['published_at'], unique=False)
    op.create_index(op.f('ix_social_posts_ingested_at'), 'social_posts', ['ingested_at'], unique=False)
    op.create_index(op.f('ix_social_posts_content_hash'), 'social_posts', ['content_hash'], unique=False)
    op.create_index('ix_social_posts_source_published', 'social_posts', ['source', 'published_at'], unique=False)

    # 2. narratives
    op.create_table(
        'narratives',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('slug', sa.String(length=128), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('keywords', sa.JSON(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index(op.f('ix_narratives_slug'), 'narratives', ['slug'], unique=True)
    op.create_index(op.f('ix_narratives_category'), 'narratives', ['category'], unique=False)
    op.create_index(op.f('ix_narratives_status'), 'narratives', ['status'], unique=False)

    # 3. social_token_associations
    op.create_table(
        'social_token_associations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('social_post_id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=False),
        sa.Column('match_type', sa.String(length=32), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('match_evidence', sa.JSON(), nullable=True),
        sa.Column('associated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['social_post_id'], ['social_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('social_post_id', 'token_id', name='uq_post_token_assoc'),
    )
    op.create_index(op.f('ix_social_token_associations_social_post_id'), 'social_token_associations', ['social_post_id'], unique=False)
    op.create_index(op.f('ix_social_token_associations_token_id'), 'social_token_associations', ['token_id'], unique=False)
    op.create_index(op.f('ix_social_token_associations_match_type'), 'social_token_associations', ['match_type'], unique=False)

    # 4. social_narrative_associations
    op.create_table(
        'social_narrative_associations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('social_post_id', sa.Integer(), nullable=False),
        sa.Column('narrative_id', sa.Integer(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('matched_keywords', sa.JSON(), nullable=True),
        sa.Column('associated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['social_post_id'], ['social_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['narrative_id'], ['narratives.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('social_post_id', 'narrative_id', name='uq_post_narrative_assoc'),
    )
    op.create_index(op.f('ix_social_narrative_associations_social_post_id'), 'social_narrative_associations', ['social_post_id'], unique=False)
    op.create_index(op.f('ix_social_narrative_associations_narrative_id'), 'social_narrative_associations', ['narrative_id'], unique=False)

    # 5. token_narrative_associations
    op.create_table(
        'token_narrative_associations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=False),
        sa.Column('narrative_id', sa.Integer(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('first_associated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_associated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['narrative_id'], ['narratives.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_id', 'narrative_id', name='uq_token_narrative_assoc'),
    )
    op.create_index(op.f('ix_token_narrative_associations_token_id'), 'token_narrative_associations', ['token_id'], unique=False)
    op.create_index(op.f('ix_token_narrative_associations_narrative_id'), 'token_narrative_associations', ['narrative_id'], unique=False)

    # 6. social_metrics_snapshots
    op.create_table(
        'social_metrics_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=True),
        sa.Column('narrative_id', sa.Integer(), nullable=True),
        sa.Column('window_seconds', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('snapshot_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('mention_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('mention_velocity', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('unique_authors_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('author_concentration', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_engagement', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('engagement_velocity', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('sentiment_positive', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('sentiment_negative', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('sentiment_neutral', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('spam_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['narrative_id'], ['narratives.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_social_metrics_snapshots_token_id'), 'social_metrics_snapshots', ['token_id'], unique=False)
    op.create_index(op.f('ix_social_metrics_snapshots_narrative_id'), 'social_metrics_snapshots', ['narrative_id'], unique=False)
    op.create_index(op.f('ix_social_metrics_snapshots_snapshot_time'), 'social_metrics_snapshots', ['snapshot_time'], unique=False)

    # 7. social_intelligence_findings
    op.create_table(
        'social_intelligence_findings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=True),
        sa.Column('narrative_id', sa.Integer(), nullable=True),
        sa.Column('finding_type', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('supporting_evidence', sa.JSON(), nullable=True),
        sa.Column('source_references', sa.JSON(), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['narrative_id'], ['narratives.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_social_intelligence_findings_token_id'), 'social_intelligence_findings', ['token_id'], unique=False)
    op.create_index(op.f('ix_social_intelligence_findings_narrative_id'), 'social_intelligence_findings', ['narrative_id'], unique=False)
    op.create_index(op.f('ix_social_intelligence_findings_finding_type'), 'social_intelligence_findings', ['finding_type'], unique=False)
    op.create_index(op.f('ix_social_intelligence_findings_observed_at'), 'social_intelligence_findings', ['observed_at'], unique=False)


def downgrade() -> None:
    op.drop_table('social_intelligence_findings')
    op.drop_table('social_metrics_snapshots')
    op.drop_table('token_narrative_associations')
    op.drop_table('social_narrative_associations')
    op.drop_table('social_token_associations')
    op.drop_table('narratives')
    op.drop_table('social_posts')
