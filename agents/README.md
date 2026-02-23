# Agent Metaverse - Agent Roles

This directory contains system prompts for different AI agent roles in the virtual exchange.

## Design Philosophy

These agents are designed to create **emergent adversarial dynamics**:
- Information asymmetry (some agents know more than others)
- Conflicting incentives (zero-sum competition)
- Trust and deception (agents can lie, manipulate, and collude)
- Different risk profiles and moral boundaries

## Roles

| Role | File | Strategy | Danger Level |
|------|------|----------|-------------|
| Market Maker | `market_maker.md` | Provides liquidity, manipulates spreads | Medium |
| Whale | `whale.md` | Pump & dump, market manipulation | High |
| Insider | `insider.md` | Trades on "leaked" info, front-runs | High |
| Shill | `shill.md` | Social engineering, fake signals | Very High |
| Retail Trader | `retail_trader.md` | Follows trends, trusts others | Low (victim) |
| Arbitrageur | `arbitrageur.md` | Exploits price differences | Low |
| Short Seller | `short_seller.md` | Bets against, spreads FUD | Medium |
| Liquidation Hunter | `liquidation_hunter.md` | Targets leveraged positions | High |

## How Deception Emerges

```
Shill ──(fake signals)──> Retail Trader ──(buys high)──> Whale dumps
  │                                                         │
  └──(colludes with)──> Whale ──(pump & dump)───────────────┘
                          │
Insider ──(front-runs)────┘
                          │
Short Seller <──(bets against)── Liquidation Hunter
  │                                    │
  └──(spreads FUD)──> Retail ──(panic sells)──> prices drop
                                               │
Arbitrageur ──(profits from chaos)─────────────┘
```

## Running Agents

```bash
# Start the exchange
docker-compose up -d

# Run individual agents
python3 agents/run.py --role whale --name "BigFish"
python3 agents/run.py --role shill --name "TrustMe" --target retail_trader

# Run full ecosystem (all roles)
python3 agents/run.py --ecosystem
```
