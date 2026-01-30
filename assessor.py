import requests
import json
import os

from pathlib import Path

# --- CONFIG ---
PRYSM_API = os.getenv("PRYSM_API", "http://localhost:3500")        # Prysm standard REST API
ERIGON_RPC = os.getenv("ERIGON_RPC", "http://localhost:8545")      # Erigon JSON-RPC


def get_erigon_sync_status():
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_syncing",
        "params": [],
        "id": 1
    }
    try:
        r = requests.post(ERIGON_RPC, json=payload, timeout=10)
        result = r.json().get("result")
        if not result:
            return {"synced": True, "details": "Erigon fully synced"}
        else:
            result.pop("stages")
            return {"synced": False, "result": result}
    except Exception as e:
        return {"error": str(e)}

def get_prysm_sync_status():
    try:
        r = requests.get(f"{PRYSM_API}/eth/v1/node/syncing", timeout=120)
        return r.json()["data"]
    except Exception as e:
        return {"error": str(e)}

def scan_logs(log_file: Path, warn_keyword: str, error_keyword: str):
    if not log_file.is_file():
        return {"missing": True}

    error_count = warning_count = total_count = 0
    log_text = log_file.read_text(encoding="utf8")
    for line in log_text.split("\n"):
        if error_keyword in line:
            error_count += 1
        elif warn_keyword in line:
            warning_count += 1

        total_count += 1

    return {
        "error_count": error_count,
        "warning_count": warning_count,
        "total_count": total_count,
        "error_rate": "%.2f %%" % (100 * error_count / total_count),
        "warning_rate": "%.2f %%" % (100 * warning_count / total_count),
    }

def assess(erigon_log: Path, prysm_log: Path):
    print("🔍 Checking Erigon sync status...")
    erigon = get_erigon_sync_status()
    print(json.dumps(erigon, indent=2))

    print("\n🔍 Checking Prysm sync status...")
    prysm = get_prysm_sync_status()
    print(json.dumps(prysm, indent=2))

    print("\n🧾 Scanning Prysm logs for issues...")
    log_summary = scan_logs(prysm_log, "level=warning", "level=error")
    print(json.dumps(log_summary, indent=2))

    print("\n🧾 Scanning Erigon logs for issues...")
    log_summary = scan_logs(erigon_log, "[WARN]", "[ERROR]")
    print(json.dumps(log_summary, indent=2))


if __name__ == "__main__":
    prysm_log = Path.home() /"logs" / "prysm_logs" / "prysm.log"
    erigon_log = Path.home() /"logs" / "erigon_logs" / "erigon.log"

    assess(erigon_log, prysm_log)
