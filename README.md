# Hello, this is a backend toolset for WireGuard in Python

## Architecture

The VPN Monitor system follows a modular architecture with three distinct layers:

### Interface Layer
- **CLI Module**: Handles command-line interactions for administration
- **Web Interface**: Provides a browser-based dashboard for monitoring 

### Core Logic Layer
- **VPN Monitoring Core**: Orchestrates application functions and business logic
- **WireGuard Interface**: Manages direct interactions with the WireGuard VPN service
- **Scheduler**: Performs automated data collection at regular intervals

### Data Layer
- **Database Management**: Tracks peer information and usage statistics
- **Configuration Management**: Handles VPN configuration files

### Directory Structure

```
.
├── README.md
├── Dockerfile             # Container definition
├── docker-compose.yml     # Container orchestration
├── requirements.txt       # Python dependencies
└── vpn-monitor
    ├── cli
    │   ├── configs        # CLI configuration files
    │   ├── monitor.py     # Main CLI interface
    │   └── vpnmon.log     # CLI log file
    ├── vpnmon
    │   ├── core.py        # Core application logic
    │   ├── database.py    # Database operations
    │   ├── vpnmon_scheduler.py # Automated collection
    │   └── wireguard.py   # WireGuard-specific operations
    └── web
        ├── app.py         # Web server application
        └── templates
            ├── index.html # Web interface landing page
            └── usage.html # Usage display page
```

## Command Line Interface

The VPN Monitor CLI provides a comprehensive set of commands for system management.

### Basic Commands

- `setup` - Initialize database and system
- `collect` - Collect current VPN usage data
- `usage` - Display usage statistics
- `sync` - Ensure database and WireGuard configuration are synchronized

### Peer Management

- `generate-peer` - Generate a new WireGuard peer configuration
- `update-peer` - Update peer information
- `delete-peer` - Remove a peer

### Usage Examples

#### Initialize System

```bash
docker exec -it wireguard-monitor /opt/venv/bin/python3 /app/cli/monitor.py setup
```

#### Collect Usage Data

```bash
docker exec -it wireguard-monitor /opt/venv/bin/python3 /app/cli/monitor.py collect
```

#### View Usage Statistics

```bash
# View all usage
docker exec -it wireguard-monitor /opt/venv/bin/python3 /app/cli/monitor.py usage

# Filter by month
docker exec -it wireguard-monitor /opt/venv/bin/python3 /app/cli/monitor.py usage --month 2025-04

# Filter by peer
docker exec -it wireguard-monitor /opt/venv/bin/python3 /app/cli/monitor.py usage --peer <public-key>

# Show accumulated data instead of monthly
docker exec -it wireguard-monitor /opt/venv/bin/python3 /app/cli/monitor.py usage --accumulated
```

#### Generate a New Peer

```bash
docker exec -it wireguard-monitor /opt/venv/bin/python3 /app/cli/monitor.py generate-peer "John Doe" john.doe@example.com
```

#### Update Peer Information

```bash
docker exec -it wireguard-monitor /opt/venv/bin/python3 /app/cli/monitor.py update-peer <public-key> --name "New Name" --email "new.email@example.com"
```

#### Delete a Peer

```bash
docker exec -it wireguard-monitor /opt/venv/bin/python3 /app/cli/monitor.py delete-peer user@example.com
```

#### Synchronize Database with WireGuard

```bash
# Check for inconsistencies
docker exec -it wireguard-monitor /opt/venv/bin/python3 /app/cli/monitor.py sync

# Fix inconsistencies automatically
docker exec -it wireguard-monitor /opt/venv/bin/python3 /app/cli/monitor.py sync --fix
```

## Database Structure

The VPN Monitor system uses SQLite for data storage. The database contains two main tables:

### Peers Table

Stores information about WireGuard peers.

| Column | Type | Description |
|--------|------|-------------|
| public_key | TEXT | Primary key, WireGuard public key |
| name | TEXT | Peer's friendly name |
| email | TEXT | Peer's email address |
| added_on | TIMESTAMP | When the peer was added |

### Monthly Usage Table

Stores usage statistics aggregated by month.

| Column | Type | Description |
|--------|------|-------------|
| public_key | TEXT | WireGuard public key (foreign key) |
| year_month | TEXT | Month of data collection (YYYY-MM) |
| accumulated_received | INTEGER | Total bytes received |
| accumulated_sent | INTEGER | Total bytes sent |
| last_received | INTEGER | Last received counter value |
| last_sent | INTEGER | Last sent counter value |
| last_updated | TIMESTAMP | When the data was last updated |

The primary key is a composite of (public_key, year_month).

## API Python

### Core Module (`core.py`)

The `VPNMonitor` class provides the following methods:

- **`setup()`**  
  Initializes the database and required system components.

- **`collect_data()`**  
  Collects current data from WireGuard and stores it in the database.

- **`get_usage(public_key=None, month=None, monthly_only=True)`**  
  Returns formatted usage data, optionally filtered by peer and month.

- **`update_info(public_key, name=None, email=None)`**  
  Updates peer information in the database.

- **`delete_peer(email, keep_usage_history=False)`**  
  Deletes all peers associated with a specified email.

- **`sync_database_with_interface(auto_fix=False)`**  
  Verifies and optionally fixes inconsistencies between WireGuard and the database.

### WireGuard Module (`wireguard.py`)

The `WireGuard` class provides methods for interacting with the WireGuard VPN service:

- **`get_peer_data()`**  
  Returns current statistics for all WireGuard peers.

- **`generate_keys()`**  
  Generates a new WireGuard key pair.

- **`add_peer_to_config(public_key, allowed_ips, config_file=None)`**  
  Adds a peer to WireGuard and persists it in the configuration file.

- **`get_next_ip(config_file=None)`**  
  Determines the next available IP address in the subnet.

- **`get_server_public_key(config_file=None)`**  
  Returns the server's WireGuard public key.

- **`get_server_endpoint()`**  
  Returns the server's public endpoint (IP).

- **`remove_peer(public_key)`**  
  Removes a peer from both the WireGuard interface and configuration file.

### Database Module (`database.py`)

The `Database` class provides methods for database operations:

- **`init_db()`**  
  Initializes the database schema.

- **`ensure_peer_exists(conn, public_key)`**  
  Ensures a peer exists in the database.

- **`get_peer_usage(public_key=None, month=None, monthly_only=True)`**  
  Returns usage statistics for one or all peers.

- **`store_measurement(conn, peer_data, current_month)`**  
  Stores monthly usage data for a peer.

- **`update_peer_info(public_key, name=None, email=None)`**  
  Updates peer information.

- **`find_peers_by_email(email)`**  
  Finds all public keys associated with a given email.

- **`delete_peer(public_key, keep_usage_history=False)`**  
  Deletes a peer from the database.
