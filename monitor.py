#!/usr/bin/env python3 

import sqlite3
import subprocess
import datetime
import click
from pathlib import Path
from tabulate import tabulate

# Constants
DATA_DIR = Path("/var/log/wireguard-usage")
DB_FILE = DATA_DIR / "usage.db"
INTERFACE = "wg0"

def setup_database():
    """Initialize the SQLite database."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(DB_FILE) as conn:
        # Table for peer information
        conn.execute("""
            CREATE TABLE IF NOT EXISTS peers (
                public_key TEXT PRIMARY KEY,
                name TEXT,              -- Friendly name for the peer
                email TEXT,             -- Optional contact
                added_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table for monthly usage
        conn.execute("""
            CREATE TABLE IF NOT EXISTS monthly_usage (
                public_key TEXT,
                year_month TEXT,        -- Format: YYYY-MM
                accumulated_received INTEGER,
                accumulated_sent INTEGER,
                last_received INTEGER,
                last_sent INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (public_key, year_month),
                FOREIGN KEY (public_key) REFERENCES peers(public_key)
            )
        """)




def get_wireguard_data():
    """Collect current WireGuard statistics."""
    try:
        # Run 'wg show wg0 dump' command and get output
        output = subprocess.check_output(["wg", "show", INTERFACE, "dump"], text=True)
        peers = []
        
        # Skip first line (interface info) and process each peer
        for line in output.strip().split('\n')[1:]:
            parts = line.split('\t')
            if len(parts) >= 7:  # Ensure we have enough fields
                peers.append({
                    'public_key': parts[0],
                    'received': int(parts[5]),
                    'sent': int(parts[6]),
                    'total': int(parts[5]) + int(parts[6])
                })
        return peers
    except subprocess.CalledProcessError as e:
        click.echo(f"Error getting WireGuard data: {e}", err=True)
        return []



def store_measurement(conn, peer_data):
    """Update peer usage, handling counter resets."""
    last = conn.execute("""
        SELECT accumulated_received, accumulated_sent,
               last_received, last_sent
        FROM peer_usage 
        WHERE public_key = ?
    """, (peer_data['public_key'],)).fetchone()

    if last:
        # Calculate deltas
        received_delta = peer_data['received'] - last[2]  # current - last_received
        sent_delta = peer_data['sent'] - last[3]         # current - last_sent
        
        # If deltas are negative (counter reset), add current values
        new_accumulated_received = last[0] + (received_delta if received_delta > 0 else peer_data['received'])
        new_accumulated_sent = last[1] + (sent_delta if sent_delta > 0 else peer_data['sent'])
        
        conn.execute("""
            UPDATE peer_usage 
            SET accumulated_received = ?,
                accumulated_sent = ?,
                last_received = ?,
                last_sent = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE public_key = ?
        """, (new_accumulated_received, new_accumulated_sent,
              peer_data['received'], peer_data['sent'],
              peer_data['public_key']))
    else:
        # First time seeing this peer
        conn.execute("""
            INSERT INTO peer_usage 
            (public_key, accumulated_received, accumulated_sent,
             last_received, last_sent)
            VALUES (?, ?, ?, ?, ?)
        """, (peer_data['public_key'], peer_data['received'],
              peer_data['sent'], peer_data['received'], peer_data['sent']))



# Test code
if __name__ == "__main__":
    setup_database()
    print("Database setup complete")
    
    peers = get_wireguard_data()
    if peers:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            
            for peer in peers:
                store_measurement(conn, peer)
                
                # Get peer data including first seen time
                peer_data = conn.execute("""
                    SELECT 
                        accumulated_received/1024/1024 as mb_received,
                        accumulated_sent/1024/1024 as mb_sent,
                        (accumulated_received + accumulated_sent)/1024/1024 as mb_total,
                        (strftime('%s', 'now') - strftime('%s', last_updated)) as seconds_elapsed
                    FROM peer_usage 
                    WHERE public_key = ?
                """, (peer['public_key'],)).fetchone()
                
                if peer_data:
                    print(f"\nPeer: {peer['public_key']}")
                    print(f"  Accumulated Received: {peer_data['mb_received']:.2f} MB")
                    print(f"  Accumulated Sent: {peer_data['mb_sent']:.2f} MB")
                    print(f"  Accumulated Total: {peer_data['mb_total']:.2f} MB")
                