import socket
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

def parse_ovpn_remote(file_path):
    """
    Parses an .ovpn file and extracts the list of (host, port) from remote lines.
    """
    remotes = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                parts = line.split()
                if parts and parts[0] == "remote":
                    if len(parts) > 1:
                        host = parts[1]
                        port = 1194  # Default OpenVPN port
                        if len(parts) > 2:
                            if parts[2].isdigit():
                                port = int(parts[2])
                        remotes.append((host, port))
    except Exception as e:
        logger.error(f"Error parsing {file_path}: {e}")
    return remotes

def ping_host(host, port, timeout=1.5):
    """
    Measures TCP connection latency to a host and port.
    If the connection succeeds or is refused (meaning host is alive and responded),
    returns the RTT in milliseconds. Otherwise, returns None.
    """
    t0 = time.perf_counter()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        rtt = (time.perf_counter() - t0) * 1000
        return round(rtt, 1)
    except ConnectionRefusedError:
        # The host exists and responded with a reset, meaning it is alive!
        rtt = (time.perf_counter() - t0) * 1000
        return round(rtt, 1)
    except Exception:
        return None
    finally:
        s.close()

def test_single_ovpn(file_path, timeout=1.5):
    """
    Tests speed for a single .ovpn file. Returns the best RTT found among all remote lines.
    """
    remotes = parse_ovpn_remote(file_path)
    if not remotes:
        return None

    best_rtt = None
    for host, port in remotes:
        rtt = ping_host(host, port, timeout=timeout)
        if rtt is not None:
            if best_rtt is None or rtt < best_rtt:
                best_rtt = rtt
    return best_rtt

def test_all_configs(config_dir, file_list, timeout=1.5, max_workers=10):
    """
    Runs speed test on a list of .ovpn files concurrently.
    Returns a dict mapping filename -> RTT.
    """
    import os
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {}
        for file in file_list:
            full_path = os.path.join(config_dir, file)
            future = executor.submit(test_single_ovpn, full_path, timeout)
            future_to_file[future] = file

        for future in as_completed(future_to_file):
            file = future_to_file[future]
            try:
                rtt = future.result()
                results[file] = rtt
            except Exception as e:
                logger.error(f"Error testing {file}: {e}")
                results[file] = None
    return results
