from dataclasses import dataclass


@dataclass(frozen=True)
class MarketSnapshot:
    token_address: str

    pair_address: str
    dex_id: str

    price_usd: float | None
    liquidity_usd: float | None

    volume_5m: float
    volume_1h: float
    volume_24h: float

    buys_5m: int
    sells_5m: int

    price_change_5m: float | None
    price_change_1h: float | None
    price_change_24h: float | None

    market_cap: float | None
    fdv: float | None

    pair_created_at: int | None

    @property
    def total_trades_5m(self) -> int:
        return self.buys_5m + self.sells_5m

    @property
    def buy_sell_ratio_5m(self) -> float | None:
        if self.sells_5m == 0:
            return None

        return self.buys_5m / self.sells_5m
