const WS_BASE = import.meta.env.VITE_WS_URL || "ws://localhost:8000";

export function connectPriceWebSocket(onMessage: (data: Record<string, unknown>) => void): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/prices`);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);
  };
  ws.onclose = () => {
    setTimeout(() => connectPriceWebSocket(onMessage), 5000);
  };
  return ws;
}
