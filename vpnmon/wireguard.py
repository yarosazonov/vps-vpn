import subprocess
from typing import List, Dict, Optional

class WireGuard:
    def __init__(self, interface: str = "wg0"):
        self.interface = interface

    def get_peer_data(self) -> List[Dict]:
        """Get current WireGuard statistics for all peers."""
        try:
            output = subprocess.check_output(
                ["wg", "show", self.interface, "dump"],
                text=True
            )
            peers = []

            for line in output.strip().split('\n')[1:]:
                parts = line.split('\t')
                if len(parts) >= 7:
                    peers.append({
                        'public_key': parts[0],
                        'received': int(parts[5]),
                        'sent': int(parts[6]),
                        'total': int(parts[5]) + int(parts[6])
                    })
            return peers
        except subprocess.CalledProcessError as e:
            print(f"Error getting WireGuard data: {e}")
            return []