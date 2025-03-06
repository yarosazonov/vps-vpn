from datetime import datetime
from typing import Dict, List, Optional
import sqlite3
import logging

from vpnmon.database import Database
from vpnmon.wireguard import WireGuard

logger = logging.getLogger(__name__)

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
                self.db.ensure_peer_exists(conn, peer['public_key'])
                self.db.store_measurement(conn, peer, current_month)  

        return True
    

            
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
    

    
    def update_info(self, public_key: str, name: str = None, email: str = None):
        """Update peer information. Delegates to database."""
        return self.db.update_peer_info(public_key, name, email)
    


    def delete_peer(self, email: str, keep_usage_history: bool = False) -> bool:
        """Delete all peers associated with specified email

        Args:
            email: Email address of the user to remove
        keep_usage_history: If True, keep usage history

        Returns:
            bool: True if all operations successful, False otherwise
        """

        # Find all public keys for this email
        public_keys = self.db.find_peers_by_email(email)

        if not public_keys:
            logger.warning(f"No peers found for email {email}")
            return False
        
        logger.info(f"Found {len(public_keys)} peers for email {email}")
    
        all_successful = True
        deleted_count = 0

        # Process each key
        for key in public_keys:
            logger.info(f"Attempting to remove peer {key}")
 
            # Remove from WireGuard
            wg_success = self.wireguard.remove_peer(key)
            
            # Remove from database
            db_success = self.db.delete_peer(key, keep_usage_history)

            if wg_success and db_success:
                logger.info(f"Successfully removed peer {key}")
                deleted_count += 1
            else:
                logger.error(f"Failed to completely remove peer {key}")
                all_successful = False
        
        logger.info(f"Deleted {deleted_count} of {len(public_keys)} peers for {email}")
        return all_successful and deleted_count > 0