# Created a wrapper script called vpnmon in (/usr/local/bin/)
#!/usr/bin/python3

import sys
import argparse
import re
import logging
from pathlib import Path
from tabulate import tabulate

script_dir = Path(__file__).parent
log_file = Path("/config/vpnmon.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also output to console
    ]
)

logger = logging.getLogger(__name__)

# Add parent directory to path so we can import vpnmon
sys.path.insert(0, str(Path(__file__).parent.parent))
from vpnmon.core import VPNMonitor



def setup_argparse():
    parser = argparse.ArgumentParser(description="Wireguard VPN Monitoring Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Initialize database")

    # Collect command
    collect_parser = subparsers.add_parser("collect", help="Collect current usage data")

    # Show usage command
    usage_parser = subparsers.add_parser("usage", help="Show usage statistics")
    usage_parser.add_argument("--month", help="Filter by month (YYYY-MM format)")
    usage_parser.add_argument("--peer", help="Filter by peer public key")
    usage_parser.add_argument("--accumulated", action="store_true", 
                            help="Show accumulated values instead of monthly-only usage")

    # Update a peer command
    peer_parser = subparsers.add_parser("update-peer", help="Update peer information")
    peer_parser.add_argument("public_key", help="Peer public key")
    peer_parser.add_argument("--name", help="Peer friendly name")
    peer_parser.add_argument("--email", help="Peer email address")

    # Generates a new peer
    def email_validator(email):
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise argparse.ArgumentTypeError(f"Invalid email format: {email}")
        return email
    
    generate_parser = subparsers.add_parser("generate-peer", help="Generate a new WireGuard peer")
    generate_parser.add_argument("name", help="User's name")
    generate_parser.add_argument("email", type=email_validator, help="User's email (required)")

    # Delete a peer by an email
    delete_parser = subparsers.add_parser("delete-peer", help="Deletes a peer by an email")
    delete_parser.add_argument("email", help="User's email for deletion")

    # Sync db and interface():
    sync_parser = subparsers.add_parser("sync", help="Sync database with WireGuard interface")
    sync_parser.add_argument("--fix", action="store_true", help="Automatically fix inconsistencies")

    return parser


def main():
    parser = setup_argparse()
    args = parser.parse_args()

    # Creating an object of a class VPNMonitor()
    monitor = VPNMonitor()

    if args.command == "setup":
        monitor.setup()
        print("Database initialized successfully")



    elif args.command == "collect":
        if monitor.collect_data():
            print("Data collected successfully")
        else:
            print("Failed to collect data")
    


    elif args.command == "usage":
        data = monitor.get_usage(args.peer, args.month, not args.accumulated)

        if not data:
            print("No data found")
            return
        
        # Change headers to indicate monthly or accumulated
        usage_type = "Accumulated" if args.accumulated else "Monthly"
        headers = ['Public Key', 'Name', 'Email', 'Month', 
                f'{usage_type} GB Received', f'{usage_type} GB Sent', 
                f'{usage_type} GB Total', 'Last Updated']
        
        table_data = [
            [
                d['public_key'], d['name'], d['email'], d['month'], 
                d['received_gb'], d['sent_gb'], d['total_gb'],
                d['last_updated']
            ] for d in data
        ]
        print(tabulate(table_data, headers=headers, tablefmt='grid'))



    elif args.command == "update-peer":
        if monitor.update_info(args.public_key, args.name, args.email):
            print(f"Peer {args.public_key} updated successfully")
        else:
            print(f"Failed to update peer {args.public_key}")
    


    elif args.command == "generate-peer":
        try:
            # Generate keys
            keys = monitor.wireguard.generate_keys()
            if not keys:
                print("Failed to generate WireGuard keys")
                sys.exit(1)

            # Get next available IP
            try:
                next_ip = monitor.wireguard.get_next_ip()
            except RuntimeError as e:
                print(f"Error: {e}")
                sys.exit(1)

            # Add to WireGuard config
            if not monitor.wireguard.add_peer_to_config(keys["public_key"], next_ip):
                print("Failed to add peer to WireGuard configuration")
                sys.exit(1)
            
            # Add user to database
            if not monitor.update_info(keys["public_key"], args.name, args.email):
                print("Failed to add user to database")
                sys.exit(1)
            
            # Create the client configuration
            server_pubkey = monitor.wireguard.get_server_public_key()
            server_endpoint = monitor.wireguard.get_server_endpoint()
            
            config = f"""[Interface]
PrivateKey = {keys['private_key']}
Address = {next_ip}
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = {server_pubkey}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {server_endpoint}
PersistentKeepalive = 25
        """
            
            # Create a safe filename from the name
            safe_name = args.name.replace(' ', '_').replace('/', '-')
            safe_name = ''.join(c for c in safe_name if c.isalnum() or c in '_-')
            
            # Create configs directory if it doesn't exist
            configs_dir = Path("/config/client_confs")
            configs_dir.mkdir(exist_ok=True)
            
            # Save the configuration to a file
            config_file = configs_dir / f"{safe_name}.conf"
            with open(config_file, "w") as f:
                f.write(config)
            
            # Show results to the user
            print("\nNew WireGuard Peer Generated\n")
            print(f"Name: {args.name}")
            print(f"Email: {args.email}")
            print(f"IP Address: {next_ip}")
            print(f"\nConfiguration saved to: {config_file}\n")
            print("Client Configuration:")
            print("---------------------")
            print(config)

        except Exception as e:
            print(f"Unexpected error: {e}")
            logger.exception("Error in generate-peer command")
            sys.exit(1)



    elif args.command == "delete-peer":
        print(f"Attempting to delete peers for email: {args.email}")
        if monitor.delete_peer(args.email):
            print(f"Successfully deleted peers for {args.email}")
        else:
            print(f"Failed to delete all peers for {args.email}. Check logs for details.")



    elif args.command == "sync":
        print("Checking for inconsistencies between WireGuard and database...")
        result = monitor.sync_database_with_interface(auto_fix=args.fix)
        
        if not result['missing_in_db'] and not result['missing_in_wg']:
            print("✓ WireGuard and database are in sync!")
            print(f"  • {result['peers_in_wg']} peers found in both systems")
        else:
            print("! Found inconsistencies:")
            
            if result['missing_in_db']:
                print(f"  • {len(result['missing_in_db'])} peers in WireGuard but missing from database:")
                for key in result['missing_in_db']:
                    print(f"    - {key}")
                    
            if result['missing_in_wg']:
                print(f"  • {len(result['missing_in_wg'])} peers in database but missing from WireGuard:")
                for key in result['missing_in_wg']:
                    print(f"    - {key}")
            
            if args.fix:
                print(f"\n✓ Fixed {result['fixed_count']} inconsistencies")
            else:
                print("\nRun with --fix to automatically resolve these inconsistencies")



    else:
        parser.print_help()



if __name__ == "__main__":
    main()