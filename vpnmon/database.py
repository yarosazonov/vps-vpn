from pathlib import Path
import sqlite3
from datetime import datetime

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
    