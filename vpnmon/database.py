# database setup

from pathlib import Path
import sqlite3
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, data_dir: Path = Path("/var/log/wireguard-usage")):
        self.data_dir = data_dir
        self.db_file = data_dir / "usage.db"
        
    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def init_db(self):
        """Initialize database schema."""
        self._ensure_data_dir() # Make sure directory exists

        with sqlite3.connect(self.db_file) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS peers (
                    public_key TEXT PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    added_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS monthly_usage (
                    public_key TEXT,
                    year_month TEXT,
                    accumulated_received INTEGER,
                    accumulated_sent INTEGER,
                    last_received INTEGER,
                    last_sent INTEGER,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (public_key, year_month),
                    FOREIGN KEY (public_key) REFERENCES peers(public_key)
                )
            """)
    


    def ensure_peer_exists(self, conn, public_key):
        """Make sure the peer is in the peers table."""
        conn.execute(
        """
        INSERT OR IGNORE INTO peers (public_key)
        VALUES (?)
        """,
        (public_key,))



    def get_peer_usage(self, public_key: str = None, month: str = None):
        """Get usage statistics for one or all peers."""
        with sqlite3.connect(self.db_file) as conn:
            query = """
                SELECT 
                    m.public_key,
                    p.name,
                    m.year_month,
                    m.accumulated_received,
                    m.accumulated_sent,
                    m.last_updated
                FROM monthly_usage m
                LEFT JOIN peers p ON m.public_key = p.public_key
                WHERE 1=1
            """
            params = []
            
            if public_key:
                query += " AND m.public_key = ?"
                params.append(public_key)
            
            if month:
                query += " AND m.year_month = ?"
                params.append(month)
                
            query += " ORDER BY m.year_month DESC, m.last_updated DESC"
            
            return conn.execute(query, params).fetchall()
        


    def store_measurement(self, conn, peer_data, current_month):
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
            


    def update_peer_info(self, public_key: str, name: str = None, email: str = None):
            """Update peer information."""
            try:
                with sqlite3.connect(self.db_file) as conn:
                    # Check if peer exists
                    existing = conn.execute(
                        "SELECT 1 FROM peers WHERE public_key = ?", 
                        (public_key,)
                    ).fetchone()
                    
                    if existing:
                        # Update existing peer
                        print(f"Updating existing peer: {public_key}")
                        if name is not None or email is not None:
                            query = "UPDATE peers SET "
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
                        print(f"Inserting new peer: {public_key}, name: {name}, email: {email}")
                        conn.execute(
                            "INSERT INTO peers (public_key, name, email) VALUES (?, ?, ?)",
                            (public_key, name, email)
                        )
                        return True
                
                return False
            except Exception as e:
                print(f"Database error: {e}")
                import traceback
                traceback.print_exc()
                return False
        


    def find_peers_by_email(self, email: str) -> List[str]:
        """Find all public keys associated with a given email."""
        with sqlite3.connect(self.db_file) as conn:
            query = "SELECT public_key FROM peers WHERE email = ?"
            result = conn.execute(query, (email,)).fetchall()
            return [row[0] for row in result] # Extract public keys from result tuples
        


    def delete_peer(self, public_key: str, keep_usage_history: bool = False) -> bool:
        """Delete a peer from the database.
        
        Args:
            public_key: The public key of the peer to delete
            keep_usage_history: If True, keep usage records but remove peer info
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                # Start a transaction
                conn.execute("BEGIN TRANSACTION")

                # Delete from peers table
                conn.execute("DELETE FROM peers WHERE public_key = ?", (public_key,))

                # Optionally delete usage records
                if not keep_usage_history:
                    conn.execute("DELETE FROM monthly_usage WHERE public_key = ?", (public_key,))

                # Commit transaction
                conn.commit()
                return True
        except Exception as e:
            logger.exception(f"Error deleting peer {public_key} from database")
            return False                     
                