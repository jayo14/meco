"""Public RSS feeds social intelligence adapter."""
import logging
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.social.base import BaseSocialAdapter
from app.social.models import RawSocialPost

logger = logging.getLogger("meco.social.rss")

DEFAULT_RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://decrypt.co/feed",
]


def _find_elem(parent: ET.Element, *tags: str) -> ET.Element | None:
    """Find first matching sub-element by tag name without evaluating element truthiness."""
    for tag in tags:
        el = parent.find(tag)
        if el is not None:
            return el
    return None


class RSSSocialAdapter(BaseSocialAdapter):
    """Adapter for permitted public crypto news RSS/Atom feeds."""

    def __init__(
        self,
        feed_urls: list[str] | None = None,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(source_name="rss")
        self.feed_urls = feed_urls or list(DEFAULT_RSS_FEEDS)
        self.timeout = timeout
        self._custom_client = client
        self._seen_urls: set[str] = set()

    async def start(self, post_handler: Callable[[RawSocialPost], Any]) -> None:
        self._running = True
        logger.info("RSS adapter started with %d feed URLs", len(self.feed_urls))

    async def stop(self) -> None:
        self._running = False
        logger.info("RSS adapter stopped")

    def _parse_pubdate(self, date_str: str | None) -> datetime:
        """Parse RFC-822 / RFC-2822 / ISO-8601 publication date to UTC."""
        if not date_str:
            return datetime.now(timezone.utc)
        try:
            dt = parsedate_to_datetime(date_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:  # noqa: BLE001
            try:
                # Fallback to ISO format
                return datetime.fromisoformat(date_str).astimezone(timezone.utc)
            except Exception:  # noqa: BLE001
                return datetime.now(timezone.utc)

    def parse_feed_xml(self, xml_content: str, feed_url: str) -> list[RawSocialPost]:
        """Parse RSS 2.0 or Atom XML content into RawSocialPost items."""
        posts: list[RawSocialPost] = []
        try:
            root = ET.fromstring(xml_content.strip())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed parsing RSS XML from %s: %s", feed_url, exc)
            return []

        # Handle RSS 2.0 (<channel><item>...)
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall("item")

        # If not RSS 2.0, try Atom (<entry>...)
        if not items:
            items = root.findall("{http://www.w3.org/2005/Atom}entry") or root.findall("entry")

        for item in items:
            title_elem = _find_elem(item, "title", "{http://www.w3.org/2005/Atom}title")
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

            link_elem = _find_elem(item, "link", "{http://www.w3.org/2005/Atom}link")
            link = ""
            if link_elem is not None:
                link = link_elem.get("href") or (link_elem.text or "").strip()

            guid_elem = _find_elem(item, "guid", "id", "{http://www.w3.org/2005/Atom}id")
            external_id = guid_elem.text.strip() if guid_elem is not None and guid_elem.text else link

            if not external_id:
                continue

            desc_elem = _find_elem(
                item,
                "description",
                "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://www.w3.org/2005/Atom}content",
            )
            desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""

            author_elem = _find_elem(
                item,
                "author",
                "{http://purl.org/dc/elements/1.1/}creator",
                "{http://www.w3.org/2005/Atom}author",
            )
            author = "rss_feed"
            if author_elem is not None:
                name_child = author_elem.find("{http://www.w3.org/2005/Atom}name")
                if name_child is not None and name_child.text:
                    author = name_child.text.strip()
                elif author_elem.text:
                    author = author_elem.text.strip()

            pub_elem = _find_elem(
                item,
                "pubDate",
                "published",
                "{http://www.w3.org/2005/Atom}published",
                "{http://www.w3.org/2005/Atom}updated",
            )
            pub_date = self._parse_pubdate(pub_elem.text.strip() if pub_elem is not None and pub_elem.text else None)

            full_content = f"{title}\n{desc}".strip()
            if not full_content:
                continue

            posts.append(
                RawSocialPost(
                    source="rss",
                    external_id=external_id,
                    author_id=author,
                    author_username=author,
                    content=full_content,
                    published_at=pub_date,
                    ingested_at=datetime.now(timezone.utc),
                    urls=[link] if link else [],
                    language="en",
                    raw_metadata={"feed_url": feed_url, "title": title, "link": link},
                )
            )

        return posts

    async def poll_once(self) -> list[RawSocialPost]:
        """Poll all configured RSS feeds sequentially."""
        if self.is_rate_limited():
            return []

        all_posts: list[RawSocialPost] = []
        client = self._custom_client or httpx.AsyncClient(timeout=self.timeout)
        should_close = self._custom_client is None

        try:
            for feed_url in self.feed_urls:
                try:
                    resp = await client.get(
                        feed_url,
                        headers={"User-Agent": "MecoNewsCollector/1.0 (+https://meco.local)"},
                    )
                    if resp.status_code == 429:
                        self.set_rate_limit(120.0)
                        break
                    if resp.status_code != 200:
                        self.record_error(f"HTTP {resp.status_code} from {feed_url}")
                        continue

                    parsed = self.parse_feed_xml(resp.text, feed_url)
                    for p in parsed:
                        if p.external_id not in self._seen_urls:
                            self._seen_urls.add(p.external_id)
                            all_posts.append(p)
                except httpx.RequestError as exc:
                    self.record_error(f"Request failed for {feed_url}: {exc}")
                except Exception as exc:  # noqa: BLE001
                    self.record_error(f"Unexpected error for {feed_url}: {exc}")

            self.record_success(count=len(all_posts))
            return all_posts
        finally:
            if should_close:
                await client.aclose()
