"""
Golemio Transport Intelligence MCP Server
File: agents/mcp_server.py
"""

import os
import glob
import json
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# Initialize MCP Server
mcp = FastMCP("GolemioTransportServer")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

@mcp.tool()
def get_delays_by_line(line_number: int) -> str:
    """Queries local data logs for today's recorded delays for a specific bus line."""
    today_prefix = datetime.now().strftime("%Y%m%d")
    files = sorted(glob.glob(os.path.join(DATA_DIR, f"{today_prefix}_*.json")))
    
    line_records = []
    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    meta = item.get("metadata", {})
                    if meta.get("linka") == line_number:
                        line_records.append(meta)
        except Exception:
            continue

    if not line_records:
        return f"No delays found for line {line_number} today."

    return json.dumps(line_records, ensure_ascii=False, indent=2)

@mcp.tool()
def get_latest_run_summary() -> str:
    """Returns a summary of the most recent transport delay execution log."""
    today_prefix = datetime.now().strftime("%Y%m%d")
    files = sorted(glob.glob(os.path.join(DATA_DIR, f"{today_prefix}_*.json")))
    
    if not files:
        return "No run logs available for today."
        
    latest_file = files[-1]
    with open(latest_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    summary = {
        "file": os.path.basename(latest_file),
        "total_delayed_records": len(data),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return json.dumps(summary, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run()