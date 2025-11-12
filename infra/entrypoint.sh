#!/bin/bash
set -e

echo "Verifying SSH configuration..."

SSH_DIR="${HOME}/.ssh"
KEY_FILE="${SSH_DIR}/id_rsa"
KNOWN_HOSTS_FILE="${SSH_DIR}/known_hosts"

if [[ ! -f "$KEY_FILE" ]]; then
    echo "ERROR: SSH private key ($KEY_FILE) not found!"
    exit 1
fi

chmod 700 "$SSH_DIR"
chmod 600 "$KEY_FILE"
chmod 644 "${KEY_FILE}.pub" || true
# touch "$KNOWN_HOSTS_FILE"
chmod 644 "$KNOWN_HOSTS_FILE" || true

if [[ -z "$EG_REMOTE_HOSTS" ]]; then
    echo "Warning!!! EG_REMOTE_HOSTS not set"
else
    IFS=',' read -ra HOSTS <<< "$EG_REMOTE_HOSTS"
    REMOTE_USER="${EG_REMOTE_USER:-jovyan}"

    for host in "${HOSTS[@]}"; do
        echo "Testing SSH connection to $REMOTE_USER@$host ..."
        
        ssh-keyscan -H "$host" >> "$KNOWN_HOSTS_FILE" 2>/dev/null || true

        if ssh -o BatchMode=yes -o ConnectTimeout=5 "$REMOTE_USER@$host" 'echo SSH OK' 2>/dev/null; then
            echo "SSH to $host successful."
        else
            echo "ERROR: Cannot SSH to $REMOTE_USER@$host"
            exit 1
        fi
    done
fi

echo "Starting Jupyter Enterprise Gateway..."
exec jupyter enterprisegateway --config=/etc/jupyter/jeg_config.py