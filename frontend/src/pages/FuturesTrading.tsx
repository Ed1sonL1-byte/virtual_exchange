import { useState, useEffect } from "react";
import { futuresApi, priceApi } from "../services/api";

interface PositionData {
  id: string;
  pair: string;
  side: string;
  leverage: number;
  entry_price: string;
  quantity: string;
  margin: string;
  liquidation_price: string;
  unrealized_pnl: string;
}

export default function FuturesTrading() {
  const [pair, setPair] = useState("BTCUSDT");
  const [side, setSide] = useState("long");
  const [leverage, setLeverage] = useState(10);
  const [quantity, setQuantity] = useState("");
  const [positions, setPositions] = useState<PositionData[]>([]);
  const [prices, setPrices] = useState<Record<string, string>>({});

  useEffect(() => {
    futuresApi.getPositions().then(({ data }) => setPositions(data));
    priceApi.getPrices().then(({ data }) => setPrices(data));
  }, []);

  const handleOpen = async () => {
    await futuresApi.openPosition(pair, side, leverage, parseFloat(quantity));
    futuresApi.getPositions().then(({ data }) => setPositions(data));
    setQuantity("");
  };

  const handleClose = async (id: string) => {
    await futuresApi.closePosition(id);
    futuresApi.getPositions().then(({ data }) => setPositions(data));
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>Futures Trading</h2>
      <p>Current Price: {prices[pair] || "Loading..."}</p>
      <select value={pair} onChange={(e) => setPair(e.target.value)}>
        <option>BTCUSDT</option><option>ETHUSDT</option><option>SOLUSDT</option>
      </select>
      <select value={side} onChange={(e) => setSide(e.target.value)}>
        <option value="long">Long</option><option value="short">Short</option>
      </select>
      <input type="number" min={1} max={125} value={leverage} onChange={(e) => setLeverage(parseInt(e.target.value))} />
      <span>x Leverage</span>
      <input placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      <button onClick={handleOpen}>Open Position</button>

      <h3>Open Positions</h3>
      <table>
        <thead><tr><th>Pair</th><th>Side</th><th>Leverage</th><th>Entry</th><th>Qty</th><th>Margin</th><th>Liq Price</th><th>PnL</th><th></th></tr></thead>
        <tbody>
          {positions.map((p) => (
            <tr key={p.id}>
              <td>{p.pair}</td><td>{p.side}</td><td>{p.leverage}x</td><td>{p.entry_price}</td>
              <td>{p.quantity}</td><td>{p.margin}</td><td>{p.liquidation_price}</td>
              <td style={{color: parseFloat(p.unrealized_pnl) >= 0 ? "green" : "red"}}>{p.unrealized_pnl}</td>
              <td><button onClick={() => handleClose(p.id)}>Close</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
