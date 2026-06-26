#!/usr/bin/env python3
"""
polymarket-mcp — MCP Server for Polymarket Prediction Markets

Model Context Protocol server that exposes Polymarket data as MCP tools.
Zero dependencies beyond Python standard library.

Protocol: JSON-RPC 2.0 over stdio (MCP stdio transport)

Usage:
    python3 polymarket_mcp.py          # Run as stdio MCP server
    python3 polymarket_mcp.py --debug  # Run with debug logging

To register with an MCP host (e.g., Claude Desktop, OpenClaw):
    mcporter config add polymarket stdio --command "python3 /path/to/polymarket_mcp.py"
"""

import json
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from collections import defaultdict
import traceback
import time
import random

API_BASE = "https://gamma-api.polymarket.com"
VERSION = "0.2.0"
DEBUG = False
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0


# ─── API Helpers ────────────────────────────────────────────────────────────

def api_get(path, params=None):
    """Make a GET request to Polymarket API with retry logic."""
    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "polymarket-mcp/2.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            last_error = RuntimeError(f"API error {e.code}: {body[:200]}")
            if e.code in (429, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                if DEBUG:
                    print(f"[DEBUG] Retry {attempt+1}/{MAX_RETRIES} after {delay:.1f}s (HTTP {e.code})", file=sys.stderr)
                time.sleep(delay)
                continue
            raise last_error
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_error = RuntimeError(f"Connection error: {e}")
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue
            raise last_error
    raise last_error or RuntimeError("Unknown API error")


def fmt_outcome_prices(prices_str):
    """Format outcomePrices JSON array (e.g. ["0.52","0.48"]) into readable string."""
    try:
        if isinstance(prices_str, str):
            prices = json.loads(prices_str)
        else:
            prices = prices_str
        if isinstance(prices, list) and len(prices) >= 2:
            yes = float(prices[0])
            no = float(prices[1])
            return f"Yes {yes*100:.0f}¢ / No {no*100:.0f}¢"
        return str(prices)
    except (ValueError, TypeError, json.JSONDecodeError):
        return str(prices_str)


# ─── Tool Implementations ───────────────────────────────────────────────────

def tool_list_tools():
    """Return the list of available tools (MCP tools/list)."""
    return {
        "top_markets": {
            "description": "Top Polymarket markets by 24h volume",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of results (default 10)", "default": 10},
                    "by_total": {"type": "boolean", "description": "Sort by total volume instead of 24h", "default": False},
                }
            }
        },
        "search_markets": {
            "description": "Search Polymarket markets by keyword",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "limit": {"type": "integer", "description": "Number of results (default 10)", "default": 10},
                },
                "required": ["query"]
            }
        },
        "get_market": {
            "description": "Get detailed info about a specific Polymarket market by slug",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Market slug (e.g. 'will-bitcoin-reach-100k-by-2025')"},
                },
                "required": ["slug"]
            }
        },
        "top_movers": {
            "description": "Biggest price movers on Polymarket",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "period": {"type": "integer", "description": "Lookback period in days (default 1)", "default": 1},
                    "limit": {"type": "integer", "description": "Number of results (default 10)", "default": 10},
                }
            }
        },
        "list_events": {
            "description": "List Polymarket events with child markets",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of events (default 10)", "default": 10},
                    "with_markets": {"type": "boolean", "description": "Include child market details", "default": False},
                    "tag": {"type": "string", "description": "Filter by tag (e.g. 'crypto', 'election', 'sports')", "default": ""},
                }
            }
        },
        "market_narratives": {
            "description": "Cluster Polymarket events by theme/narrative",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of events to analyze (default 50)", "default": 50},
                }
            }
        },
        "detect_volume_spikes": {
            "description": "Detect Polymarket markets with unusual 24h volume",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of results (default 10)", "default": 10},
                }
            }
        },
        "find_arbitrage": {
            "description": "Find arbitrage opportunities where Yes+No != 100%",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of results (default 10)", "default": 10},
                    "min_spread": {"type": "number", "description": "Minimum total spread for arb detection (default 0.0)", "default": 0.0},
                }
            }
        },
        "market_summary": {
            "description": "Get a comprehensive summary of the Polymarket ecosystem right now",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
    }


def cmd_top_markets(args):
    """Top markets by 24h (or total) volume."""
    limit = min(args.get("limit", 10), 100)
    by_total = args.get("by_total", False)
    params = [("limit", str(limit)), ("closed", "false")]
    if by_total:
        params.append(("sort", "volume"))
    else:
        params.append(("sort", "volume_24h"))
    markets = api_get("/markets", params)
    results = []
    for m in markets[:limit]:
        results.append({
            "title": m.get("question", m.get("title", "?")),
            "slug": m.get("slug", ""),
            "price": fmt_outcome_prices(m.get("outcomePrices", "[]")),
            "volume_24h": m.get("volume24hr", "0"),
            "volume_total": m.get("volume", "0"),
            "liquidity": m.get("liquidity", "0"),
        })
    return results


def cmd_search_markets(args):
    """Search markets by keyword."""
    query = args.get("query", "")
    limit = min(args.get("limit", 10), 100)
    params = [("limit", str(limit)), ("closed", "false"), ("tag", query)]
    markets = api_get("/markets", params)
    results = []
    for m in markets[:limit]:
        results.append({
            "title": m.get("question", m.get("title", "?")),
            "slug": m.get("slug", ""),
            "price": fmt_outcome_prices(m.get("outcomePrices", "[]")),
            "volume_24h": m.get("volume24hr", "0"),
            "volume_total": m.get("volume", "0"),
        })
    return results


def cmd_get_market(args):
    """Get market details by slug."""
    slug = args.get("slug", "")
    markets = api_get("/markets", [("slug", slug)])
    if not markets:
        return {"error": f"Market not found: {slug}"}
    m = markets[0]
    return {
        "title": m.get("question", m.get("title", "?")),
        "slug": m.get("slug", ""),
        "description": m.get("description", m.get("question", "")),
        "price": fmt_outcome_prices(m.get("outcomePrices", "[]")),
        "volume_24h": m.get("volume24hr", "0"),
        "volume_total": m.get("volume", "0"),
        "liquidity": m.get("liquidity", "0"),
        "spread": m.get("spread", "?"),
        "start_date": m.get("startDate", ""),
        "end_date": m.get("endDate", ""),
        "outcomes": m.get("outcomes", ""),
        "condition_id": m.get("conditionId", ""),
        "neg_risk": m.get("negRisk", False),
    }


def cmd_top_movers(args):
    """Biggest price movers over a period."""
    period = min(args.get("period", 1), 30)
    limit = min(args.get("limit", 10), 100)
    params = [("limit", str(limit)), ("closed", "false")]
    markets = api_get("/markets", params)
    results = []
    for m in markets:
        try:
            prices_str = m.get("outcomePrices", "[0]")
            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
            yes_price = float(prices[0]) if prices else 0.0
        except (ValueError, IndexError, TypeError):
            continue
        results.append({
            "title": m.get("question", m.get("title", "?")),
            "slug": m.get("slug", ""),
            "price": f"{yes_price*100:.1f}¢",
            "volume_24h": m.get("volume24hr", "0"),
        })
    results.sort(key=lambda x: float(x["volume_24h"]), reverse=True)
    return results[:limit]


def cmd_list_events(args):
    """List events, optionally with child market details."""
    limit = min(args.get("limit", 10), 100)
    with_markets = args.get("with_markets", False)
    tag = args.get("tag", "")
    params = [("limit", str(limit * 2))]
    if tag:
        params.append(("tag", tag))
    events = api_get("/events", params)
    results = []
    for e in events[:limit]:
        entry = {
            "title": e.get("title", "?"),
            "slug": e.get("slug", ""),
            "description": e.get("description", ""),
            "start_date": e.get("startDate", ""),
            "end_date": e.get("endDate", ""),
            "volume": e.get("volume", "0"),
            "liquidity": e.get("liquidity", "0"),
        }
        if with_markets:
            markets = e.get("markets", [])
            entry["markets"] = [{
                "title": m.get("question", m.get("title", "?")),
                "slug": m.get("slug", ""),
                "price": fmt_outcome_prices(m.get("outcomePrices", "[]")),
                "volume_24h": m.get("volume24hr", "0"),
            } for m in markets[:5]]
        results.append(entry)
    return results


def cmd_narratives(args):
    """Cluster events by theme/narrative."""
    limit = min(args.get("limit", 50), 200)
    events = api_get("/events", [("limit", str(limit))])
    themes = defaultdict(lambda: {"volume": 0, "count": 0, "events": []})
    theme_keywords = {
        "crypto/blockchain": ["crypto", "bitcoin", "ethereum", "blockchain", "solana", "defi", "nft", "token", "btc", "eth"],
        "US politics": ["trump", "biden", "election", "congress", "senate", "democrat", "republican", "presidential", "gop", "dfl"],
        "economy/markets": ["fed", "inflation", "recession", "gdp", "stock", "s&p", "rate", "tariff", "trade"],
        "geopolitics": ["war", "russia", "ukraine", "china", "taiwan", "nato", "iran", "israel", "gaza", "nuclear"],
        "tech/ai": ["ai", "openai", "gpt", "anthropic", "google", "apple", "meta", "microsoft", "nvidia", "robot"],
        "sports": ["nba", "nfl", "mlb", "soccer", "champions", "super bowl", "world cup", "olympic", "fight"],
        "science/health": ["covid", "vaccine", "space", "nasa", "mars", "cancer", "drug", "fda"],
        "entertainment": ["oscar", "grammy", "movie", "music", "box office", "netflix", "disney"],
    }
    for e in events:
        title = (e.get("title", "") + " " + e.get("description", "")).lower()
        vol = float(e.get("volume", "0"))
        for theme, keywords in theme_keywords.items():
            if any(kw in title for kw in keywords):
                themes[theme]["volume"] += vol
                themes[theme]["count"] += 1
                themes[theme]["events"].append({
                    "title": e.get("title", "?"),
                    "slug": e.get("slug", ""),
                    "volume": str(vol),
                })
                break
        else:
            themes["other"]["volume"] += vol
            themes["other"]["count"] += 1
    sorted_themes = sorted(themes.items(), key=lambda x: x[1]["volume"], reverse=True)
    results = []
    for theme, data in sorted_themes:
        top_events = sorted(data["events"], key=lambda x: float(x["volume"]), reverse=True)[:3]
        results.append({
            "theme": theme,
            "volume": f"{data['volume']:.0f}",
            "count": data["count"],
            "top_events": top_events,
        })
    return results


def cmd_volume_spikes(args):
    """Detect markets with unusual volume."""
    limit = min(args.get("limit", 10), 100)
    markets = api_get("/markets", [("limit", "200"), ("closed", "false")])
    candidates = []
    for m in markets:
        try:
            vol_24h = float(m.get("volume24hr", "0"))
            vol_total = float(m.get("volume", "0"))
        except (ValueError, TypeError):
            continue
        if vol_total > 0 and vol_24h > 0:
            ratio = vol_24h / vol_total
            if ratio > 0.3:  # More than 30% of life volume in last 24h
                candidates.append({
                    "title": m.get("question", m.get("title", "?")),
                    "slug": m.get("slug", ""),
                    "volume_24h": f"{vol_24h:.0f}",
                    "volume_total": f"{vol_total:.0f}",
                    "ratio": f"{ratio*100:.0f}%",
                })
    candidates.sort(key=lambda x: float(x.get("volume_24h", "0")), reverse=True)
    return candidates[:limit]


def cmd_arbitrage(args):
    """Find markets where Yes+No != 100%."""
    limit = min(args.get("limit", 10), 100)
    min_spread = args.get("min_spread", 0.0)
    markets = api_get("/markets", [("limit", "200"), ("closed", "false")])
    opportunities = []
    for m in markets:
        try:
            prices_str = m.get("outcomePrices", "[0]")
            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
            if len(prices) >= 2:
                total = float(prices[0]) + float(prices[1])
                spread = abs(total - 1.0)
                if spread >= min_spread:
                    opportunities.append({
                        "title": m.get("question", m.get("title", "?")),
                        "slug": m.get("slug", ""),
                        "yes_price": f"{float(prices[0])*100:.0f}¢",
                        "no_price": f"{float(prices[1])*100:.0f}¢",
                        "total": f"{total*100:.1f}%",
                        "spread": f"{spread*100:.1f}%",
                    })
        except (ValueError, IndexError, TypeError):
            continue
    opportunities.sort(key=lambda x: abs(float(x["spread"].rstrip("%"))), reverse=True)
    return opportunities[:limit]


def cmd_summary(args):
    """Comprehensive market summary."""
    # Top markets
    top = cmd_top_markets({"limit": 5, "by_total": False})
    # Narratives
    narratives = cmd_narratives({"limit": 50})
    # Arbitrage
    arb = cmd_arbitrage({"limit": 3, "min_spread": 0.0})
    # Volume spikes
    spikes = cmd_volume_spikes({"limit": 3})
    # Events
    events = api_get("/events", [("limit", "20")])
    total_volume = sum(float(e.get("volume", "0")) for e in events)
    active_events = len(events)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ecosystem": {
            "active_events": active_events,
            "total_volume": f"{total_volume:.0f}",
        },
        "top_markets": top,
        "narratives": narratives[:5],
        "arbitrage_opportunities": arb,
        "volume_spikes": spikes,
    }


# ─── MCP Protocol ───────────────────────────────────────────────────────────
#
# Implements the Model Context Protocol (stdio transport).
# Communicates via JSON-RPC 2.0 over stdin/stdout.
#
# Required endpoints:
#   - tools/list   -> List available tools
#   - tools/call   -> Call a tool by name with arguments
#
# Optional (not implemented yet):
#   - resources/list
#   - resources/read

COMMANDS = {
    "top_markets": cmd_top_markets,
    "search_markets": cmd_search_markets,
    "get_market": cmd_get_market,
    "top_movers": cmd_top_movers,
    "list_events": cmd_list_events,
    "market_narratives": cmd_narratives,
    "detect_volume_spikes": cmd_volume_spikes,
    "find_arbitrage": cmd_arbitrage,
    "market_summary": cmd_summary,
}




# ──────────────────────────────────────────────
# HTTP Server Mode
# ──────────────────────────────────────────────


def run_http_server(port=8099):
    """Run polymarket-mcp as an HTTP server for curl/web/dashboard access.

    Endpoints:
      GET  /                    -> HTML status page
      GET  /health              -> JSON health check
      GET  /tools               -> List available tools
      POST /call/{tool_name}    -> Call a tool with JSON body
    """
    import http.server
    import socketserver
    import urllib.parse

    class MCPHTTPHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("[polymarket-http] %s\n" % (fmt % args))

        def _send_json(self, data, status=200):
            body = json.dumps(data, indent=2, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _call_tool(self, name, args):
            if name not in COMMANDS:
                return {"error": "Unknown tool: " + name}, 404
            try:
                result = COMMANDS[name](args)
                return result, 200
            except Exception as e:
                return {"error": str(e)}, 500

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path == "/health":
                self._send_json({
                    "status": "ok",
                    "server": "polymarket-mcp",
                    "version": VERSION,
                    "tools": len(COMMANDS),
                })
            elif path == "/tools":
                tools_info = tool_list_tools()
                self._send_json({
                    "tools": [
                        {"name": n, "description": m["description"], "inputSchema": m["inputSchema"]}
                        for n, m in tools_info.items()
                    ]
                })
            elif path == "/":
                tools_info = tool_list_tools()
                rows = "".join(
                    '<tr><td><code>' + n + '</code></td><td>' + m["description"] + '</td></tr>'
                    for n, m in tools_info.items()
                )
                html = """<!DOCTYPE html>
<html><head><title>Polymarket MCP Server</title><meta charset="utf-8">
<style>
body{font-family:system-ui,sans-serif;max-width:900px;margin:2em auto;padding:1em}
h1{color:#2563eb}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #d1d5db;padding:8px 12px;text-align:left}
th{background:#f3f4f6}
code{background:#f3f4f6;padding:2px 4px;border-radius:3px}
pre{background:#1e293b;color:#e2e8f0;padding:1em;border-radius:6px;overflow-x:auto}
</style></head><body>
<h1>Polymarket MCP Server v""" + VERSION + """</h1>
<p>Zero-dependency MCP + HTTP server for Polymarket prediction markets.
<a href="/health">Health</a> | <a href="/tools">Tools JSON</a></p>
<h2>Tools (""" + str(len(COMMANDS)) + """)</h2>
<table><tr><th>Tool</th><th>Description</th></tr>"""
                html += rows
                html += """</table>
<h2>Usage</h2>
<pre># Health check
curl http://localhost:""" + str(port) + """/health

# List tools
curl http://localhost:""" + str(port) + """/tools

# Call a tool
curl -X POST http://localhost:""" + str(port) + """/call/top_markets \\
  -H 'Content-Type: application/json' \\
  -d '{"limit":5}'
</pre>
</body></html>"""
                body = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._send_json({"error": "not found"}, 404)

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/")
            content_length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                args = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._send_json({"error": "invalid JSON"}, 400)
                return
            if path.startswith("/call/"):
                name = path[6:]
                result, status = self._call_tool(name, args)
                self._send_json(result, status)
            else:
                self._send_json({"error": "not found"}, 404)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), MCPHTTPHandler) as server:
        sys.stderr.write("[polymarket-mcp] HTTP server on http://0.0.0.0:%d\n" % port)
        sys.stderr.write("[polymarket-mcp] Endpoints: /health /tools /call/{tool_name}\n")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            sys.stderr.write("[polymarket-mcp] HTTP server stopped\n")


def handle_request(request):
    """Handle a single JSON-RPC request."""
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [{
                    "name": name,
                    "description": meta["description"],
                    "inputSchema": meta["inputSchema"],
                } for name, meta in tool_list_tools().items()]
            }
        }

    elif method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        if name not in COMMANDS:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {name}"}
            }
        try:
            result = COMMANDS[name](arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }
        except Exception as e:
            tb = traceback.format_exc()
            if DEBUG:
                print(f"[DEBUG] Error calling {name}: {tb}", file=sys.stderr)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)[:500]}
            }

    elif method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "polymarket-mcp",
                    "version": VERSION,
                }
            }
        }

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


def main():
    global DEBUG
    if "--debug" in sys.argv:
        DEBUG = True
        sys.argv.remove("--debug")

    if "--http" in sys.argv or "--port" in sys.argv:
        port = 8099
        if "--http" in sys.argv and len(sys.argv) > sys.argv.index("--http") + 1:
            next_arg = sys.argv[sys.argv.index("--http") + 1]
            if next_arg.lstrip("-").isdigit():
                port = int(next_arg)
                sys.argv.pop(sys.argv.index("--http") + 1)
            sys.argv.remove("--http")
        if "--port" in sys.argv and len(sys.argv) > sys.argv.index("--port") + 1:
            next_arg = sys.argv[sys.argv.index("--port") + 1]
            if next_arg.lstrip("-").isdigit():
                port = int(next_arg)
                sys.argv.pop(sys.argv.index("--port") + 1)
            sys.argv.remove("--port")
        run_http_server(port)
        return

    if DEBUG:
        print("[polymarket-mcp] Starting MCP server (stdio transport)", file=sys.stderr)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if DEBUG:
            print(f"[DEBUG] <<< {line[:200]}", file=sys.stderr)
        try:
            request = json.loads(line)
            response = handle_request(request)
        except json.JSONDecodeError as e:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"}
            }
        output = json.dumps(response)
        if DEBUG:
            print(f"[DEBUG] >>> {output[:200]}", file=sys.stderr)
        sys.stdout.write(output + "\n")
        sys.stdout.flush()

    if DEBUG:
        print("[polymarket-mcp] stdin closed, shutting down", file=sys.stderr)


if __name__ == "__main__":
    main()
