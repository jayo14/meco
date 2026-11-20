"""X (Twitter) official API v2 compliant search adapter."""
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import httpx

from app.social.base import BaseSocialAdapter
from app.social.models import RawSocialPost

logger = logging.getLogger("meco.social.x")

TWITTER_SEARCH_RECENT_URL = "https://api.twitter.com/2/tweets/search/recent"


class XSocialAdapter(BaseSocialAdapter):
    """Permitted X (Twitter API v2) adapter using official search endpoints.

    Adheres strictly to official API v2 specifications, rate limits, and authentication.
    Does not scrape or use unauthorized endpoints.
    """

    def __init__(
        self,
        bearer_token: str | None = None,
        search_query: str = "(solana OR $SOL) -is:retweet lang:en",
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        super().__init__(source_name="x")
        self.bearer_token = bearer_token
        self.search_query = search_query
        self.timeout = timeout
        self._custom_client = client
        self._since_id: str | None = None

    async def start(self, post_handler: Callable[[RawSocialPost], Any]) -> None:
        self._running = True
        logger.info("X (Twitter) social adapter started (query: %s)", self.search_query)

    async def stop(self) -> None:
        self._running = False
        logger.info("X (Twitter) social adapter stopped")

    def parse_tweet_object(self, tweet: dict[str, Any], users_by_id: dict[str, dict[str, Any]]) -> RawSocialPost:
        """Parse official Twitter API v2 Tweet object into RawSocialPost."""
        tweet_id = str(tweet.get("id", ""))
        text = tweet.get("text", "")
        author_id = str(tweet.get("author_id", "unknown"))

        # Look up username from includes
        author_user = users_by_id.get(author_id, {})
        username = author_user.get("username")

        # Parse created_at ISO8601
        created_at_str = tweet.get("created_at")
        pub_date = datetime.now(timezone.utc)
        if created_at_str:
            try:
                pub_date = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001, S110
                pass

        # Public metrics
        metrics = tweet.get("public_metrics", {})
        likes = metrics.get("like_count", 0)
        reposts = metrics.get("retweet_count", 0)
        replies = metrics.get("reply_count", 0)
        views = metrics.get("impression_count", 0)

        # Entities URLs
        urls: list[str] = []
        for url_obj in tweet.get("entities", {}).get("urls", []):
            expanded = url_obj.get("expanded_url") or url_obj.get("url")
            if expanded:
                urls.append(expanded)

        return RawSocialPost(
            source="x",
            external_id=tweet_id,
            author_id=author_id,
            author_username=username,
            content=text,
            published_at=pub_date,
            ingested_at=datetime.now(timezone.utc),
            likes_count=likes,
            reposts_count=reposts,
            replies_count=replies,
            views_count=views,
            urls=urls,
            language=tweet.get("lang", "en"),
            raw_metadata=tweet,
        )

    async def poll_once(self) -> list[RawSocialPost]:
        """Poll recent tweets matching the configured query."""
        if not self.bearer_token:
            logger.debug("X adapter skipped: bearer token not configured")
            return []

        if self.is_rate_limited():
            logger.debug("X adapter in rate-limit backoff period")
            return []

        params: dict[str, str] = {
            "query": self.search_query,
            "max_results": "50",
            "tweet.fields": "created_at,public_metrics,entities,lang,author_id",
            "expansions": "author_id",
            "user.fields": "username,verified",
        }
        if self._since_id:
            params["since_id"] = self._since_id

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "User-Agent": "MecoIntelligence/1.0",
        }

        client = self._custom_client or httpx.AsyncClient(timeout=self.timeout)
        should_close = self._custom_client is None

        try:
            resp = await client.get(TWITTER_SEARCH_RECENT_URL, headers=headers, params=params)

            if resp.status_code == 429:
                # Rate limit exceeded: check x-rate-limit-reset header
                reset_header = resp.headers.get("x-rate-limit-reset")
                backoff_seconds = 900.0  # default 15 minutes
                if reset_header:
                    try:
                        reset_ts = float(reset_header)
                        backoff_seconds = max(10.0, reset_ts - datetime.now(timezone.utc).timestamp())
                    except ValueError:
                        pass
                self.set_rate_limit(backoff_seconds)
                self.record_error(f"X API rate limit (429), backoff for {backoff_seconds:.0f}s")
                return []

            if resp.status_code != 200:
                self.record_error(f"X API error HTTP {resp.status_code}: {resp.text[:200]}")
                return []

            data = resp.json()
            tweets = data.get("data", [])
            includes = data.get("includes", {})
            users = includes.get("users", [])
            users_by_id = {str(u["id"]): u for u in users if "id" in u}

            posts: list[RawSocialPost] = []
            for t in tweets:
                p = self.parse_tweet_object(t, users_by_id)
                posts.append(p)

            # Update since_id to newest tweet id
            meta = data.get("meta", {})
            if meta.get("newest_id"):
                self._since_id = str(meta["newest_id"])

            self.record_success(count=len(posts))
            return posts

        except httpx.RequestError as exc:
            self.record_error(f"X API request error: {exc}")
            return []
        except Exception as exc:  # noqa: BLE001
            self.record_error(f"Unexpected X API error: {exc}")
            return []
        finally:
            if should_close:
                await client.aclose()
