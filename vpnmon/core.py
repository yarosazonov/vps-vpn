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
            received_mb = round(row[4] / 1024 / 1024, 2)
            sent_mb = round(row[5] / 1024 / 1024, 2)
            total_mb = round((row[4] + row[5]) / 1024 / 1024, 2)

            formatted_data.append({
                'public_key': row[0],
                'name': row[1] or 'Unknown',
                'email': row[2] or 'Unknown',
                'month': row[3],
                'received_mb': received_mb,
                'sent_mb': sent_mb,
                'total_mb': total_mb,
                'last_updated': row[6]
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
    
        successful_count = 0
        total_count = len(public_keys)
        
        # Process each peer individually
        for key in public_keys:
            logger.info(f"Attempting to remove peer {key}")
            
            # Try to remove from WireGuard
            wg_success = self.wireguard.remove_peer(key)
            
            if wg_success:
                # Only update database if WireGuard operation succeeded
                if self.db.delete_peer(key, keep_usage_history):
                    successful_count += 1
                else:
                    logger.error(f"Removed from WireGuard but failed to delete from database: {key}")
            else:
                logger.error(f"Failed to remove peer {key} from WireGuard, database unchanged")
        
        logger.info(f"Deleted {successful_count} of {total_count} peers for {email}")
        return successful_count > 0
    


    def sync_database_with_interface(self, auto_fix=False):
        """Verify and optionally fix inconsistencies between WireGuard and database
        
        Args:
            auto_fix: If True, automatically resolve incosistencies

        Returns:
            Dict with counts of inconsistencies and resolved issues
        """ 
        logger.info("Starting sync between WireGuard interface and database")

        # Get active peers from WireGUard
        wg_peers = self.wireguard.get_peer_data()
        wg_keys = set(peer['public_key'] for peer in wg_peers)

        # Get all peers from database
        with sqlite3.connect(self.db.db_file) as conn:
            db_peers = conn.execute("SELECT public_key FROM peers").fetchall()
        db_keys = set(peer[0] for peer in db_peers)

        # Find inconsistencies
        missing_in_db = wg_keys - db_keys
        missing_in_wg = db_keys - wg_keys

        result = {
            'peers_in_wg': len(wg_keys),
            'peers_in_db': len(db_keys),
            'missing_in_db': list(missing_in_db),
            'missing_in_wg': list(missing_in_wg),
            'fixed_count': 0
        }

        # Handle auto_fix if requested
        if auto_fix:
            # Add missing peers to database
            for key in missing_in_db:
                logger.info(f"Adding missing peer {key} to database")
                self.db.update_peer_info(key, name=f"Auto-added {key[:8]}")
                result['fixed_count'] += 1

            # Remove database entries for peers not in WireGuard
            for key in missing_in_wg:
                logger.info(f"Removing peer {key} from database")
                self.db.delete_peer(key)
                result['fixed_count'] += 1

        logger.info(f"Sync completed. Found {len(missing_in_db)} peers missing in DB, " + 
                f"{len(missing_in_wg)} peers missing in WireGuard")
                
        return result