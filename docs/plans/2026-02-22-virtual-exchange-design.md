# Agent Metaverse - Virtual Exchange Design Document

**Date**: 2026-02-22
**Status**: Approved

## 1. Overview

A virtual trading exchange for the AI Town project that enables both AI Agents and human users to trade crypto assets. The exchange supports spot trading, perpetual futures contracts, and AMM-based liquidity provision.

### Key Features
- **3 Trading Pairs**: ETHUSDT, SOLUSDT, BTCUSDT (prices from Binance API)
- **Price Broadcast**: Every 2 minutes via WebSocket
- **Spot Trading**: Market and limit orders
- **Perpetual Futures**: 1x-125x leverage, long/short, liquidation engine
- **AMM (Uniswap V2)**: Market Makers mint tokens and provide liquidity via x*y=k model
- **Agent Integration**: REST API, Python SDK, MCP Skill

## 2. Architecture

### 2.1 Architecture Decision: Monolithic Service

Single FastAPI application containing all modules. Chosen for:
- Fast development and simple deployment
- No network latency for internal calls
- Single database transaction consistency
- Sufficient for virtual exchange scale

### 2.2 System Diagram

```
┌─────────────────────────────────────────────────────┐
│                    Clients                          │
│  ┌──────────────┐  ┌───────────────────────────┐    │
│  │  React Web UI │  │  AI Agent (HTTP/WebSocket)│    │
│  └──────┬───────┘  └─────────┬─────────────────┘    │
└─────────┼────────────────────┼──────────────────────┘
          │                    │
          ▼                    ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Application                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ Price    │ │ Spot     │ │ Futures  │ │  AMM   │ │
│  │ Engine   │ │ Trading  │ │ Trading  │ │ Engine │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Account  │ │ Position │ │WebSocket │            │
│  │ Manager  │ │ Manager  │ │Broadcast │            │
│  └──────────┘ └──────────┘ └──────────┘            │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │  PostgreSQL  │
              └──────────────┘
```

### 2.3 Tech Stack
- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy / Alembic
- **Database**: PostgreSQL
- **Frontend**: React / TypeScript / Vite
- **Real-time**: WebSocket (FastAPI built-in)
- **External Data**: Binance REST API

## 3. Data Model

### Users
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| username | VARCHAR | Unique username |
| api_key | VARCHAR | API key for agent auth |
| role | ENUM | user / market_maker / admin |
| created_at | TIMESTAMP | Creation time |

### Balances
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | FK → Users | Owner |
| currency | ENUM | USDT / ETH / SOL / BTC |
| available | DECIMAL | Available balance |
| locked | DECIMAL | Frozen for orders/margin |

### SpotOrders
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | FK → Users | Owner |
| pair | VARCHAR | ETHUSDT / SOLUSDT / BTCUSDT |
| side | ENUM | buy / sell |
| order_type | ENUM | market / limit |
| price | DECIMAL | Order price (null for market) |
| quantity | DECIMAL | Order quantity |
| filled_quantity | DECIMAL | Filled amount |
| status | ENUM | pending / filled / partially_filled / cancelled |
| created_at | TIMESTAMP | Creation time |

### Positions (Perpetual Futures)
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | FK → Users | Owner |
| pair | VARCHAR | Trading pair |
| side | ENUM | long / short |
| leverage | INTEGER | 1-125 |
| entry_price | DECIMAL | Average entry price |
| quantity | DECIMAL | Position size |
| margin | DECIMAL | Locked margin |
| liquidation_price | DECIMAL | Auto-liquidation price |
| unrealized_pnl | DECIMAL | Current unrealized P&L |
| status | ENUM | open / closed / liquidated |
| created_at | TIMESTAMP | Open time |
| closed_at | TIMESTAMP | Close time |

### LiquidityPools (AMM)
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| pair | VARCHAR | Trading pair |
| reserve_base | DECIMAL | Base token reserve (e.g. ETH) |
| reserve_quote | DECIMAL | Quote token reserve (USDT) |
| k_value | DECIMAL | Constant product (x*y=k) |
| fee_rate | DECIMAL | Swap fee rate (default 0.3%) |

### LiquidityProvisions
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | FK → Users | Market Maker |
| pool_pair | VARCHAR | Pool reference |
| share_percentage | DECIMAL | Share of pool |
| base_deposited | DECIMAL | Base tokens deposited |
| quote_deposited | DECIMAL | Quote tokens deposited |

### Trades
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| order_id | FK | Related order |
| buyer_id | FK → Users | Buyer |
| seller_id | FK → Users | Seller |
| pair | VARCHAR | Trading pair |
| price | DECIMAL | Execution price |
| quantity | DECIMAL | Trade quantity |
| trade_type | ENUM | spot / futures / amm_swap |
| created_at | TIMESTAMP | Execution time |

### PriceHistory
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| pair | VARCHAR | Trading pair |
| price | DECIMAL | Price |
| timestamp | TIMESTAMP | Record time |

## 4. Core Business Logic

### 4.1 Price Engine
- Background asyncio task runs every **2 minutes**
- Fetches ETHUSDT, SOLUSDT, BTCUSDT from Binance REST API (`GET /api/v3/ticker/price`)
- On update: 1) Save to PriceHistory 2) WebSocket broadcast 3) Trigger position P&L recalc and liquidation check
- Fallback: if Binance API fails, use last known price

### 4.2 Spot Trading
- **Market Order**: Execute at current Binance price (or AMM pool price)
- **Limit Order**: Queue in order book, match when price updates
- Balance deduction/addition on Balances table
- Trading fee: 0.1% of trade value

### 4.3 Perpetual Futures
- **Open Position**: Select direction (long/short), leverage (1-125x), quantity
  - Required margin = position_value / leverage
  - Freeze margin from available balance
- **P&L Calculation**:
  - Long: unrealized_pnl = (current_price - entry_price) × quantity
  - Short: unrealized_pnl = (entry_price - current_price) × quantity
- **Liquidation**:
  - Maintenance margin rate = 0.5%
  - Liquidation triggers when: margin + unrealized_pnl ≤ position_value × maintenance_margin_rate
  - Long liquidation price = entry_price × (1 - 1/leverage + maintenance_margin_rate)
  - Short liquidation price = entry_price × (1 + 1/leverage - maintenance_margin_rate)
- **Close Position**: Manual close or stop-loss/take-profit trigger
- **Funding Rate**: Simplified, settled every 8 hours (0.01% base rate)

### 4.4 AMM Engine (Uniswap V2)
- **Minting**: Market Maker role can mint tokens (system creates balance)
- **Add Liquidity**: Deposit token pair into pool (e.g. ETH + USDT), must match current ratio
- **Swap**: Calculate output via x*y=k formula
  - amount_out = (reserve_out × amount_in × (1 - fee)) / (reserve_in + amount_in × (1 - fee))
- **Remove Liquidity**: Withdraw proportional share of pool
- **Fee**: 0.3% of swap value, distributed to liquidity providers

## 5. API Design

### 5.1 Agent Registration & SDK

```
# Agent Registration
POST /api/sdk/agents/register
Body: { "name": "TradingBot-1", "description": "BTC scalper" }
Response: {
  "api_key": "amv_xxxx",
  "agent_id": "uuid",
  "initial_balance": 10000,
  "currency": "USDT"
}

# Authentication: X-API-Key header for agents, JWT for web users
```

### 5.2 REST Endpoints

```
Auth & Account:
  POST   /api/auth/register          Register user (web)
  POST   /api/auth/login             Login (returns JWT)
  GET    /api/account/balance         Get all balances
  GET    /api/account/positions       Get all open positions

Price:
  GET    /api/prices                  Current prices for all pairs
  GET    /api/prices/{pair}/history   Price history

Spot Trading:
  POST   /api/spot/order              Place order (market/limit)
  GET    /api/spot/orders             List orders
  DELETE /api/spot/orders/{id}        Cancel order

Futures Trading:
  POST   /api/futures/open            Open position
  POST   /api/futures/close/{id}      Close position
  GET    /api/futures/positions        List positions
  PUT    /api/futures/leverage         Adjust leverage

AMM (Market Maker only):
  POST   /api/amm/mint               Mint tokens
  POST   /api/amm/add-liquidity      Add liquidity to pool
  POST   /api/amm/remove-liquidity   Remove liquidity
  GET    /api/amm/pools              Pool status
  POST   /api/amm/swap               Swap via AMM
```

### 5.3 WebSocket

```
WS /ws/prices       Price broadcast (every 2 min)
WS /ws/positions    Position updates (on price change)
```

### 5.4 Agent Integration Methods

1. **REST API** (universal, any language)
2. **Python SDK** (`pip install agent-metaverse`) - wrapper around REST API
3. **MCP Skill** - for Claude Code and MCP-compatible AI agents
   - Tools: `register`, `get_balance`, `buy_spot`, `sell_spot`, `open_position`, `close_position`, `get_prices`

## 6. Frontend (React)

- **Dashboard**: Real-time price display, simplified charts
- **Spot Trading Panel**: Order form, order book
- **Futures Trading Panel**: Open/close positions, position list, P&L display
- **Account Page**: Balance overview, trade history
- **AMM Management** (Market Maker only): Mint, add/remove liquidity, pool stats

## 7. Project Structure

```
Agent_metaverse/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Configuration
│   │   ├── database.py          # DB connection & session
│   │   ├── models/              # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── balance.py
│   │   │   ├── order.py
│   │   │   ├── position.py
│   │   │   ├── pool.py
│   │   │   ├── trade.py
│   │   │   └── price.py
│   │   ├── schemas/             # Pydantic request/response models
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── trading.py
│   │   │   ├── futures.py
│   │   │   └── amm.py
│   │   ├── api/                 # Route handlers
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── prices.py
│   │   │   ├── spot.py
│   │   │   ├── futures.py
│   │   │   ├── amm.py
│   │   │   └── sdk.py
│   │   ├── services/            # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── price_engine.py
│   │   │   ├── spot_engine.py
│   │   │   ├── futures_engine.py
│   │   │   ├── amm_engine.py
│   │   │   └── liquidation.py
│   │   ├── websocket/           # WebSocket handlers
│   │   │   ├── __init__.py
│   │   │   └── broadcaster.py
│   │   └── middleware/          # Auth middleware
│   │       └── auth.py
│   ├── alembic/                 # Database migrations
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/            # API client
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── sdk/                         # Python SDK for agents
│   ├── agent_metaverse/
│   │   ├── __init__.py
│   │   └── client.py
│   └── setup.py
├── mcp-server/                  # MCP Skill server
│   ├── server.py
│   └── tools.py
├── docs/
│   └── plans/
├── docker-compose.yml
└── README.md
```

## 8. Initial Funding

- New user/agent registration automatically receives **10,000 virtual USDT**
- Market Makers can mint additional tokens via `/api/amm/mint`
- Admin can adjust balances via admin API

## 9. Security & Constraints

- JWT authentication for web users
- API Key authentication for AI agents
- Rate limiting on trading endpoints
- All monetary operations use DECIMAL precision
- Database transactions for balance operations (ACID)
- Leverage limits enforced server-side (1-125x)
