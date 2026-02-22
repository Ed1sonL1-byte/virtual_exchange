import { useState, useEffect } from "react";
import { spotApi, priceApi } from "../services/api";

interface OrderData {
  id: string;
  pair: string;
  side: string;
  quantity: string;
  price: string | null;
  status: string;
}

export default function SpotTrading() {
  const [pair, setPair] = useState("BTCUSDT");
  const [side, setSide] = useState("buy");
  const [quantity, setQuantity] = useState("");
  const [orders, setOrders] = useState<OrderData[]>([]);
  const [prices, setPrices] = useState<Record<string, string>>({});

  useEffect(() => {
    spotApi.getOrders().then(({ data }) => setOrders(data));
    priceApi.getPrices().then(({ data }) => setPrices(data));
  }, []);

  const handleOrder = async () => {
    await spotApi.placeOrder(pair, side, "market", parseFloat(quantity));
    spotApi.getOrders().then(({ data }) => setOrders(data));
    setQuantity("");
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>Spot Trading</h2>
      <p>Current Price: {prices[pair] || "Loading..."}</p>
      <select value={pair} onChange={(e) => setPair(e.target.value)}>
        <option>BTCUSDT</option><option>ETHUSDT</option><option>SOLUSDT</option>
      </select>
      <select value={side} onChange={(e) => setSide(e.target.value)}>
        <option value="buy">Buy</option><option value="sell">Sell</option>
      </select>
      <input placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      <button onClick={handleOrder}>Place Order</button>

      <h3>Orders</h3>
      <table>
        <thead><tr><th>Pair</th><th>Side</th><th>Qty</th><th>Price</th><th>Status</th></tr></thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id}><td>{o.pair}</td><td>{o.side}</td><td>{o.quantity}</td><td>{o.price}</td><td>{o.status}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
