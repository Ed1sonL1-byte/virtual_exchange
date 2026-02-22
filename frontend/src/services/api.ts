import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authApi = {
  register: (username: string, password: string) =>
    api.post("/api/auth/register", { username, password }),
  login: (username: string, password: string) =>
    api.post("/api/auth/login", { username, password }),
};

export const accountApi = {
  getBalance: () => api.get("/api/account/balance"),
  getPositions: () => api.get("/api/account/positions"),
};

export const priceApi = {
  getPrices: () => api.get("/api/prices"),
};

export const spotApi = {
  placeOrder: (pair: string, side: string, order_type: string, quantity: number, price?: number) =>
    api.post("/api/spot/order", { pair, side, order_type, quantity, price }),
  getOrders: () => api.get("/api/spot/orders"),
  cancelOrder: (id: string) => api.delete(`/api/spot/orders/${id}`),
};

export const futuresApi = {
  openPosition: (pair: string, side: string, leverage: number, quantity: number) =>
    api.post("/api/futures/open", { pair, side, leverage, quantity }),
  closePosition: (id: string) => api.post(`/api/futures/close/${id}`),
  getPositions: () => api.get("/api/futures/positions"),
};

export const ammApi = {
  getPools: () => api.get("/api/amm/pools"),
  swap: (pair: string, side: string, amount: number) =>
    api.post("/api/amm/swap", { pair, side, amount }),
};

export default api;
