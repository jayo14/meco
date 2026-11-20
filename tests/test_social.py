"""Comprehensive test suite for Phase 3 Social Intelligence and Narrative Discovery."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from solders.keypair import Keypair

from app.database.models import (
    Narrative,
    SocialIntelligenceFinding,
    SocialMetricsSnapshot,
    SocialNarrativeAssociation,
    SocialPost,
    SocialTokenAssociation,
    Token,
    TokenMarketSnapshot,
)
from app.social.correlation import SocialMarketCorrelator
from app.social.extractor import (
    compute_content_hash,
    extract_cashtags,
    extract_solana_mints,
    extract_urls,
    is_probable_solana_address,
    sanitize_social_text,
)
from app.social.ingestion import SocialIngestionService
from app.social.matcher import MIN_ASSOCIATION_CONFIDENCE, TokenSocialMatcher
from app.social.metrics import (
    SocialMetricsCalculator,
    calculate_author_concentration_hhi,
    calculate_lexicon_sentiment,
    calculate_spam_score,
)
from app.social.models import RawSocialPost
from app.social.narratives import NarrativeEngine
from app.social.rss_adapter import RSSSocialAdapter
from app.social.telegram_adapter import TelegramSocialAdapter
from app.social.x_adapter import XSocialAdapter

# ==============================================================================
# In-Memory Fake Async Session for Social Subsystem
# ==============================================================================

class FakeSocialAsyncSession:
    """In-memory async session supporting social intelligence models."""

    def __init__(self, db_state: dict | None = None) -> None:
        if db_state is None:
            self.db_state = {
                "tokens": {},                        # mint -> Token
                "social_posts": {},                  # (source, external_id) -> SocialPost
                "social_token_associations": [],    # list[SocialTokenAssociation]
                "narratives": {},                    # slug -> Narrative
                "social_narrative_associations": [], # list[SocialNarrativeAssociation]
                "social_metrics": [],                # list[SocialMetricsSnapshot]
                "social_findings": [],               # list[SocialIntelligenceFinding]
                "market_snapshots": [],              # list[TokenMarketSnapshot]
            }
        else:
            self.db_state = db_state
        self._next_id = 100

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def begin(self):
        return self

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1

        if isinstance(obj, Token):
            self.db_state["tokens"][obj.mint_address] = obj
        elif isinstance(obj, SocialPost):
            self.db_state["social_posts"][(obj.source, obj.external_id)] = obj
        elif isinstance(obj, SocialTokenAssociation):
            self.db_state["social_token_associations"].append(obj)
        elif isinstance(obj, Narrative):
            self.db_state["narratives"][obj.slug] = obj
        elif isinstance(obj, SocialNarrativeAssociation):
            self.db_state["social_narrative_associations"].append(obj)
        elif isinstance(obj, SocialMetricsSnapshot):
            self.db_state["social_metrics"].append(obj)
        elif isinstance(obj, SocialIntelligenceFinding):
            self.db_state["social_findings"].append(obj)
        elif isinstance(obj, TokenMarketSnapshot):
            self.db_state["market_snapshots"].append(obj)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def execute(self, statement):
        mock_result = MagicMock()
        statement_str = str(statement).lower()
        params = {}
        try:
            compiled = statement.compile()
            params = compiled.params or {}
        except Exception:  # noqa: BLE001, S110
            pass

        # 1. Query Token by mint_address, id, or symbol
        if "from tokens" in statement_str:
            tokens = list(self.db_state["tokens"].values())
            # Check by token id in params
            for k, v in params.items():
                if "id" in k and isinstance(v, int):
                    matched = [t for t in tokens if t.id == v]
                    mock_result.scalar_one_or_none.return_value = matched[0] if matched else None
                    mock_result.scalars.return_value.all.return_value = matched
                    return mock_result
                if "mint" in k and isinstance(v, str):
                    matched = [t for t in tokens if t.mint_address == v]
                    mock_result.scalar_one_or_none.return_value = matched[0] if matched else None
                    mock_result.scalars.return_value.all.return_value = matched
                    return mock_result
                if "symbol" in k and isinstance(v, str):
                    sym_clean = v.strip("%").upper()
                    matched = [t for t in tokens if t.symbol and t.symbol.upper() == sym_clean]
                    mock_result.scalars.return_value.all.return_value = matched
                    mock_result.scalar_one_or_none.return_value = matched[0] if matched else None
                    return mock_result

            for token in tokens:
                if f"tokens.id = {token.id}" in statement_str:
                    mock_result.scalar_one_or_none.return_value = token
                    mock_result.scalars.return_value.all.return_value = [token]
                    return mock_result
                if f"tokens.mint_address = '{token.mint_address}'" in statement_str:
                    mock_result.scalar_one_or_none.return_value = token
                    mock_result.scalars.return_value.all.return_value = [token]
                    return mock_result

            mock_result.scalar_one_or_none.return_value = None
            mock_result.scalars.return_value.all.return_value = []
            return mock_result

        # 2. Query SocialPost by (source, external_id) or joins
        if "from social_posts" in statement_str:
            posts = list(self.db_state["social_posts"].values())
            # Check join with social_token_associations
            if "join social_token_associations" in statement_str:
                matched_post_ids = {
                    a.social_post_id for a in self.db_state["social_token_associations"]
                }
                filtered = [p for p in posts if p.id in matched_post_ids]
                # Filter by published_at range or cutoff if present in params
                dates = [v for v in params.values() if isinstance(v, datetime)]
                if len(dates) >= 2:
                    start_dt, end_dt = min(dates), max(dates)
                    filtered = [p for p in filtered if start_dt <= p.published_at <= end_dt]
                elif len(dates) == 1:
                    filtered = [p for p in filtered if p.published_at <= dates[0]]
                filtered.sort(key=lambda p: p.published_at)
                mock_result.scalars.return_value.all.return_value = filtered
                mock_result.scalar_one_or_none.return_value = filtered[0] if filtered else None
                return mock_result

            # Check join with social_narrative_associations
            if "join social_narrative_associations" in statement_str:
                matched_post_ids = {
                    a.social_post_id for a in self.db_state["social_narrative_associations"]
                }
                filtered = [p for p in posts if p.id in matched_post_ids]
                filtered.sort(key=lambda p: p.published_at)
                mock_result.scalars.return_value.all.return_value = filtered
                mock_result.scalar_one_or_none.return_value = filtered[0] if filtered else None
                return mock_result

            for (src, ext_id), p in self.db_state["social_posts"].items():
                if (src == params.get("source_1") and ext_id == str(params.get("external_id_1"))) or (
                    f"'{src}'" in statement_str and f"'{ext_id}'" in statement_str
                ):
                    mock_result.scalar_one_or_none.return_value = p
                    return mock_result

            mock_result.scalar_one_or_none.return_value = None
            mock_result.scalars.return_value.all.return_value = posts
            return mock_result

        # 3. Query Narrative by slug or status
        if "from narratives" in statement_str:
            narrs = list(self.db_state["narratives"].values())
            slug_val = params.get("slug_1")
            if slug_val:
                matched = [n for n in narrs if n.slug == slug_val]
                mock_result.scalar_one_or_none.return_value = matched[0] if matched else None
                return mock_result
            for n in narrs:
                if f"'{n.slug}'" in statement_str:
                    mock_result.scalar_one_or_none.return_value = n
                    return mock_result
            mock_result.scalars.return_value.all.return_value = narrs
            mock_result.scalar_one_or_none.return_value = None
            return mock_result

        # 4. Query SocialTokenAssociation
        if "from social_token_associations" in statement_str:
            assocs = self.db_state["social_token_associations"]
            mock_result.scalar_one_or_none.return_value = assocs[0] if assocs else None
            mock_result.scalars.return_value.all.return_value = assocs
            return mock_result

        # 5. Query TokenMarketSnapshot
        if "from token_market_snapshots" in statement_str:
            snaps = self.db_state["market_snapshots"]
            mock_result.scalar_one_or_none.return_value = snaps[0] if snaps else None
            mock_result.scalars.return_value.all.return_value = snaps
            return mock_result

        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        return mock_result


def create_fake_social_session_factory():
    db_state = {
        "tokens": {},
        "social_posts": {},
        "social_token_associations": [],
        "narratives": {},
        "social_narrative_associations": [],
        "social_metrics": [],
        "social_findings": [],
        "market_snapshots": [],
    }

    def factory():
        return FakeSocialAsyncSession(db_state)

    return factory, db_state


# ==============================================================================
# Unit & Integration Tests
# ==============================================================================

def test_extractor_solana_mints_and_cashtags():
    fake_mint = str(Keypair().pubkey())
    text = (
        f"Check out the new coin with CA {fake_mint}! "
        f"It is mooning $BONK69 and $SOL. Also visit https://pump.fun/coin/{fake_mint}"
    )

    mints = extract_solana_mints(text)
    assert fake_mint in mints

    cashtags = extract_cashtags(text)
    assert "BONK69" in cashtags
    assert "SOL" in cashtags

    urls = extract_urls(text)
    assert any("pump.fun" in u for u in urls)

    assert is_probable_solana_address(fake_mint) is True
    assert is_probable_solana_address("not_an_address") is False
    assert is_probable_solana_address("00000000000000000000000000000000") is False  # '0' not in Base58


def test_sanitize_social_text_and_content_hash():
    dirty_html = "<b>Huge announcement!</b>   $ALPHA is live on &amp; ready to send! <script>alert(1)</script>"
    clean = sanitize_social_text(dirty_html)
    assert "<b>" not in clean
    assert "<script>" not in clean
    assert "&amp;" not in clean
    assert "&" in clean
    assert "Huge announcement! $ALPHA is live on & ready to send! alert(1)" == clean

    # Hash should be invariant to whitespace and casing
    hash1 = compute_content_hash("Buy $PEPE now! Huge pump coming")
    hash2 = compute_content_hash("  BUY   $pepe now!  huge pump coming   ")
    assert hash1 == hash2


@pytest.mark.asyncio
async def test_social_ingestion_idempotency_and_engagement_update():
    session_factory, state = create_fake_social_session_factory()
    service = SocialIngestionService(session_factory)

    mint = str(Keypair().pubkey())
    post1 = RawSocialPost(
        source="x",
        external_id="tweet_1001",
        author_id="user_abc",
        author_username="AlphaCaller",
        content=f"Early gem found! Mint: {mint} $GEM",
        published_at=datetime.now(timezone.utc),
        ingested_at=datetime.now(timezone.utc),
        likes_count=10,
        reposts_count=2,
    )

    # First ingestion
    async with session_factory() as session, session.begin():
        res1 = await service.ingest_post(session, post1)
        assert res1 is not None
        assert res1.likes_count == 10

    # Second ingestion of the same post with updated metrics
    post2 = RawSocialPost(
        source="x",
        external_id="tweet_1001",
        author_id="user_abc",
        author_username="AlphaCaller",
        content=f"Early gem found! Mint: {mint} $GEM",
        published_at=datetime.now(timezone.utc),
        ingested_at=datetime.now(timezone.utc),
        likes_count=50,
        reposts_count=12,
    )

    async with session_factory() as session, session.begin():
        res2 = await service.ingest_post(session, post2)
        assert res2 is not None
        assert res2.id == res1.id  # Same record
        assert res2.likes_count == 50  # Updated
        assert res2.reposts_count == 12

    # Should only have 1 post in DB
    assert len(state["social_posts"]) == 1


@pytest.mark.asyncio
async def test_delayed_posts_and_out_of_order_timestamps():
    session_factory, _state = create_fake_social_session_factory()
    service = SocialIngestionService(session_factory)

    past_time = datetime.now(timezone.utc) - timedelta(hours=5)
    now_time = datetime.now(timezone.utc)

    delayed_post = RawSocialPost(
        source="telegram",
        external_id="tg_123_456",
        author_id="channel_crypto",
        author_username="CryptoChannel",
        content="Delayed news broadcast about Solana ecosystem",
        published_at=past_time,
        ingested_at=now_time,
    )

    async with session_factory() as session, session.begin():
        db_post = await service.ingest_post(session, delayed_post)
        assert db_post is not None
        assert db_post.published_at == past_time
        assert db_post.ingested_at == now_time
        assert (db_post.ingested_at - db_post.published_at).total_seconds() >= 18000


@pytest.mark.asyncio
async def test_symbol_disambiguation_ambiguous_vs_distinct():
    session_factory, state = create_fake_social_session_factory()
    matcher = TokenSocialMatcher(session_factory)

    mint1 = str(Keypair().pubkey())
    mint2 = str(Keypair().pubkey())

    # Add tokens to state
    token_sol = Token(id=1, mint_address=mint1, symbol="SOL", name="Wrapped SOL")
    token_distinct = Token(id=2, mint_address=mint2, symbol="BONK69", name="Bonk Sixty Nine")
    state["tokens"][mint1] = token_sol
    state["tokens"][mint2] = token_distinct

    # Case 1: Post mentions bare ambiguous symbol $SOL with no other corroboration
    post_ambiguous = SocialPost(
        id=10,
        source="x",
        external_id="tx_1",
        author_id="anon",
        content="I love $SOL, to the moon!",
        sanitized_content="I love $SOL, to the moon!",
        referenced_symbols=["SOL"],
        referenced_mints=[],
        published_at=datetime.now(timezone.utc),
    )

    async with session_factory() as session:
        matches = await matcher.match_post(session, post_ambiguous)
        # Should not associate ambiguous symbol without context
        assert len(matches) == 0

    # Case 2: Post mentions ambiguous symbol with token name corroboration
    post_corroborated = SocialPost(
        id=11,
        source="x",
        external_id="tx_2",
        author_id="anon",
        content="Check Wrapped SOL on dex, $SOL looking great!",
        sanitized_content="Check Wrapped SOL on dex, $SOL looking great!",
        referenced_symbols=["SOL"],
        referenced_mints=[],
        published_at=datetime.now(timezone.utc),
    )

    async with session_factory() as session:
        matches = await matcher.match_post(session, post_corroborated)
        assert len(matches) == 1
        assert matches[0].token_id == 1
        assert matches[0].confidence >= MIN_ASSOCIATION_CONFIDENCE

    # Case 3: Distinct 4+ char unique symbol $BONK69
    post_distinct = SocialPost(
        id=12,
        source="x",
        external_id="tx_3",
        author_id="anon",
        content="Ape into $BONK69 right now!",
        sanitized_content="Ape into $BONK69 right now!",
        referenced_symbols=["BONK69"],
        referenced_mints=[],
        published_at=datetime.now(timezone.utc),
    )

    async with session_factory() as session:
        matches = await matcher.match_post(session, post_distinct)
        assert len(matches) == 1
        assert matches[0].token_id == 2
        assert matches[0].confidence >= 0.70

    # Case 4: Exact mint address match
    post_mint = SocialPost(
        id=13,
        source="x",
        external_id="tx_4",
        author_id="anon",
        content=f"Contract address: {mint2}",
        sanitized_content=f"Contract address: {mint2}",
        referenced_symbols=[],
        referenced_mints=[mint2],
        published_at=datetime.now(timezone.utc),
    )

    async with session_factory() as session:
        matches = await matcher.match_post(session, post_mint)
        assert len(matches) == 1
        assert matches[0].token_id == 2
        assert matches[0].confidence == 0.98


@pytest.mark.asyncio
async def test_narrative_baseline_initialization_and_keyword_matching():
    session_factory, state = create_fake_social_session_factory()
    narrative_engine = NarrativeEngine(session_factory)

    async with session_factory() as session, session.begin():
        await narrative_engine.initialize_baseline_narratives(session)

    assert "ai_agents" in state["narratives"]
    assert "pump_graduations" in state["narratives"]
    assert "depin" in state["narratives"]

    # Post matching AI agents
    post = SocialPost(
        id=20,
        source="x",
        external_id="ai_post",
        author_id="researcher",
        content="New autonomous swarm agent powered by eliza framework terminal launch on solana",
        sanitized_content="new autonomous swarm agent powered by eliza framework terminal launch on solana",
        published_at=datetime.now(timezone.utc),
    )

    async with session_factory() as session:
        matches = await narrative_engine.match_post_narratives(session, post)
        assert any(m.slug == "ai_agents" for m in matches)
        ai_match = next(m for m in matches if m.slug == "ai_agents")
        assert ai_match.confidence >= 0.70
        assert len(ai_match.matched_keywords) >= 3


def test_emerging_ngram_detection():
    posts = [
        SocialPost(
            id=i,
            source="telegram",
            external_id=f"p_{i}",
            author_id=f"u_{i}",
            content="quantum computing meta is exploding right now",
            sanitized_content="quantum computing meta is exploding right now",
            published_at=datetime.now(timezone.utc),
        )
        for i in range(5)
    ]

    ngrams = NarrativeEngine.extract_emerging_ngrams(posts, n=2, min_freq=3)
    assert len(ngrams) > 0
    top_phrase, count = ngrams[0]
    assert "quantum computing" in top_phrase or "computing meta" in top_phrase
    assert count == 5


def test_hhi_author_concentration_and_spam_scoring():
    # Scenario A: Organic distribution - 10 different authors, 1 post each
    organic_authors = [f"author_{i}" for i in range(10)]
    organic_hhi = calculate_author_concentration_hhi(organic_authors)
    assert organic_hhi == 0.10  # 10 * (0.1)^2 = 0.10

    # Scenario B: Heavily coordinated - 1 author makes 9 out of 10 posts
    spam_authors = ["bot_master"] * 9 + ["innocent_user"]
    spam_hhi = calculate_author_concentration_hhi(spam_authors)
    assert spam_hhi >= 0.82  # (0.9)^2 + (0.1)^2 = 0.82

    # Spam scoring test
    now = datetime.now(timezone.utc)
    spam_posts = [
        SocialPost(
            id=i,
            source="x",
            external_id=f"spam_{i}",
            author_id="bot_master",
            content="BUY THIS COIN FAST 100x GUARANTEED",
            sanitized_content="buy this coin fast 100x guaranteed",
            content_hash="identical_hash_123",
            published_at=now + timedelta(seconds=i * 5),  # 5s apart rapid fire
        )
        for i in range(5)
    ]
    score = calculate_spam_score(spam_posts)
    assert score >= 0.75  # High spam burst


def test_lexicon_sentiment_analysis():
    bullish_text = "Massive alpha! This gem is an absolute moon rocket, sending hard!"
    pos, neg, _neu = calculate_lexicon_sentiment(bullish_text)
    assert pos > neg
    assert pos >= 0.40

    bearish_text = "Warning! Massive dump, dev is a scam fraud and pulled liquidity, rekt honeypot!"
    pos2, neg2, _neu2 = calculate_lexicon_sentiment(bearish_text)
    assert neg2 > pos2
    assert neg2 >= 0.40


@pytest.mark.asyncio
async def test_point_in_time_metrics_zero_lookahead():
    session_factory, state = create_fake_social_session_factory()
    calc = SocialMetricsCalculator(session_factory)

    mint = str(Keypair().pubkey())
    token = Token(id=1, mint_address=mint, symbol="TEST")
    state["tokens"][mint] = token

    t0 = datetime.now(timezone.utc) - timedelta(minutes=30)
    t_cutoff = datetime.now(timezone.utc)

    # 3 posts before t_cutoff
    for i in range(3):
        post = SocialPost(
            id=i + 1,
            source="telegram",
            external_id=f"past_{i}",
            author_id=f"user_{i}",
            content="Great project",
            sanitized_content="great project",
            published_at=t0 + timedelta(minutes=i * 5),
        )
        state["social_posts"][("telegram", f"past_{i}")] = post
        state["social_token_associations"].append(
            SocialTokenAssociation(id=i + 1, social_post_id=post.id, token_id=1, match_type="symbol", confidence=0.8)
        )

    # 1 post strictly after t_cutoff (future leakage test)
    future_post = SocialPost(
        id=99,
        source="telegram",
        external_id="future_post",
        author_id="future_user",
        content="Future info that must not leak",
        sanitized_content="future info that must not leak",
        published_at=t_cutoff + timedelta(minutes=10),
    )
    state["social_posts"][("telegram", "future_post")] = future_post
    state["social_token_associations"].append(
        SocialTokenAssociation(id=99, social_post_id=99, token_id=1, match_type="symbol", confidence=0.8)
    )

    async with session_factory() as session:
        # Calculate as of t_cutoff
        metrics = await calc.calculate_token_metrics(session, token_id=1, as_of_time=t_cutoff, window_seconds=3600)
        # Should count exactly the 3 past posts, strictly excluding the future post
        assert metrics.mention_count == 3
        assert metrics.unique_authors_count == 3


@pytest.mark.asyncio
async def test_social_market_correlation_pre_market_buzz():
    session_factory, state = create_fake_social_session_factory()
    correlator = SocialMarketCorrelator(session_factory)

    mint = str(Keypair().pubkey())
    token = Token(id=1, mint_address=mint, symbol="EARLY")
    state["tokens"][mint] = token

    now = datetime.now(timezone.utc)
    first_post_time = now - timedelta(minutes=45)
    pool_created_time = now - timedelta(minutes=15)  # Pool created 30 mins after post

    # Add post
    post = SocialPost(
        id=1,
        source="telegram",
        external_id="leak_1",
        author_id="insider",
        content="Deploying new token soon",
        sanitized_content="deploying new token soon",
        published_at=first_post_time,
    )
    state["social_posts"][("telegram", "leak_1")] = post
    state["social_token_associations"].append(
        SocialTokenAssociation(id=1, social_post_id=1, token_id=1, match_type="symbol", confidence=0.9)
    )

    # Market snapshot with earliest pool created at pool_created_time
    market_snap = TokenMarketSnapshot(
        id=1,
        token_id=1,
        earliest_pair_created_at=int(pool_created_time.timestamp() * 1000),
        liquidity_usd=50000.0,
        volume_1h=10000.0,
        price_change_1h=5.0,
        observed_at=now,
    )
    state["market_snapshots"].append(market_snap)

    async with session_factory() as session:
        findings = await correlator.evaluate_token_social_correlations(session, token_id=1, as_of_time=now)
        assert any(f.finding_type == "pre_market_buzz" for f in findings)
        buzz_finding = next(f for f in findings if f.finding_type == "pre_market_buzz")
        assert buzz_finding.confidence == 0.85
        assert buzz_finding.supporting_evidence["lead_seconds"] >= 1700


@pytest.mark.asyncio
async def test_rss_adapter_parsing_and_error_handling():
    sample_rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Crypto News</title>
        <item>
          <title>Solana DEX Volume Hits New Record</title>
          <link>https://news.example.com/solana-dex-record</link>
          <guid>news_item_12345</guid>
          <description>Solana decentralized exchanges processed over 5B in volume.</description>
          <pubDate>Thu, 20 Nov 2026 14:00:00 GMT</pubDate>
          <author>Alice Editor</author>
        </item>
      </channel>
    </rss>
    """

    adapter = RSSSocialAdapter(feed_urls=["https://test.rss/feed"])
    posts = adapter.parse_feed_xml(sample_rss_xml, "https://test.rss/feed")
    assert len(posts) == 1
    p = posts[0]
    assert p.source == "rss"
    assert p.external_id == "news_item_12345"
    assert "Solana DEX Volume" in p.content
    assert p.author_username == "Alice Editor"
    assert p.published_at.year == 2026

    # Test rate limit handling
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_client.get.return_value = mock_resp

    adapter_rl = RSSSocialAdapter(feed_urls=["https://test.rss/feed"], client=mock_client)
    res = await adapter_rl.poll_once()
    assert res == []
    assert adapter_rl.is_rate_limited() is True


@pytest.mark.asyncio
async def test_x_adapter_parsing_and_rate_limiting():
    sample_tweet = {
        "id": "1850000000000000001",
        "text": "Bullish on $SOL! Check out the pump.",
        "author_id": "999888",
        "created_at": "2026-11-20T14:30:00.000Z",
        "lang": "en",
        "public_metrics": {
            "like_count": 25,
            "retweet_count": 5,
            "reply_count": 3,
            "impression_count": 1200,
        },
        "entities": {
            "urls": [{"url": "https://t.co/xyz", "expanded_url": "https://dexscreener.com/solana"}]
        },
    }
    users_by_id = {"999888": {"username": "sol_whale"}}

    adapter = XSocialAdapter(bearer_token="fake_token")
    raw = adapter.parse_tweet_object(sample_tweet, users_by_id)
    assert raw.source == "x"
    assert raw.external_id == "1850000000000000001"
    assert raw.author_username == "sol_whale"
    assert raw.likes_count == 25
    assert raw.views_count == 1200
    assert "https://dexscreener.com/solana" in raw.urls

    # Test HTTP 429 backoff
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"x-rate-limit-reset": str(datetime.now(timezone.utc).timestamp() + 300)}
    mock_client.get.return_value = mock_resp

    adapter_rl = XSocialAdapter(bearer_token="fake_token", client=mock_client)
    tweets = await adapter_rl.poll_once()
    assert tweets == []
    assert adapter_rl.is_rate_limited() is True


def test_telegram_adapter_transformation():
    adapter = TelegramSocialAdapter()
    now = datetime.now(timezone.utc)
    raw = adapter.transform_telegram_message(
        message_id=9876,
        channel_id=100200300,
        channel_title="AlphaCallersGroup",
        text="New gem alert: $PEPE69 on pump",
        date=now,
        views=450,
        forwards=15,
    )

    assert raw.source == "telegram"
    assert raw.external_id == "tg_100200300_9876"
    assert raw.author_username == "AlphaCallersGroup"
    assert raw.views_count == 450
    assert raw.reposts_count == 15
    assert raw.published_at == now
