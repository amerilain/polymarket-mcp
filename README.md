# Polymarket MCP Server

<!-- mcp-name: polymarket-mcp -->

**Model Context Protocol server for Polymarket prediction markets.** v0.3.0

Query Polymarket markets, events, narratives, arbitrage opportunities, and more — from any MCP-compatible client (Claude Desktop, OpenClaw, Cursor, etc.) OR via HTTP REST.

Zero dependencies. No API key required. MIT license.

## Quick Start

### Option A: MCP (recommended)



### Option B: HTTP (for curl/web/dashboards)



## Available Tools

| Tool | Description |
|------|-------------|
| top_markets | Top markets by volume (24h or total) with formatted prices |
| search_markets | Client-side keyword search across title+description |
| get_market | Detailed market info by slug |
| top_movers | Biggest price movers with price formatting |
| list_events | List events with optional child market details |
| market_narratives | Cluster events by theme/narrative with volume analysis |
| detect_volume_spikes | Find markets with unusual 24h volume spikes |
| find_arbitrage | Discover Yes+No != 100% opportunities |
| market_summary | Comprehensive ecosystem snapshot |

## Changelog

### v0.3.0 (2026-06-26)
- HTTP mode: --http PORT starts a REST API at /health, /tools, /call/{tool_name}
- HTML status page: GET / shows a human-readable dashboard
- CORS headers: All endpoints support cross-origin requests

### v0.2.0 (2026-06-26)
- Smart price formatting (Yes 52¢ / No 48¢)
- Proper client-side search
- Retry logic (429, 502, 503, 504)
- Connection resilience

## Technical Details

- Protocol: JSON-RPC 2.0 over stdio (MCP) OR HTTP REST
- Dependencies: Zero (Python standard library only)
- API: Polymarket Gamma API (public, no key needed)
- Python: 3.7+
- License: MIT

## Configuration with Claude Desktop

Add to claude_desktop_config.json:

