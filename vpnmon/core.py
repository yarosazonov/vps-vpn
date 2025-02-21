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
            """
            SELECT accumulated_received, accumulated_sent,
                last_received, last_sent
            FROM monthly_usage
            WHERE public_key = ? AND year_month = ?
            """, (peer_data['public_key'], current_month)).fetchone()
        
        if last:
            # Check for counter reset
            if peer_data['received'] < last[2] or peer_data['sent'] < last[3]:
                # Counter reset - add new value to accumulated
                new_accumulated_received = last[0] + peer_data['received']
                new_accumulated_sent = last[1] + peer_data['sent']
            else:
                # Normal case - add the difference
                received_diff = peer_data['received'] - last[2]
                sent_diff = peer_data['sent'] - last[3]
                # Ask why do I need max() here
                new_accumulated_received = last[0] + max(0, received_diff)
                new_accumulated_sent = last[1] + max(0, sent_diff)

            conn.execute(
                """
                UPDATE monthly_usage
                SET accumulated_received = ?,
                    accumulated_sent = ?,
                    last_received = ?,
                    last_sent = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE public_key = ? AND year_month = ?
                    """, (new_accumulated_received, new_accumulated_sent, 
                        peer_data['received'], peer_data['sent'],
                        peer_data['public_key'], current_month))
        else:
            # First measurement for this month
            conn.execute(
                """
                INSERT INTO monthly_usage 
                (public_key, year_month, accumulated_received, accumulated_sent,
                 last_received, last_sent)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (peer_data['public_key'], current_month,
                  peer_data['received'], peer_data['sent'],
                  peer_data['received'], peer_data['sent']))
            
    def get_usage(self, public_key: str = None, month: str = None):
        """Get formatted usage data."""
        raw_data = self.db.get_peer_usage(public_key, month)
        formatted_data = []

        for row in raw_data:
            received_mb = round(row[3] / 1024 / 1024, 2)
            sent_mb = round(row[4] / 1024 / 1024, 2)
            total_mb = round((row[3] + row[4]) / 1024 / 1024, 2)

            formatted_data.append({
                'public_key': row[0],
                'name': row[1] or 'Unknown',
                'month': row[2],
                'received_mb': received_mb,
                'sent_mb': sent_mb,
                'total_mb': total_mb,
                'last_updated': row[5]
            })
        return formatted_data
    
    def update_peer_info(self, public_key: str, name: str = None, email: str = None):
        """Update peer information."""
        with sqlite3.connect(self.db.db_file) as conn:
            # Check if peer exists
            existing = conn.execute(
                "SELECT 1 FROM peers WHERE public_key = ?",
                (public_key,)
            ).fetchone()

            if existing:
                # Update existing peer
                if name is not None or email is not None:
                    query = "UPDATE peer SET "
                    params = []
                    updates = []

                    if name is not None:
                        updates.append("name = ?")
                        params.append(name)

                    if email is not None:
                        updates.append("email = ?")
                        params.append(email)
                    
                    query += ", ".join(updates)
                    query += " WHERE public_key = ?"
                    params.append(public_key)

                    conn.execute(query, params)
                    return True 
                else:
                    # Insert new peer
                    conn.execute(
                        "INSET INTO peers (public_key, name, email) VALUES (?, ?, ?)",
                        (public_key, name, email)
                    )
                    return True
                    
            return False