import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any

import websockets

from app.config.settings import get_settings
from app.discovery.base import BaseDiscoveryAdapter
from app.discovery.models import (
    NormalizedDiscoveryEvent,
    SourceCapabilities,
)

logger = logging.getLogger("meco.discovery.pumpportal")


def parse_pumpportal_message(
    raw_message: str | bytes | dict[str, Any],
    received_at: datetime | None = None,
) -> NormalizedDiscoveryEvent | None:
    """
    Parse a message from the PumpPortal WebSocket feed.
    Extracts token creation events (`subscribeNewToken`).
    Returns NormalizedDiscoveryEvent or None if unparseable / unrelated.
    """
    rec_time = received_at or datetime.now(timezone.utc)

    if isinstance(raw_message, (str, bytes)):
        try:
            payload = json.loads(raw_message)
        except Exception:
            return None
    elif isinstance(raw_message, dict):
        payload = raw_message
    else:
        return None

    if not isinstance(payload, dict):
        return None

    # Check for confirmation / status messages like {"message": "Successfully subscribed..."}
    if "message" in payload and "mint" not in payload:
        return None

    mint = payload.get("mint")
    if not mint or not isinstance(mint, str):
        return None

    signature = payload.get("signature")
    if signature is not None and not isinstance(signature, str):
        signature = str(signature)

    # Provider timestamp if available in seconds or ms
    source_ts = None
    raw_ts = payload.get("timestamp") or payload.get("time") or payload.get("created_at")
    if raw_ts is not None:
        try:
            if isinstance(raw_ts, (int, float)):
                if raw_ts > 1e11:  # ms
                    source_ts = datetime.fromtimestamp(raw_ts / 1000.0, tz=timezone.utc)
                else:  # seconds
                    source_ts = datetime.fromtimestamp(float(raw_ts), tz=timezone.utc)
            elif isinstance(raw_ts, str):
                source_ts = datetime.fromisoformat(raw_ts)
        except Exception:
            source_ts = None

    name = payload.get("name")
    symbol = payload.get("symbol")
    uri = payload.get("uri")

    source_meta = {
        "trader_public_key": payload.get("traderPublicKey"),
        "bonding_curve_key": payload.get("bondingCurveKey"),
        "v_tokens_in_bonding_curve": payload.get("vTokensInBondingCurve"),
        "v_sol_in_bonding_curve": payload.get("vSolInBondingCurve"),
        "market_cap_sol": payload.get("marketCapSol"),
        "initial_buy": payload.get("initialBuy"),
        "tx_type": payload.get("txType", "create"),
    }

    return NormalizedDiscoveryEvent(
        mint_address=mint,
        source="pumpportal",
        event_type="token_created",
        source_event_id=signature or mint,
        signature=signature,
        slot=None,
        commitment="processed",
        source_timestamp=source_ts,
        received_at=rec_time,
        raw_payload=payload,
        name=str(name) if name is not None else None,
        symbol=str(symbol) if symbol is not None else None,
        metadata_uri=str(uri) if uri is not None else None,
        source_metadata=source_meta,
    )


class PumpPortalDiscoveryAdapter(BaseDiscoveryAdapter):
    """
    WebSocket discovery adapter for PumpPortal.
    Subscribes to `subscribeNewToken` on wss://pumpportal.fun/api/data.
    """

    def __init__(
        self,
        ws_url: str | None = None,
        *,
        heartbeat_interval: float = 30.0,
        reconnect_min_delay: float = 1.0,
        reconnect_max_delay: float = 60.0,
    ) -> None:
        settings = get_settings()
        url = ws_url or settings.pumpportal_ws_url
        capabilities = SourceCapabilities(
            source_name="pumpportal",
            can_stream_realtime=True,
            provides_transaction_signature=True,
            provides_slot=False,
            provides_metadata=True,
            supports_catchup_replay=False,
            supported_event_types=["token_created"],
        )
        super().__init__(
            source_name="pumpportal",
            capabilities=capabilities,
            reconnect_min_delay=reconnect_min_delay,
            reconnect_max_delay=reconnect_max_delay,
        )
        self.ws_url = url
        self.heartbeat_interval = heartbeat_interval
        self._subscription_sent = False

    async def _connect_and_listen(self) -> None:
        """Connect to PumpPortal WebSocket and listen for new token creations."""
        logger.info("Connecting to PumpPortal WebSocket: %s", self.ws_url)
        self._subscription_sent = False

        async with websockets.connect(
            self.ws_url,
            ping_interval=self.heartbeat_interval,
            ping_timeout=10.0,
            close_timeout=5.0,
        ) as ws:
            self.mark_connected()

            # Subscribe only once per active connection
            subscribe_payload = {"method": "subscribeNewToken"}
            await ws.send(json.dumps(subscribe_payload))
            self._subscription_sent = True
            logger.info("Subscribed to PumpPortal subscribeNewToken stream")

            async for message in ws:
                if not self._running:
                    break

                received_at = datetime.now(timezone.utc)
                try:
                    event = parse_pumpportal_message(message, received_at=received_at)
                    if event is not None:
                        await self.emit_event(event)
                except Exception as parse_err:
                    logger.warning("Error processing PumpPortal message: %s", parse_err)
                    self.health.invalid_events += 1

        self.mark_disconnected()
