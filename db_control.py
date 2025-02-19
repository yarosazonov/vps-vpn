#!/opt/vpn-monitor/venv/bin/python3

import sqlite3
import sys
from pathlib import Path
from tabulate import tabulate

# Constants
DATA_DIR = Path("/var/log/wireguard-usage")
DB_FILE = DATA_DIR / "usage.db"
ACTIONS = 'view-peers, view-usage, drop'

def view_peers():
    """Display all registered peers."""
    with sqlite3.connect(DB_FILE) as conn:
        data = conn.execute("""
            SELECT 
                public_key,
                name,
                email,
                datetime(added_on, 'localtime') as added_on
            FROM peers 
            ORDER BY added_on DESC
        """).fetchall()
        
        headers = ['Public Key', 'Name', 'Email', 'Added On']
        print(tabulate(data, headers=headers, tablefmt='grid'))

def view_usage():
    """Display monthly usage for all peers."""
    with sqlite3.connect(DB_FILE) as conn:
        data = conn.execute("""
            SELECT 
                m.public_key,
                p.name,
                m.year_month,
                ROUND(m.accumulated_received/1024.0/1024.0, 2) as mb_received,
                ROUND(m.accumulated_sent/1024.0/1024.0, 2) as mb_sent,
                ROUND((m.accumulated_received + m.accumulated_sent)/1024.0/1024.0, 2) as mb_total,
                datetime(m.last_updated, 'localtime') as last_updated
            FROM monthly_usage m
            LEFT JOIN peers p ON m.public_key = p.public_key
            ORDER BY m.year_month DESC, m.last_updated DESC
        """).fetchall()
        
        headers = ['Public Key', 'Name', 'Month', 'MB Received', 'MB Sent', 'MB Total', 'Last Updated']
        print(tabulate(data, headers=headers, tablefmt='grid'))

def drop_table():
    """Drop specified table"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print("No tables found in the database.")
            return
        
        print("Tables in the database:")
        for table in tables:
            print(table[0])

        table_to_drop = input("Enter the name of the table to drop: ").strip()

        if (table_to_drop,) not in tables:
            print(f"Table '{table_to_drop}' does not exist.")
            return
        
        confirm = input(f"Are you sure you want to drop the table '{table_to_drop}'? (y/n): ").strip().lower()
        if confirm == 'y':
            cursor.execute(f"DROP TABLE {table_to_drop};")
            print(f"Table '{table_to_drop}' dropped successfully.")
        else:
            print("Operation canceled.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f'Usage: python {sys.argv[0]} action({ACTIONS})')
    else:
        if sys.argv[1] == 'view-peers':
            view_peers()
        elif sys.argv[1] == 'view-usage':
            view_usage()
        elif sys.argv[1] == 'drop':
            drop_table()
        else:
            print(f'actions available: {ACTIONS}')