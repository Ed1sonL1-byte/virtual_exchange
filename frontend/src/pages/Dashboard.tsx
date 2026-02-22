import { useEffect, useState } from "react";
import { priceApi, accountApi } from "../services/api";
import { connectPriceWebSocket } from "../services/websocket";

interface BalanceData {
  currency: string;
  available: string;
  locked: string;
}

export default function Dashboard() {
  const [prices, setPrices] = useState<Record<string, string>>({});
  const [balances, setBalances] = useState<BalanceData[]>([]);

  useEffect(() => {
    priceApi.getPrices().then(({ data }) => setPrices(data));
    accountApi.getBalance().then(({ data }) => setBalances(data));

    const ws = connectPriceWebSocket((msg) => {
      if ((msg as { type: string }).type === "price_update") {
        setPrices((msg as { data: Record<string, string> }).data);
      }
    });
    return () => ws.close();
  }, []);

  return (
    <div style={{ padding: 20 }}>
      <h2>Market Prices</h2>
      <table>
        <thead><tr><th>Pair</th><th>Price (USDT)</th></tr></thead>
        <tbody>
          {Object.entries(prices).map(([pair, price]) => (
            <tr key={pair}><td>{pair}</td><td>{price}</td></tr>
          ))}
        </tbody>
      </table>
      <h2>Balances</h2>
      <table>
        <thead><tr><th>Currency</th><th>Available</th><th>Locked</th></tr></thead>
        <tbody>
          {balances.map((b) => (
            <tr key={b.currency}><td>{b.currency}</td><td>{b.available}</td><td>{b.locked}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
