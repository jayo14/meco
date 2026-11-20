"""Token association and disambiguation engine for social posts."""
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import SocialPost, SocialTokenAssociation, Token
from app.social.models import TokenMatchResult

logger = logging.getLogger("meco.social.matcher")

# Known high-frequency / generic / ambiguous symbols that should never be matched on symbol alone
AMBIGUOUS_SYMBOLS = {
    "SOL",
    "WSOL",
    "USDC",
    "USDT",
    "ETH",
    "BTC",
    "AI",
    "CAT",
    "DOG",
    "DOGE",
    "PEPE",
    "MEME",
    "PUMP",
    "MOON",
    "DEV",
    "SAFE",
    "FAST",
    "RAY",
    "ORCA",
}

# Minimum confidence required to persist a social-token association
MIN_ASSOCIATION_CONFIDENCE = 0.60


class TokenSocialMatcher:
    """Matches social posts to canonical tokens with strict disambiguation."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _normalize_name_for_matching(name: str) -> str:
        """Strip emojis, punctuation, and normalize spaces."""
        clean = re.sub(r"[^\w\s]", "", name.lower())
        return " ".join(clean.split())

    async def match_post(
        self,
        session: AsyncSession,
        post: SocialPost,
    ) -> list[TokenMatchResult]:
        """Match a social post to canonical tokens.

        Returns a list of TokenMatchResult with calculated confidence and evidence.
        """
        matches: list[TokenMatchResult] = []
        matched_token_ids: set[int] = set()

        # 1. Exact Solana Mint Address Match (Highest Confidence: 0.98)
        referenced_mints = post.referenced_mints or []
        for mint in referenced_mints:
            stmt = select(Token).where(Token.mint_address == mint)
            token = (await session.execute(stmt)).scalar_one_or_none()
            if token and token.id not in matched_token_ids:
                matches.append(
                    TokenMatchResult(
                        token_id=token.id,
                        mint_address=token.mint_address,
                        match_type="mint_address",
                        confidence=0.98,
                        evidence={
                            "matched_mint": mint,
                            "symbol": token.symbol,
                            "name": token.name,
                            "post_source": post.source,
                        },
                    )
                )
                matched_token_ids.add(token.id)

        # 2. Cashtag Symbol Match with Strict Disambiguation
        referenced_symbols = post.referenced_symbols or []
        post_text_normalized = post.sanitized_content.lower()

        for symbol in referenced_symbols:
            symbol_upper = symbol.upper()
            # Query active tokens matching this symbol
            stmt = select(Token).where(Token.symbol.ilike(symbol_upper))
            candidate_tokens = (await session.execute(stmt)).scalars().all()

            if not candidate_tokens:
                continue

            for token in candidate_tokens:
                if token.id in matched_token_ids:
                    continue

                is_ambiguous = symbol_upper in AMBIGUOUS_SYMBOLS or len(candidate_tokens) > 1

                # Check for corroborating context in post text
                token_name_norm = self._normalize_name_for_matching(token.name or "") if token.name else ""
                name_in_post = bool(token_name_norm and len(token_name_norm) >= 3 and token_name_norm in post_text_normalized)

                # Check if mint address prefix appears in post
                mint_prefix = token.mint_address[:8].lower()
                mint_ref = mint_prefix in post_text_normalized

                confidence = 0.0
                match_type = "cashtag_symbol"
                evidence: dict[str, Any] = {
                    "matched_symbol": symbol_upper,
                    "token_id": token.id,
                    "mint_address": token.mint_address,
                    "name_in_post": name_in_post,
                    "is_ambiguous_symbol": is_ambiguous,
                    "candidate_count": len(candidate_tokens),
                }

                if mint_ref:
                    confidence = 0.92
                    evidence["corroboration"] = "mint_prefix_found"
                elif name_in_post and not is_ambiguous:
                    confidence = 0.85
                    evidence["corroboration"] = "name_and_unique_symbol"
                elif name_in_post and is_ambiguous:
                    confidence = 0.70
                    evidence["corroboration"] = "name_corroborated_ambiguous_symbol"
                elif not is_ambiguous and len(symbol_upper) >= 4:
                    confidence = 0.72
                    evidence["corroboration"] = "unique_distinct_symbol"
                else:
                    # Ambiguous symbol with no corroboration -> Low confidence (<0.50), do not associate
                    confidence = 0.30
                    evidence["corroboration"] = "unsupported_ambiguous_symbol"

                if confidence >= MIN_ASSOCIATION_CONFIDENCE:
                    matches.append(
                        TokenMatchResult(
                            token_id=token.id,
                            mint_address=token.mint_address,
                            match_type=match_type,
                            confidence=confidence,
                            evidence=evidence,
                        )
                    )
                    matched_token_ids.add(token.id)
                else:
                    logger.debug(
                        "Rejected ambiguous match for post #%s and token #%s ($%s, conf=%.2f)",
                        post.id,
                        token.id,
                        symbol_upper,
                        confidence,
                    )

        return matches

    async def associate_post(
        self,
        session: AsyncSession,
        post: SocialPost,
    ) -> list[SocialTokenAssociation]:
        """Find matches and persist SocialTokenAssociation records."""
        matches = await self.match_post(session, post)
        associations: list[SocialTokenAssociation] = []

        for m in matches:
            # Check existing association
            stmt = select(SocialTokenAssociation).where(
                SocialTokenAssociation.social_post_id == post.id,
                SocialTokenAssociation.token_id == m.token_id,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                # Update confidence if higher
                if m.confidence > existing.confidence:
                    existing.confidence = m.confidence
                    existing.match_evidence = m.evidence
                    await session.flush()
                associations.append(existing)
            else:
                assoc = SocialTokenAssociation(
                    social_post_id=post.id,
                    token_id=m.token_id,
                    match_type=m.match_type,
                    confidence=m.confidence,
                    match_evidence=m.evidence,
                )
                session.add(assoc)
                await session.flush()
                associations.append(assoc)

        return associations
