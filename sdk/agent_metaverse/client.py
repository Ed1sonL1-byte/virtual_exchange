import httpx


class AgentMetaverseClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(base_url=self.base_url, headers={"X-API-Key": api_key} if api_key else {})

    @classmethod
    def register(cls, base_url: str, name: str, description: str = "") -> "AgentMetaverseClient":
        resp = httpx.post(f"{base_url}/api/sdk/agents/register", json={"name": name, "description": description})
        resp.raise_for_status()
        data = resp.json()
        return cls(base_url=base_url, api_key=data["api_key"])

    def get_prices(self) -> dict:
        return self._client.get("/api/prices").json()

    def get_balance(self) -> list:
        return self._client.get("/api/account/balance").json()

    def buy_spot(self, pair: str, quantity: float) -> dict:
        return self._client.post("/api/spot/order", json={"pair": pair, "side": "buy", "order_type": "market", "quantity": quantity}).json()

    def sell_spot(self, pair: str, quantity: float) -> dict:
        return self._client.post("/api/spot/order", json={"pair": pair, "side": "sell", "order_type": "market", "quantity": quantity}).json()

    def open_position(self, pair: str, side: str, leverage: int, quantity: float) -> dict:
        return self._client.post("/api/futures/open", json={"pair": pair, "side": side, "leverage": leverage, "quantity": quantity}).json()

    def close_position(self, position_id: str) -> dict:
        return self._client.post(f"/api/futures/close/{position_id}").json()

    def get_positions(self) -> list:
        return self._client.get("/api/futures/positions").json()

    def swap(self, pair: str, side: str, amount: float) -> dict:
        return self._client.post("/api/amm/swap", json={"pair": pair, "side": side, "amount": amount}).json()
