"""
Polls active network connections and flags anything that isn't loopback or
private-LAN. Run this in its own terminal, visible to judges, for the whole
demo. A clean log (only 127.0.0.1 / your LAN subnet, no public IPs) is the
actual proof of "nothing leaves the premises" — not a slide claiming it.

Run: python network_monitor/watch.py
"""
import ipaddress
import time
from datetime import datetime
from pathlib import Path

import psutil

LOG_PATH = Path(__file__).parent / "network_activity.log"
POLL_SECONDS = 2

# Extend this only with your own LAN/subnet if the GPU box is a separate
# on-prem server reachable over the intranet. Empty = strictly loopback-only.
ALLOWED_PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]


def is_allowed(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in ALLOWED_PRIVATE_NETS)


def scan_once():
    flagged = []
    for conn in psutil.net_connections(kind="inet"):
        if conn.status != psutil.CONN_ESTABLISHED or not conn.raddr:
            continue
        remote_ip = conn.raddr.ip
        if not is_allowed(remote_ip):
            flagged.append((conn.pid, remote_ip, conn.raddr.port))
    return flagged


def main():
    print(f"[network monitor] watching every {POLL_SECONDS}s — logging to {LOG_PATH}")
    print("[network monitor] anything outside 127.0.0.0/8, 10/8, 172.16/12, 192.168/16 will be flagged in RED below.\n")
    with open(LOG_PATH, "a") as log:
        log.write(f"\n--- session started {datetime.now().isoformat()} ---\n")
        while True:
            flagged = scan_once()
            ts = datetime.now().isoformat(timespec="seconds")
            if flagged:
                for pid, ip, port in flagged:
                    line = f"{ts} EXTERNAL CONNECTION pid={pid} -> {ip}:{port}"
                    print(f"\033[91m{line}\033[0m")   # red
                    log.write(line + "\n")
            else:
                line = f"{ts} clean (loopback/LAN only)"
                print(line)
                log.write(line + "\n")
            log.flush()
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
