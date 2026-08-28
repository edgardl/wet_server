#!/bin/bash

set -euo pipefail

# Variables
LOG_FILE="/var/log/provisioning.log"
DOCKER_LOGS="/var/log/docker"
NETWORK="wet-network"
SERVICE_APP="wet_app"
VERBOSE="false"

# Log function
log_generic() {
    local level=$1
    local message=$2

    # Make sure log file exists
    if [[ ! -f "$LOG_FILE" ]]; then
	touch "$LOG_FILE"
    fi
    
    # Format => YYYY-MM-DD.HH:MM:SS [LEVEL] Message
    local log_entry="$(date +%F.%T) [$level] $message"
    
    # Append to log file and print to console
    echo "$log_entry" | tee -a "$LOG_FILE"
}

# Mimic Python log levels
log_info()  { log_generic "INFO"  "$1"; }
log_warn()  { log_generic "WARN"  "$1"; }
log_error() { log_generic "ERROR" "$1" >&2; }
log_debug() {
    # Only print debug messages when running on verbose mode
    if [[ "$VERBOSE" == "true" ]]; then
        log_generic "DEBUG" "$1"
    fi
}

system_setup() {
    # Update system
    log_info "Updating system"
    apt-get update

    # Install packages
    log_info "Installing docker and dependencies"
    package_list="docker.io openssl fail2ban openssh-server nftables"
    log_debug "Installing packages: $package_list"
    apt-get install -y $package_list
}

firewall_setup() {
    log_info "Setting up firewall rules"

    # Ensure nftables service is running
    systemctl enable --now nftables

    # Flush existing rules to start clean
    nft flush ruleset

    # Create the base table and chain with default policy (deny incoming, allow outgoing)
    nft add table inet filter
    nft add chain inet filter input \{ type filter hook input priority 0 \; policy drop \; \}
    nft add chain inet filter forward \{ type filter hook forward priority 0 \; policy drop \; \}
    nft add chain inet filter output \{ type filter hook output priority 0 \; policy accept \; \}

    # Allow loopback interface traffic
    nft add rule inet filter input iifname "lo" accept

    # Allow established and related connections (required for responses to outgoing traffic)
    nft add rule inet filter input ct state established,related accept

    # Allow SSH
    log_debug "Allowing traffic on port 22 TCP (SSH)"
    nft add rule inet filter input tcp dport 22 accept

    # Allow custom port 9999
    log_debug "Allowing traffic on port 9999 TCP for feedback app"
    nft add rule inet filter input tcp dport 9999 accept

    # Make rules persistent across reboots
    log_debug "Saving nftables ruleset"
    nft list ruleset > /etc/nftables.conf
}

sshd_setup() {
    log_info "Setting up SSHD"
    # Backup the config
    log_debug "Backing up file /etc/ssh/sshd_config as /etc/ssh/sshd_config.bak"
    cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak

    # Apply hardening
    log_debug "Modifying SSHD config to disallow root login"
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config
    sed -i 's/#MaxAuthTries 6/MaxAuthTries 3/' /etc/ssh/sshd_config
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

    # Restart service
    log_debug "Restarting SSH service"
    systemctl restart ssh
}

start_fail2ban() {
    log_info "Starting fail2ban to monitor SSH access"

    # Default settings should be good enough for SSH (IP with 5 failed attempts is banned for 10 min)
    systemctl enable --now fail2ban
}

env_setup() {
    # Ensure Debian has iptables installed for Docker's NAT rules
    if ! command -v iptables >/dev/null 2>&1; then
        log_info "Installing iptables prerequisite for Docker"
        apt-get update && apt-get install -y iptables
    fi

    # Enable and FORCE RESTART docker to rebuild iptables chains wiped by the firewall
    log_debug "Restarting Docker service to regenerate iptables rules"
    systemctl enable docker
    systemctl restart docker

    # Wait briefly for Docker daemon socket to be fully ready
    sleep 2

    # Create docker network for containers to talk to each other
    log_info "Creating container network"
    if ! /usr/bin/docker network inspect "$NETWORK" >/dev/null 2>&1; then
        /usr/bin/docker network create "$NETWORK"
    fi

    # Cleanup existing containers for a clean deployment
    log_info "Cleaning up old container instances"
    /usr/bin/docker rm -f "$SERVICE_APP" >/dev/null 2>&1 || true
}

# Shared directory for docker container logs
log_setup() {
    log_info "Creating log directories for docker containers"
    mkdir -p "$DOCKER_LOGS/$SERVICE_APP/flask"
    
    # Ensure the directories are writable by the containers
    chmod -R 777 "$DOCKER_LOGS"
}

start_app() {
    local app_artifact="ghcr.io/edgardl/wet_server:latest"
    log_info "Pulling latest WET server artifact"
    log_debug "Image: $app_artifact"
    /usr/bin/docker pull "$app_artifact"

    # Gracefully stop the service app (if already exists)
    if docker ps -a --format '{{.Names}}' | grep -q "^$SERVICE_APP$"; then
	  log_info "Stopping existing service app gracefully"
	  /usr/bin/docker stop "$SERVICE_APP" || true
	  /usr/bin/docker rm "$SERVICE_APP" || true
    fi
    
    # Starting feedback app container
    log_info "Starting $SERVICE_APP container"
    /usr/bin/docker run -d \
		    --name "$SERVICE_APP" \
		    --network "$NETWORK" \
		    --log-opt max-size=10m \
		    --log-opt max-file=3 \
		    --restart always \
		    --publish 9999:9999 \
		    --volume "/home/wet_model/scripts:/app/scripts"
		    "$app_artifact"
}

integration_health() {
    # Give the services five seconds to stabilize
    sleep 5

    # Confirm Nginx can reach starman and starman can reach the DB
    local health_check=$(curl -s -k -o /dev/null -w "%{http_code}" https://localhost:9999/health)

    if [ "$health_check" -eq 200 ]; then
	log_info "Success: Service is healthy and connected to DB"
    else
	log_error "Failed: Received HTTP $health_check"
	log_info "Checking if Nginx came up"
	local unhealthy_nginx=$(/usr/bin/docker exec -it $SERVICE_APP ss -tulnp | grep -q "0.0.0.0:9999")
	if $unhealthy_nginx; then
	    log_error "Nginx appears to be down. Port 9999 is not open"
	    log_error "Nginx logs under $DOCKER_LOGS/$SERVICE_APP/nginx should be reviewed"
	    exit 1
	fi
	log_info "Nginx appears to be healthy. Seems like starman could be the problem"
	log_error "Starman logs under $DOCKER_LOGS/$SERVICE_APP/starman should be reviewed"
	exit 1
    fi
}

main() {
    log_info "================ START ================"
    
    log_info "Getting the system ready..."
    system_setup
    firewall_setup
    sshd_setup
    start_fail2ban

    log_info "Getting docker environment ready..."
    env_setup
    log_setup
    
    log_info "Starting services..."
    start_app

    log_info "Cleaning up old docker images..."
    /usr/bin/docker image prune -f

    log_info "Running final integration health checks..."
    # TODO: Modify integration health function
    #integration_health
    
    log_info "System ready!"

    log_info "Check $LOG_FILE to access the log of this execution"
    log_info "================= END ================="
}

show_help() {
    cat << EOF
Usage: ./provisioning_3.sh [options]

This script provisions the WET server.

Options:
  -v             Enable verbose (DEBUG) mode for detailed logging.
  -h             Show this help message and exit.

Example:
  sudo ./provisioning_3.sh -v
EOF
}

# Parse parameters
while getopts "vh" opt; do
  case $opt in
    h)
      show_help
      exit 0
      ;;
    v)
      VERBOSE="true"
      ;;
    *)
      show_help
      exit 1
      ;;
  esac
done

# Shift off the options
shift $((OPTIND-1))

# Everything starts here
main
