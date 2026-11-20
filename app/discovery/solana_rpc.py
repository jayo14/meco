import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import websockets
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.signature import Signature

from app.config.settings import get_settings
from app.discovery.base import BaseDiscoveryAdapter
from app.discovery.models import (
    NormalizedDiscoveryEvent,
    SourceCapabilities,
)
from app.identity.registry import is_valid_solana_address
from app.research.onchain import PUMP_PROGRAM_ID
from app.solana.detector import parse_pump_instruction_logs

logger = logging.getLogger("meco.discovery.solana_rpc")

# Regex pattern to match Solana Base58 public keys in log lines
MINT_IN_LOG_PATTERN = re.compile(
    r"(?:mint|token|mint_address|target)[:\s]+([1-9A-HJ-NP-Za-km-z]{32,44})",
    re.IGNORECASE,
)
PUMP_SUFFIX_PATTERN = re.compile(
    r"\b([1-9A-HJ-NP-Za-km-z]{32,40}pump)\b",
    re.IGNORECASE,
)


def extract_mint_from_logs(logs: list[str]) -> str | None:
    """
    Extract a candidate mint address directly from Solana transaction logs.
    Handles explicit labels (e.g. 'mint: <pubkey>') and Pump.fun vanity mints.
    """
    for line in logs:
        # Check for explicit label
        match = MINT_IN_LOG_PATTERN.search(line)
        if match:
            candidate = match.group(1)
            if is_valid_solana_address(candidate) and candidate != str(PUMP_PROGRAM_ID):
                return candidate

        # Check for pump-suffix vanity mints
        pump_match = PUMP_SUFFIX_PATTERN.search(line)
        if pump_match:
            candidate = pump_match.group(1)
            if is_valid_solana_address(candidate) and candidate != str(PUMP_PROGRAM_ID):
                return candidate

    return None


def parse_solana_logs_notification(
    data: dict[str, Any],
    commitment: str = "confirmed",
    received_at: datetime | None = None,
) -> NormalizedDiscoveryEvent | None:
    """
    Parse a Solana RPC `logsNotification` JSON-RPC message.
    Extracts token creation events from program logs.
    """
    rec_time = received_at or datetime.now(timezone.utc)

    if not isinstance(data, dict):
        return None

    # Check method is logsNotification
    method = data.get("method")
    if method != "logsNotification":
        return None

    params = data.get("params", {})
    result = params.get("result", {})
    value = result.get("value", {})
    context = result.get("context", {})

    slot = context.get("slot")
    signature = value.get("signature")
    err = value.get("err")
    logs = value.get("logs") or []

    # If transaction resulted in an on-chain error, ignore it
    if err is not None:
        return None

    # Distinguish token creation from trades or unrelated instructions
    log_analysis = parse_pump_instruction_logs(logs)
    if not log_analysis.get("is_creation"):
        return None

    # Extract candidate mint from logs
    mint = extract_mint_from_logs(logs)
    if not mint:
        # Log indicates creation, but mint address needs on-chain resolution
        return None

    return NormalizedDiscoveryEvent(
        mint_address=mint,
        source="solana_rpc",
        event_type="token_created",
        source_event_id=signature or f"slot_{slot}_{mint}",
        signature=signature,
        slot=slot,
        commitment=commitment,
        source_timestamp=None,
        received_at=rec_time,
        raw_payload=data,
        source_metadata={
            "instruction_type": "create",
            "is_pump_program": log_analysis.get("is_pump_program", True),
            "log_count": len(logs),
            "slot": slot,
            "commitment": commitment,
        },
    )


class SolanaRpcDiscoveryAdapter(BaseDiscoveryAdapter):
    """
    WebSocket discovery adapter for Solana RPC.
    Subscribes to `logsSubscribe` filtered by token creation programs.
    """

    def __init__(
        self,
        ws_url: str | None = None,
        rpc_http_url: str | None = None,
        *,
        commitment: str = "confirmed",
        program_id: Pubkey | None = None,
        heartbeat_interval: float = 30.0,
        reconnect_min_delay: float = 1.0,
        reconnect_max_delay: float = 60.0,
        fetch_tx_if_missing_mint: bool = False,
    ) -> None:
        settings = get_settings()
        url = ws_url or settings.resolved_solana_ws_url
        self.rpc_http_url = rpc_http_url or settings.solana_rpc_url
        self.commitment = commitment
        self.program_id = program_id or PUMP_PROGRAM_ID
        self.heartbeat_interval = heartbeat_interval
        self.fetch_tx_if_missing_mint = fetch_tx_if_missing_mint

        capabilities = SourceCapabilities(
            source_name="solana_rpc",
            can_stream_realtime=True,
            provides_transaction_signature=True,
            provides_slot=True,
            provides_metadata=False,
            supports_catchup_replay=False,
            supported_event_types=["token_created"],
        )
        super().__init__(
            source_name="solana_rpc",
            capabilities=capabilities,
            reconnect_min_delay=reconnect_min_delay,
            reconnect_max_delay=reconnect_max_delay,
        )
        self.ws_url = url
        self.last_observed_slot: int | None = None
        self.slot_gap_count = 0
        self._current_subscription_id: int | None = None

    async def _resolve_mint_from_transaction(
        self,
        signature: str,
    ) -> str | None:
        """Fallback: fetch transaction details via HTTP RPC to resolve mint."""
        try:
            sig = Signature.from_string(signature)
            async with AsyncClient(self.rpc_http_url) as client:
                tx_resp = await client.get_transaction(
                    sig,
                    encoding="jsonParsed",
                    max_supported_transaction_version=0,
                )
                if tx_resp.value is None or tx_resp.value.transaction is None:
                    return None

                # Look for newly created mint in postTokenBalances or accounts
                meta = tx_resp.value.transaction.meta
                if meta and meta.post_token_balances:
                    for bal in meta.post_token_balances:
                        mint = getattr(bal, "mint", None)
                        if mint and is_valid_solana_address(str(mint)):
                            return str(mint)
        except Exception as e:  # noqa: BLE001
            logger.debug("Failed on-chain transaction lookup for %s: %s", signature, e)
        return None

    async def _connect_and_listen(self) -> None:
        """Connect to Solana RPC WebSocket and listen for logs."""
        logger.info("Connecting to Solana RPC WebSocket: %s", self.ws_url)
        self._current_subscription_id = None

        async with websockets.connect(
            self.ws_url,
            ping_interval=self.heartbeat_interval,
            ping_timeout=10.0,
            close_timeout=5.0,
        ) as ws:
            self.mark_connected()

            # Subscribe to logs mentions for target program
            sub_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "logsSubscribe",
                "params": [
                    {"mentions": [str(self.program_id)]},
                    {"commitment": self.commitment},
                ],
            }
            await ws.send(json.dumps(sub_req))
            logger.info(
                "Subscribed to Solana logsSubscribe for program %s (commitment=%s)",
                self.program_id,
                self.commitment,
            )

            async for message in ws:
                if not self._running:
                    break

                received_at = datetime.now(timezone.utc)
                try:
                    data = json.loads(message)
                except (json.JSONDecodeError, ValueError):
                    self.health.invalid_events += 1
                    continue

                # Handle subscription confirmation response
                if "result" in data and "id" in data and data.get("id") == 1:
                    self._current_subscription_id = data.get("result")
                    logger.info(
                        "Solana RPC subscription confirmed. Subscription ID: %s",
                        self._current_subscription_id,
                    )
                    continue

                event = parse_solana_logs_notification(
                    data,
                    commitment=self.commitment,
                    received_at=received_at,
                )

                # Track slot gaps
                if isinstance(data, dict):
                    params = data.get("params", {})
                    result = params.get("result", {})
                    context = result.get("context", {})
                    current_slot = context.get("slot")
                    if current_slot is not None:
                        if self.last_observed_slot is not None:
                            gap = current_slot - self.last_observed_slot
                            if gap > 100:  # significant gap
                                self.slot_gap_count += 1
                                logger.warning(
                                    "Detected slot gap on Solana RPC stream: %s -> %s (gap: %s slots)",
                                    self.last_observed_slot,
                                    current_slot,
                                    gap,
                                )
                        self.last_observed_slot = current_slot

                if event is not None:
                    await self.emit_event(event)
                elif self.fetch_tx_if_missing_mint and isinstance(data, dict):
                    # Check if it was a creation instruction where mint wasn't in logs
                    params = data.get("params", {})
                    result = params.get("result", {})
                    value = result.get("value", {})
                    logs = value.get("logs") or []
                    sig = value.get("signature")
                    analysis = parse_pump_instruction_logs(logs)

                    if analysis.get("is_creation") and sig:
                        mint = await self._resolve_mint_from_transaction(sig)
                        if mint and is_valid_solana_address(mint):
                            resolved_event = NormalizedDiscoveryEvent(
                                mint_address=mint,
                                source="solana_rpc",
                                event_type="token_created",
                                source_event_id=sig,
                                signature=sig,
                                slot=context.get("slot"),
                                commitment=self.commitment,
                                source_timestamp=None,
                                received_at=received_at,
                                raw_payload=data,
                                source_metadata={
                                    "instruction_type": "create",
                                    "resolved_via_tx_lookup": True,
                                    "slot": context.get("slot"),
                                },
                            )
                            await self.emit_event(resolved_event)

        self.mark_disconnected()
