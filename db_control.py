#!/usr/bin/env python3

import sqlite3
from pathlib import Path
from tabulate import tabulate

# Constants (same as in monitor.py)
DATA_DIR = Path("/var/log/wireguard-usage")
DB_FILE = DATA_DIR / "usage.db"

def view_all_measurements():
   """Display all peer usage data in a formatted table."""
   with sqlite3.connect(DB_FILE) as conn:
       data = conn.execute("""
           SELECT 
               public_key,
               datetime(last_updated, 'localtime') as last_updated,
               ROUND(accumulated_received/1024.0/1024.0, 2) as mb_received,
               ROUND(accumulated_sent/1024.0/1024.0, 2) as mb_sent,
               ROUND((accumulated_received + accumulated_sent)/1024.0/1024.0, 2) as mb_total,
               ROUND(last_received/1024.0/1024.0, 2) as last_counter_received,
               ROUND(last_sent/1024.0/1024.0, 2) as last_counter_sent
           FROM peer_usage 
           ORDER BY last_updated DESC
       """).fetchall()
       
       headers = [
           'Public Key', 
           'Last Updated', 
           'Total MB Received', 
           'Total MB Sent', 
           'Total MB',
           'Last Received',
           'Last Sent'
       ]
       print(tabulate(data, headers=headers, tablefmt='grid'))



def drop_table():
    """Drop specified table"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # Get a list of all tables in the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print("No tables found in the database.")
            return
        
        print("Tables in the database:")
        for table in tables:
            print(table[0])

        # Ask the user to input the table name to drop
        table_to_drop = input("Enter the name of the table to drop: ").strip()

        # Check if the table exists
        if (table_to_drop,) not in tables:
            print(f"Table '{table_to_drop}' does not exist.")
            return
        
        # Confirm before dropping the table
        confirm = input(f"Are you sure you want to drop the table '{table_to_drop}'? (y/n): ").strip().lower()
        if confirm == 'y':
            cursor.execute(f"DROP TABLE {table_to_drop};")
            print(f"Table '{table_to_drop}' dropped successfully.")
        else:
            print("Operation canceled.")

if __name__ == "__main__":
    view_all_measurements()
    # drop_table()