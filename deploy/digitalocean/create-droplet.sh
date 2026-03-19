#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Lab Manager — DigitalOcean Droplet Creator
# Creates a droplet with cloud-init for automatic Lab Manager deployment.
#
# Prerequisites:
#   1. Install doctl: https://docs.digitalocean.com/reference/doctl/how-to/install/
#   2. Authenticate:  doctl auth init
#   3. (Optional) Add SSH key: doctl compute ssh-key list
#
# Usage:
#   bash deploy/digitalocean/create-droplet.sh
#   bash deploy/digitalocean/create-droplet.sh --region sfo3 --name my-lab
# ============================================================================

# --- Defaults ---------------------------------------------------------------
DROPLET_NAME="lab-manager"
REGION="nyc1"
SIZE="s-2vcpu-4gb"  # 4GB RAM, $24/mo
IMAGE="ubuntu-24-04-x64"
FIREWALL_NAME="lab-manager-fw"

# --- Colors -----------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }

# --- Parse arguments --------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case $1 in
        --name)    DROPLET_NAME="$2"; shift 2 ;;
        --region)  REGION="$2"; shift 2 ;;
        --size)    SIZE="$2"; shift 2 ;;
        --image)   IMAGE="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --name NAME     Droplet name (default: lab-manager)"
            echo "  --region SLUG   Region slug (default: nyc1)"
            echo "  --size SLUG     Size slug (default: s-2vcpu-4gb, 4GB \$24/mo)"
            echo "  --image SLUG    Image slug (default: ubuntu-24-04-x64)"
            echo "  -h, --help      Show this help"
            echo ""
            echo "Available regions: doctl compute region list"
            echo "Available sizes:   doctl compute size list"
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
done

# --- Pre-flight checks ------------------------------------------------------
if ! command -v doctl &>/dev/null; then
    error "doctl is not installed."
    error "Install it: https://docs.digitalocean.com/reference/doctl/how-to/install/"
    exit 1
fi

# Verify authentication
if ! doctl account get &>/dev/null; then
    error "doctl is not authenticated. Run: doctl auth init"
    exit 1
fi

ACCOUNT_EMAIL=$(doctl account get --format Email --no-header)
info "Authenticated as: $ACCOUNT_EMAIL"

# Find cloud-init file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUD_INIT="${SCRIPT_DIR}/cloud-init.yml"

if [[ ! -f "$CLOUD_INIT" ]]; then
    error "cloud-init.yml not found at: $CLOUD_INIT"
    exit 1
fi

# --- SSH Key ----------------------------------------------------------------
info "Checking SSH keys..."
SSH_KEYS=$(doctl compute ssh-key list --format ID --no-header 2>/dev/null | tr '\n' ',' | sed 's/,$//')

if [[ -z "$SSH_KEYS" ]]; then
    warn "No SSH keys found in your DigitalOcean account."
    warn "You will need to use the console to access the droplet."
    warn "Add a key first: doctl compute ssh-key create"
    read -rp "Continue without SSH keys? [y/N] " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        exit 0
    fi
    SSH_KEY_FLAG=""
else
    KEY_COUNT=$(echo "$SSH_KEYS" | tr ',' '\n' | wc -l)
    info "Found $KEY_COUNT SSH key(s)."
    SSH_KEY_FLAG="--ssh-keys $SSH_KEYS"
fi

# --- Firewall ---------------------------------------------------------------
info "Checking firewall..."
EXISTING_FW=$(doctl compute firewall list --format ID,Name --no-header 2>/dev/null | grep "$FIREWALL_NAME" | awk '{print $1}' || true)

if [[ -n "$EXISTING_FW" ]]; then
    success "Firewall '$FIREWALL_NAME' already exists (ID: $EXISTING_FW)."
    FIREWALL_ID="$EXISTING_FW"
else
    info "Creating firewall '$FIREWALL_NAME'..."
    FIREWALL_ID=$(doctl compute firewall create \
        --name "$FIREWALL_NAME" \
        --inbound-rules "protocol:tcp,ports:22,address:0.0.0.0/0,address:::/0 protocol:tcp,ports:80,address:0.0.0.0/0,address:::/0 protocol:tcp,ports:443,address:0.0.0.0/0,address:::/0 protocol:icmp,address:0.0.0.0/0,address:::/0" \
        --outbound-rules "protocol:tcp,ports:all,address:0.0.0.0/0,address:::/0 protocol:udp,ports:all,address:0.0.0.0/0,address:::/0 protocol:icmp,address:0.0.0.0/0,address:::/0" \
        --format ID --no-header)
    success "Firewall created (ID: $FIREWALL_ID)."
fi

# --- Create Droplet ---------------------------------------------------------
echo ""
info "Creating droplet with the following configuration:"
echo "  Name:   $DROPLET_NAME"
echo "  Region: $REGION"
echo "  Size:   $SIZE (4GB RAM, \$24/mo)"
echo "  Image:  $IMAGE"
echo ""

# shellcheck disable=SC2086
DROPLET_ID=$(doctl compute droplet create "$DROPLET_NAME" \
    --region "$REGION" \
    --size "$SIZE" \
    --image "$IMAGE" \
    --user-data-file "$CLOUD_INIT" \
    $SSH_KEY_FLAG \
    --tag-name "labclaw" \
    --wait \
    --format ID --no-header)

success "Droplet created (ID: $DROPLET_ID)."

# Assign firewall
info "Assigning firewall to droplet..."
doctl compute firewall add-droplets "$FIREWALL_ID" --droplet-ids "$DROPLET_ID"
success "Firewall assigned."

# Get IP address
DROPLET_IP=$(doctl compute droplet get "$DROPLET_ID" --format PublicIPv4 --no-header)

# --- Done -------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}"
echo "  Droplet is ready!"
echo -e "${NC}"
echo "  IP Address:  ${BOLD}${DROPLET_IP}${NC}"
echo "  SSH Access:  ${BOLD}ssh root@${DROPLET_IP}${NC}"
echo ""
echo "  Lab Manager is installing automatically via cloud-init."
echo "  This takes 3-5 minutes. Check progress with:"
echo "    ssh root@${DROPLET_IP} tail -f /var/log/labclaw-setup.log"
echo ""
echo "  Once ready, open in your browser:"
echo "    ${BOLD}http://${DROPLET_IP}${NC}"
echo ""
echo "  To get the admin password:"
echo "    ssh root@${DROPLET_IP} cat /opt/labclaw/.admin_password"
echo ""
echo "  Monthly cost: ~\$24 (s-2vcpu-4gb)"
echo ""
echo "  To destroy:  doctl compute droplet delete ${DROPLET_ID} --force"
echo ""
