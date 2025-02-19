from datetime import datetime
from typing import Dict, List, Optional
import sqlite3

from vpnmon.database import Database
from vpnmon.wireguard import WireGuard

class VPNMonitor:
    def __init__(self, interface: str = "wg0", data_dir = None):
        self.wireguard = WireGuard(interface)
        self.db = Database(data_dir) if data_dir else Database()

    def setup(self):
        """Initialize database and any required setup."""
        self.db.init_db()

    def collect_data(self):
        """Collect current data from WireGuard and store in database."""
        peers = self.wireguard.get_peer_data()
        if not peers:
            return False
        
        current_month = datetime.now().strftime('%Y-%m')

        with sqlite3.connect(self.db.db_file) as conn:
            for peer in peers:
                self._ensure_peer_exists(conn, peer['public_key'])
                self._store_measurement(conn, peer, current_month)

        return True
    
    def _ensure_peer_exists(self, conn, public_key):
        """Make sure the peer is in the peers table."""
        conn.execute(
        """
        INSERT OR IGNORE INTO peers (public_key)
        VALUES (?)
        """,
        (public_key,))

    def _store_measurement(self, conn, peer_data, current_month):
        """Store monthly usage data for a peer."""
        last = conn.execute(
            """SELECT"""
        )