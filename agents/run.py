#!/usr/bin/env python3
"""
Agent Metaverse - Multi-Agent Ecosystem Runner

Registers agents on the exchange, loads their role prompts,
and provides the context needed for LLM-powered agents to trade.

Usage:
    # Register all agents from ecosystem.json
    python3 agents/run.py --setup

    # Get the full prompt for a specific agent (pipe to your LLM)
    python3 agents/run.py --agent GoldenWhale --action prompt

    # Execute a single trading cycle for an agent
    python3 agents/run.py --agent GoldenWhale --action cycle

    # Show ecosystem status (all agents' balances and positions)
    python3 agents/run.py --status
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

BASE_URL = os.environ.get("AGENT_METAVERSE_BASE_URL", "http://localhost:8000")
AGENTS_DIR = Path(__file__).parent
ECOSYSTEM_FILE = AGENTS_DIR / "ecosystem.json"
KEYS_FILE = AGENTS_DIR / ".agent_keys.json"


def load_ecosystem() -> dict:
    with open(ECOSYSTEM_FILE) as f:
        return json.load(f)


def load_keys() -> dict:
    if KEYS_FILE.exists():
        with open(KEYS_FILE) as f:
            return json.load(f)
    return {}


def save_keys(keys: dict):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)


def register_agent(name: str, description: str) -> dict:
    resp = httpx.post(
        f"{BASE_URL}/api/sdk/agents/register",
        json={"name": name, "description": description},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def get_agent_state(api_key: str) -> dict:
    headers = {"X-API-Key": api_key}
    client = httpx.Client(base_url=BASE_URL, headers=headers, timeout=30.0)

    balances = client.get("/api/account/balance").json()
    positions = client.get("/api/futures/positions").json()
    orders = client.get("/api/spot/orders").json()
    prices = client.get("/api/prices").json()
    pools = client.get("/api/amm/pools").json()

    client.close()

    return {
        "prices": prices,
        "balances": balances,
        "positions": positions,
        "open_orders": orders,
        "amm_pools": pools,
    }


def build_agent_prompt(agent_config: dict, state: dict, ecosystem: dict) -> str:
    """Build the full system prompt for an agent, including role + market state."""

    # Load role prompt
    prompt_path = AGENTS_DIR / agent_config["prompt_file"]
    with open(prompt_path) as f:
        role_prompt = f.read()

    # Build allies info
    allies = agent_config.get("allies", [])
    allies_text = f"Your known allies: {', '.join(allies)}" if allies else "You have no pre-arranged allies."

    # Build other agents info (what this agent can see)
    other_agents = [a["name"] for a in ecosystem["agents"] if a["name"] != agent_config["name"]]

    prompt = f"""{role_prompt}

---

# Current Market State

## Your Identity
- Name: {agent_config['name']}
- Role: {agent_config['role']}
- {allies_text}

## Other Agents in the Market
{', '.join(other_agents)}

## Current Prices
{json.dumps(state['prices'], indent=2)}

## Your Balances
{json.dumps(state['balances'], indent=2)}

## Your Open Futures Positions
{json.dumps(state['positions'], indent=2)}

## Your Spot Orders
{json.dumps(state['open_orders'], indent=2)}

## AMM Pool States (Public)
{json.dumps(state['amm_pools'], indent=2)}

---

# Your Action

Based on your role, the current market state, and your strategy, decide your next actions.

Respond with a JSON object:
```json
{{
  "reasoning": "Your private internal reasoning (not shared with others)",
  "trades": [
    {{"action": "buy_spot", "pair": "ETHUSDT", "quantity": 0.5}},
    {{"action": "sell_spot", "pair": "ETHUSDT", "quantity": 0.5}},
    {{"action": "open_long", "pair": "BTCUSDT", "leverage": 10, "quantity": 0.01}},
    {{"action": "open_short", "pair": "ETHUSDT", "leverage": 5, "quantity": 1.0}},
    {{"action": "close_position", "position_id": "uuid"}},
    {{"action": "swap_buy", "pair": "ETHUSDT", "amount": 100}},
    {{"action": "swap_sell", "pair": "ETHUSDT", "amount": 0.5}}
  ],
  "messages": [
    {{"to": "all", "content": "Public message visible to all agents"}},
    {{"to": "GoldenWhale", "content": "Private message to a specific agent"}}
  ],
  "strategy_update": "Brief note on how your strategy is evolving"
}}
```

Only include trades you actually want to execute this cycle. You may include 0 trades if waiting is the best strategy. Messages are optional.
"""
    return prompt


def cmd_setup(args):
    """Register all agents from ecosystem.json."""
    ecosystem = load_ecosystem()
    keys = load_keys()

    for agent in ecosystem["agents"]:
        name = agent["name"]
        if name in keys:
            print(f"  [skip] {name} already registered (key: {keys[name][:20]}...)")
            continue

        try:
            result = register_agent(name, agent["description"])
            keys[name] = result["api_key"]
            save_keys(keys)
            print(f"  [ok]   {name} registered → {result['api_key'][:20]}... (${result['initial_balance']} USDT)")
        except Exception as e:
            print(f"  [fail] {name}: {e}")

    print(f"\nRegistered {len(keys)} agents. Keys saved to {KEYS_FILE}")


def cmd_prompt(args):
    """Print the full prompt for an agent."""
    ecosystem = load_ecosystem()
    keys = load_keys()

    agent_config = next((a for a in ecosystem["agents"] if a["name"] == args.agent), None)
    if not agent_config:
        print(f"Agent '{args.agent}' not found in ecosystem.json")
        sys.exit(1)

    if args.agent not in keys:
        print(f"Agent '{args.agent}' not registered. Run --setup first.")
        sys.exit(1)

    state = get_agent_state(keys[args.agent])
    prompt = build_agent_prompt(agent_config, state, ecosystem)
    print(prompt)


def cmd_status(args):
    """Show status of all agents."""
    ecosystem = load_ecosystem()
    keys = load_keys()
    prices = httpx.get(f"{BASE_URL}/api/prices", timeout=30.0).json()

    print(f"Prices: {json.dumps(prices)}\n")
    print(f"{'Agent':<16} {'Role':<20} {'USDT':>12} {'ETH':>10} {'SOL':>10} {'BTC':>10} {'Positions':>10}")
    print("-" * 90)

    pair_map = {"ETH": "ETHUSDT", "SOL": "SOLUSDT", "BTC": "BTCUSDT"}

    for agent in ecosystem["agents"]:
        name = agent["name"]
        if name not in keys:
            print(f"{name:<16} {'(not registered)':<20}")
            continue

        try:
            state = get_agent_state(keys[name])
            bal = {b["currency"]: b["available"] for b in state["balances"]}

            usdt = f"{float(bal.get('USDT', 0)):.2f}"
            eth = f"{float(bal.get('ETH', 0)):.4f}"
            sol = f"{float(bal.get('SOL', 0)):.4f}"
            btc = f"{float(bal.get('BTC', 0)):.6f}"
            pos_count = str(len(state["positions"]))

            print(f"{name:<16} {agent['role']:<20} {usdt:>12} {eth:>10} {sol:>10} {btc:>10} {pos_count:>10}")
        except Exception as e:
            print(f"{name:<16} {'error: ' + str(e):<20}")

    print()


def cmd_execute(args):
    """Execute trades from a JSON action file (output of LLM agent)."""
    keys = load_keys()

    if args.agent not in keys:
        print(f"Agent '{args.agent}' not registered.")
        sys.exit(1)

    api_key = keys[args.agent]
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    # Read action JSON from stdin or file
    if args.action_file:
        with open(args.action_file) as f:
            action = json.load(f)
    else:
        action = json.load(sys.stdin)

    trades = action.get("trades", [])
    messages = action.get("messages", [])

    print(f"Executing {len(trades)} trades for {args.agent}...")

    for trade in trades:
        act = trade["action"]
        try:
            if act == "buy_spot":
                resp = httpx.post(f"{BASE_URL}/api/spot/order", headers=headers, json={
                    "pair": trade["pair"], "side": "buy", "order_type": "market", "quantity": trade["quantity"]
                }, timeout=30.0)
            elif act == "sell_spot":
                resp = httpx.post(f"{BASE_URL}/api/spot/order", headers=headers, json={
                    "pair": trade["pair"], "side": "sell", "order_type": "market", "quantity": trade["quantity"]
                }, timeout=30.0)
            elif act == "open_long":
                resp = httpx.post(f"{BASE_URL}/api/futures/open", headers=headers, json={
                    "pair": trade["pair"], "side": "long", "leverage": trade["leverage"], "quantity": trade["quantity"]
                }, timeout=30.0)
            elif act == "open_short":
                resp = httpx.post(f"{BASE_URL}/api/futures/open", headers=headers, json={
                    "pair": trade["pair"], "side": "short", "leverage": trade["leverage"], "quantity": trade["quantity"]
                }, timeout=30.0)
            elif act == "close_position":
                resp = httpx.post(f"{BASE_URL}/api/futures/close/{trade['position_id']}", headers=headers, timeout=30.0)
            elif act == "swap_buy":
                resp = httpx.post(f"{BASE_URL}/api/amm/swap", headers=headers, json={
                    "pair": trade["pair"], "side": "buy", "amount": trade["amount"]
                }, timeout=30.0)
            elif act == "swap_sell":
                resp = httpx.post(f"{BASE_URL}/api/amm/swap", headers=headers, json={
                    "pair": trade["pair"], "side": "sell", "amount": trade["amount"]
                }, timeout=30.0)
            else:
                print(f"  [skip] Unknown action: {act}")
                continue

            if resp.status_code < 400:
                print(f"  [ok]   {act}: {json.dumps(trade)}")
            else:
                print(f"  [fail] {act}: {resp.text}")
        except Exception as e:
            print(f"  [fail] {act}: {e}")

    if messages:
        print(f"\nMessages from {args.agent}:")
        for msg in messages:
            print(f"  → [{msg['to']}]: {msg['content']}")


def main():
    parser = argparse.ArgumentParser(description="Agent Metaverse Ecosystem Runner")
    parser.add_argument("--setup", action="store_true", help="Register all agents from ecosystem.json")
    parser.add_argument("--status", action="store_true", help="Show all agents' status")
    parser.add_argument("--agent", type=str, help="Agent name")
    parser.add_argument("--action", choices=["prompt", "execute"], help="Action to perform")
    parser.add_argument("--action-file", type=str, help="JSON file with trades to execute (for execute action)")

    args = parser.parse_args()

    if args.setup:
        cmd_setup(args)
    elif args.status:
        cmd_status(args)
    elif args.agent and args.action == "prompt":
        cmd_prompt(args)
    elif args.agent and args.action == "execute":
        cmd_execute(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
