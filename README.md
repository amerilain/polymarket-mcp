# Polymarket MCP Server

**Model Context Protocol server for Polymarket prediction markets.**

Query Polymarket markets, events, narratives, arbitrage opportunities, and more — all from your MCP-compatible client (Claude Desktop, OpenClaw, Cursor, etc.).

Zero dependencies. No API key required. Uses Polymarket's public API.

# Polymarket MCP Server v0.2.0

**Model Context Protocol server for Polymarket prediction markets.**

Query Polymarket markets, events, narratives, arbitrage opportunities, and more — all from your MCP-compatible client (Claude Desktop, OpenClaw, Cursor, etc.).

Zero dependencies. No API key required. Automatic retry on rate limits.

## Quick Start

### 1. Register with mcporter

```bash
mcporter config add polymarket \
  --command "$(which python3)" \
  --arg "/path/to/polymarket-mcp/polymarket_mcp.py"
```

### 2. Use it

```bash
mcporter call polymarket.market_summary
mcporter call polymarket.top_markets limit=10
mcporter call polymarket.search_markets query=bitcoin
mcporter call polymarket.find_arbitrage min_spread=0.02
mcporter call polymarket.market_narratives limit=50
```

### 3. Or use directly (stdio)

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 polymarket_mcp.py
```

## Available Tools

| Tool | Description |
|------|-------------|
| `top_markets` | Top markets by volume (24h or total) with formatted prices |
| `search_markets` | Client-side keyword search across title+description (not just tags) |
| `get_market` | Detailed market info by slug (includes description, dates, condition id) |
| `top_movers` | Biggest price movers with price formatting |
| `list_events` | List events with optional child market details |
| `market_narratives` | Cluster events by theme/narrative with volume analysis |
| `detect_volume_spikes` | Find markets with unusual 24h volume spikes |
| `find_arbitrage` | Discover Yes+No != 100% opportunities with formatted prices |
| `market_summary` | Comprehensive ecosystem snapshot (top markets, narratives, arb, spikes) |

## v0.2.0 Changes

- **Smart price formatting**: Prices now show as `Yes 52¢ / No 48¢` instead of raw JSON arrays
- **Proper search**: `search_markets` now does real client-side keyword matching instead of server-side tag filtering
- **Retry logic**: Automatic backoff + retry on rate limits (429) and server errors (502, 503, 504)
- **Connection resilience**: Retries on network errors and timeouts
- **Better market fetching**: `top_movers` and `search_markets` now pull 200 markets instead of 10 for more accurate results

## Technical Details

- **Protocol**: JSON-RPC 2.0 over stdio (MCP stdio transport)
- **Dependencies**: Zero (Python standard library only)
- **API**: Polymarket Gamma API (public, no key needed)
- **MCP Version**: 2024-11-05
- **Python**: 3.7+

## Examples

```bash
# Get top crypto markets
mcporter call polymarket.search_markets query=crypto limit=5

# Find arbitrage opportunities with >2% spread
mcporter call polymarket.find_arbitrage limit=20 min_spread=0.02

# Market health check
mcporter call polymarket.market_summary

# See what narratives are driving volume
mcporter call polymarket.market_narratives limit=100

# Monitor a specific market
mcporter call polymarket.get_market slug=will-bitcoin-reach-100k-by-2025
```

## Configuration with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "polymarket": {
      "command": "python3",
      "args": ["/path/to/polymarket-mcp/polymarket_mcp.py"]
    }
  }
}
```

## Configuration with OpenClaw

```bash
# Already done if you're reading this
mcporter config add polymarket \
  --command "$(which python3)" \
  --arg "$(pwd)/polymarket_mcp.py"
```
