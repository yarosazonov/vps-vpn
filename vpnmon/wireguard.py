# Wireguard specific operations

import subprocess
from typing import List, Dict, Optional

class WireGuard:
    def __init__(self, interface: str = "wg0"):
        self.interface = interface

    def get_peer_data(self) -> List[Dict]:
        """Get current WireGuard statistics for all peers."""
        try:
            output = subprocess.check_output(
                ["sudo", "wg", "show", self.interface, "dump"],
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
            print(f"Error getting WireGuard data: {e}")
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
            print(f"Error generating WireGuard keys: {e}")
            print(f"Private key type: {type(private_key)}")
            return None

    def add_peer_to_config(self, public_key, allowed_ips, config_file="/etc/wireguard/wg0.conf"):
        """Dynamically add a peer to WireGuard and persist it in the config file."""
        try:
            # Apply the peer dynamically
            print(f"Attempting to set WireGuard peer: {public_key} with allowed IPs: {allowed_ips}")
            set_result = subprocess.run([
                "sudo", "wg", "set", self.interface, "peer", 
                public_key, "allowed-ips", allowed_ips
            ], check=False, capture_output=True, text=True)
            
            if set_result.returncode != 0:
                print(f"WireGuard set command failed: {set_result.stderr}")
                return False
            
            # Append to the configuration file for persistence using sudo
            print(f"Attempting to update config file: {config_file}")
            peer_config = f"\n[Peer]\nPublicKey = {public_key}\nAllowedIPs = {allowed_ips}\n"
            tee_result = subprocess.run(
                ["sudo", "tee", "-a", config_file], 
                input=peer_config, 
                check=False,
                capture_output=True,
                text=True
            )
            
            if tee_result.returncode != 0:
                print(f"Config file update failed: {tee_result.stderr}")
                return False
                
            print("Peer added successfully")
            return True
        except Exception as e:
            print(f"Error adding peer to config: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_next_ip(self, config_file="/etc/wireguard/wg0.conf"):
        """Get the next available IP address in the subnet."""
        try:
            # Read config file
            with open(config_file, 'r') as f:
                config = f.readlines()
                
            # Extract all AllowedIPs
            ips = []
            for line in config:
                if line.strip().startswith("AllowedIPs"):
                    # Extract IP from format like "AllowedIPs = 10.0.0.2/32"
                    ip_part = line.split("=")[1].strip()
                    ip = ip_part.split("/")[0].strip()
                    ips.append(ip)
            
            # Find the highest IP in the 10.0.0.x range
            highest = 1  # Start at 1 since .1 is usually the server
            for ip in ips:
                if ip.startswith("10.0.0."):
                    try:
                        num = int(ip.split(".")[-1])
                        if num > highest:
                            highest = num
                    except ValueError:
                        continue
                        
            # Return next IP
            return f"10.0.0.{highest + 1}/32"
        except Exception as e:
            print(f"Error finding next IP: {e}")
            return "10.0.0.2/32"  # Fallback to first client IP
        
    
    def get_server_public_key(self, config_file="/etc/wireguard/wg0.conf"):
        """Get the server's public key from the config file."""
        try:
            # with open(config_file, 'r') as f:
            #     config = f.readlines()
                
            # for line in config:
            #     if line.strip().startswith("PrivateKey"):
            #         private_key = line.split("=")[1].strip()
            #         public_key = subprocess.check_output(
            #             ["wg", "pubkey"], 
            #             input=private_key.encode(), 
            #             text=True
            #         ).strip()
            #         return public_key
                
            # Fallback: Get from interface directly
            output = subprocess.check_output(["wg", "show", self.interface, "public-key"], text=True)
            return output.strip()
        except Exception as e:
            print(f"Error getting server public key: {e}")
            return None
        
    

    def get_server_endpoint(self):
        """Get the server's public endpoint address."""
        try:
            # Get public IP from external service
            ip = subprocess.check_output(["curl", "-s", "https://api.ipify.org"], text=True).strip()
            
            # Get listening port from wg show
            output = subprocess.check_output(["wg", "show", self.interface], text=True)
            for line in output.split("\n"):
                if "listening port" in line:
                    port = line.split(":")[1].strip()
                    return f"{ip}:{port}"
                    
            return f"{ip}:51820"  # Default port if not found
        except Exception as e:
            print(f"Error getting server endpoint: {e}")
            return "95.179.186:51820"  # Fallback