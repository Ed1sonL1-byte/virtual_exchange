import { useState } from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import SpotTrading from "./pages/SpotTrading";
import FuturesTrading from "./pages/FuturesTrading";
import Login from "./pages/Login";

export default function App() {
  const [loggedIn, setLoggedIn] = useState(!!localStorage.getItem("token"));

  if (!loggedIn) return <Login onLogin={() => setLoggedIn(true)} />;

  return (
    <BrowserRouter>
      <nav style={{ padding: 10, borderBottom: "1px solid #ccc" }}>
        <Link to="/" style={{ marginRight: 20 }}>Dashboard</Link>
        <Link to="/spot" style={{ marginRight: 20 }}>Spot</Link>
        <Link to="/futures" style={{ marginRight: 20 }}>Futures</Link>
        <button onClick={() => { localStorage.removeItem("token"); setLoggedIn(false); }}>Logout</button>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/spot" element={<SpotTrading />} />
        <Route path="/futures" element={<FuturesTrading />} />
      </Routes>
    </BrowserRouter>
  );
}
