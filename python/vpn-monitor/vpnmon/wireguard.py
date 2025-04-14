# Wireguard specific operations

import subprocess
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class WireGuard:
    def __init__(self, interface: str = None):
        self.interface = interface or os.environ.get("WG_INTERFACE", "wg0")

        # Get the base config directory
        base_config_dir = os.environ.get("WG_CONFIG_DIR", "/config")
        
        # Set path to wg_confs subdirectory
        self.config_dir = os.path.join(base_config_dir, "wg_confs")
        self.config_file = os.path.join(self.config_dir, f"{self.interface}.conf")

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
            logger.exception("Error getting WireGuard data")
            return []
        



    def generate_keys(self):
        """Generate a new WireGuard key pair."""
        try:
            # Generate private key
            private_key = subprocess.check_output(["wg", "genkey"], text=True).strip()
            # Derive public key from private key
            public_key = subprocess.check_output(["wg", "pubkey"], input=private_key, text=True).strip()

            return {
                "private_key": private_key,
                "public_key": public_key
            }
        except subprocess.CalledProcessError as e:
            logger.exception("Error generating WireGuard keys")
            return None




    def add_peer_to_config(self, public_key, allowed_ips, config_file=None):
        """Dynamically add a peer to WireGuard and persist it in the config file."""
        try:
            # Use the instance config_file if none provided

            config_file = config_file or self.config_file
            # Apply the peer dynamically
            logger.info(f"Attempting to set WireGuard peer: {public_key} with allowed IPs: {allowed_ips}")
            set_result = subprocess.run([
                "wg", "set", self.interface, "peer", 
                public_key, "allowed-ips", allowed_ips
            ], check=False, capture_output=True, text=True)
            
            if set_result.returncode != 0:
                logger.error(f"WireGuard set command failed: {set_result.stderr}")
                return False
            
            # Append to the configuration file for persistence 
            logger.info(f"Attempting to update config file: {config_file}")
            peer_config = f"\n[Peer]\nPublicKey = {public_key}\nAllowedIPs = {allowed_ips}\n"
            tee_result = subprocess.run(
                ["tee", "-a", config_file], 
                input=peer_config, 
                check=False,
                capture_output=True,
                text=True
            )
            
            if tee_result.returncode != 0:
                logger.error(f"Config file update failed: {tee_result.stderr}")
                return False
                
            logger.info("Peer added successfully")    
            return True
        except Exception as e:
            logger.exception("Error adding peer to config")
            return False
    


    def get_next_ip(self, config_file=None):
        """Get the next available IP address in the subnet."""
        try:
            # Use the instance config_file if none provided
            config_file = config_file or self.config_file
            logger.info(f"Finding next available IP from {config_file}")

            # Get the subnet from environment or default to 10.0.1
            subnet_base = os.environ.get("WG_SUBNET_BASE", "10.0.1")

            # Read config file using
            read_result = subprocess.run(
                ["cat", config_file],
                check=True, 
                capture_output=True, 
                text=True
            )
            config_lines = read_result.stdout.splitlines()
                
            # Extract all AllowedIPs
            used_ips = set()
            for line in config_lines:
                if line.strip().startswith("AllowedIPs"):
                    # Extract IP from format like "AllowedIPs = 10.0.1.2/32"
                    ip_part = line.split("=")[1].strip()
                    ip = ip_part.split("/")[0].strip()
                    if ip.startswith(f"{subnet_base}."):
                        used_ips.add(ip)
            
            # Find the first available IP starting from x.x.x.2
            # (x.x.x.1 is typically the server)
            for i in range(2, 255):
                candidate_ip = f"{subnet_base}.{i}"
                if candidate_ip not in used_ips:
                    next_ip = f"{candidate_ip}/32"
                    logger.info(f"Found available IP: {next_ip}")
                    return next_ip
                        
            # If we get here, all IPs are taken (unlikely)
            logger.error(f"No available IPs in the {subnet_base}.x range")
            raise RuntimeError("No available IPs in subnet - all 253 addresses are in use")
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Error accessing config file: {e}")
            raise RuntimeError("Cannot determine next available IP - permission denied")
        except Exception as e:
            logger.exception(f"Error finding next IP")
            raise RuntimeError("Cannot determine next available IP")
        
    

    def get_server_public_key(self, config_file=None):
        """Get the server's public key from the config file."""
        try:   
             # Use the instance config_file if none provided
            config_file = config_file or self.config_file

            # Get the public key
            output = subprocess.check_output(
                ["wg", "show", self.interface, "public-key"], 
                text=True
            )
            return output.strip()
        except Exception as e:
            logger.exception("Error getting server public key")
            return None
        
    

    def get_server_endpoint(self):
        """Get the server's public endpoint address."""
        try:
            # Get public IP from external service
            ip = subprocess.check_output(["curl", "-s", "https://api.ipify.org"], text=True).strip()
            
            # Get port from environment variable or WireGuard
            port = os.environ.get("SERVER_PORT")
            
            if not port:
                # Try to get from WireGuard if not in environment
                output = subprocess.check_output(
                    ["wg", "show", self.interface], 
                    text=True
                )
                for line in output.split("\n"):
                    if "listening port" in line:
                        port = line.split(":")[1].strip()
                        break

            # Use default if still not found        
            if not port:
                port = "51820"  # Default port if not found
            
            return f"{ip}:{port}"
        except Exception as e:
            logger.exception("Error getting server endpoint")
            # Use environment variable in fallback too
            port = os.environ.get("SERVER_PORT", "53")
            return f"95.179.186.138:{port}"  # Fallback with configurable port
        


    def _remove_peer_from_interface(self, public_key):
        """Dynamically remove a peer from WireGuard interface."""
        try:
            # Apply the peer dynamically
            logger.info(f"Attempting to remove a WireGuard peer: {public_key}")
            set_result = subprocess.run([
                "wg", "set", self.interface, "peer", public_key, "remove"
            ], check=False, capture_output=True, text=True)

            if set_result.returncode != 0:
                logger.error(f"WireGuard set command failed: {set_result.stderr}")
                return False
            
            logger.info(f"Peer removed from a {self.interface} interface successfully")
            return True
        except Exception as e:
            logger.exception("Error removing a peer from interface")
            return False



    def _restore_config_from_backup(self, path_to_conf, path_to_backup):
        """Restore configuration from backup if something goes wrong."""
        try:
            logger.warning(f"Attempting to restore {self.interface}.conf from backup")
            restore_result = subprocess.run([
                "cp", "-f", path_to_backup, path_to_conf
            ], check=False, capture_output=True, text=True)
            
            if restore_result.returncode != 0:
                logger.error(f"Failed to restore from backup: {restore_result.stderr}")
                return False
                
            logger.info(f"Successfully restored {self.interface}.conf from backup")
            return True
        except Exception as e:
            logger.exception(f"Error restoring from backup")
            return False



    def _remove_peer_from_config(self, public_key):
        """Remove peer from .conf file"""
        # Path to .conf
        path_to_conf = Path(self.config_file)
        # single backup setup
        path_to_backup = Path(f"{self.config_file}_backup_")

        # Check if file exists
        try:
            subprocess.run(
                ["test", "-f", str(path_to_conf)], 
                check=True, 
                stderr=subprocess.PIPE
            )
            logger.info("Config found")
        except subprocess.CalledProcessError:
            logger.error(f"Configuration file {path_to_conf} does not exist or is not accessible")
            return False

        try:
            # Attempting to make a backup of .conf
            logger.info("Attempt on backup creation")
            make_backup = subprocess.run([
                "cp", path_to_conf, "-p", path_to_backup
            ], check=False, capture_output=True, text=True)

            if make_backup.returncode != 0:
                logger.error(f"{self.interface} backup failed: {make_backup.stderr}")
                return False

            logger.info(f"{self.interface} backup created successfully")
        except Exception as e:
            logger.exception("Error creating backup")
            return False
        
        # Editing .conf 
        try:
            logger.info(f"Parsing .conf for a peer")
            read_conf = subprocess.run([
                "cat", path_to_conf
            ], check=False, capture_output=True, text=True)
            conf_lines = read_conf.stdout.split("\n")

           

            # Parse config file
            keep_lines = []
            peer_lines = []
            in_peer_section = False
            skip_current_peer = False
            found_peer = False
            
            for line in conf_lines:
                # Start of a new section
                if line.strip().startswith('['):
                    if in_peer_section and not skip_current_peer:
                        # Add the previous peer section if it wasn't skipped
                        keep_lines.append('[Peer]')
                        keep_lines.extend(peer_lines)

                    # Reset for new section
                    if line.strip() == '[Peer]':
                        in_peer_section = True
                        skip_current_peer = False
                        peer_lines = [] # Store peer lines temporarily
                    else:
                        # Non-peer section, add directly
                        in_peer_section = False
                        keep_lines.append(line)
                
                elif in_peer_section:
                    # Check if this is the peer we want to remove
                    if line.strip().startswith('PublicKey') and public_key in line:
                        skip_current_peer = True
                        found_peer = True

                    # Store the lines for this peer
                    if not skip_current_peer:
                        peer_lines.append(line)
                
                else:
                    # Not in a peer section, add directly
                    keep_lines.append(line)

            # Don't forget to add the last peer section if it exists and wasn't skipped
            if in_peer_section and not skip_current_peer:
                keep_lines.append('[Peer]')
                keep_lines.extend(peer_lines)

            if not found_peer:
                logger.warning(f"Public key {public_key} not found in configuration")

        except Exception as e:
            logger.exception(f"Error editing {path_to_conf}")
            self._restore_config_from_backup(path_to_conf, path_to_backup)
            return False
            
        # Join the kept lines back into a single string with newlines
        modified_content = '\n'.join(keep_lines)

        # Write the modified content back to the config file
        try:
            logger.info(f"Writing modified configuration to {path_to_conf}")
            write_result = subprocess.run(
                ["tee", path_to_conf], 
                input=modified_content, 
                check=False,
                capture_output=True,
                text=True
            )
            
            if write_result.returncode != 0:
                logger.error(f"Failed to write modified config: {write_result.stderr}")
                return False
                
            logger.info(f"Successfully removed peer from {path_to_conf}")
            return True
        except Exception as e:
            logger.exception(f"Error writing to {path_to_conf}")
            self._restore_config_from_backup(path_to_conf, path_to_backup)
            return False


    def remove_peer(self, public_key):
        """Remove a peer from both the WireGuard interface and configuration file"""
        
        # First try to remove from interface
        interface_success = self._remove_peer_from_interface(public_key)
        if not interface_success:
            logger.error(f"Failed to remove peer from interface")
            # Continue to config removal despite interface failure
        
        # Then remove from config file
        config_success = self._remove_peer_from_config(public_key)
        if not config_success:
            logger.error(f"Failed to remove peer from configuration file")
            return False
        
        # Determine overall success
        if interface_success and config_success:
            logger.info(f"Successfully removed peer {public_key}")
            return True
        else:
            logger.warning(f"Partial success removing peer {public_key} - " +
                        f"Interface: {'Success' if interface_success else 'Failed'}, " +
                        f"Config: {'Success' if config_success else 'Failed'}")
            return False
