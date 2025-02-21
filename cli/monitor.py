# Created a wrapper script called vpnmon in (/usr/local/bin/)
#!/opt/vpn-monitor/venv/bin/python3

import sys
import argparse
from pathlib import Path
from tabulate import tabulate

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

    # Update peer command
    peer_parser = subparsers.add_parser("update-peer", help="Update peer information")
    peer_parser.add_argument("public_key", help="Peer public key")
    peer_parser.add_argument("--name", help="Peer friendly name")
    peer_parser.add_argument("--email", help="Peer email address")

    return parser

def main():
    parser = setup_argparse()
    args = parser.parse_args()

    monitor = VPNMonitor()

    if args.command == "setup":
        monitor.setup()
        print("Database intialized successfully")

    elif args.command == "collect":
        if monitor.collect_data():
            print("Data collected successfully")
        else:
            print("Failed to collect data")
    
    elif args.command == "usage":
        data = monitor.get_usage(args.peer, args.month)

        if not data:
            print("No data found")
            return
        
        headers = ['Public Key', 'Name', 'Month', 'MB Received', 'MB Sent', 'MB Total', 'Last Updated']
        table_data = [
            [
                d['public_key'], d['name'], d['month'], 
                d['received_mb'], d['sent_mb'], d['total_mb'],
                d['last_updated']
            ] for d in data
        ]
        print(tabulate(table_data, headers=headers, tablefmt='grid'))

    elif args.command == "update-peer":
        if monitor.update_peer_info(args.public_key, args.name, args.email):
            print(f"Peer {args.public_key} updated successfully")
        else:
            print(f"Failed to update peer {args.public_key}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()