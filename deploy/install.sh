#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Lab Manager — Universal Installer
# One-command deployment for non-technical users.
# Usage: cd lab-manager && bash deploy/install.sh
# ============================================================================

REPO_URL="https://github.com/labclaw/lab-manager.git"
INSTALL_DIR="/opt/labclaw/lab-manager"

# --- Colors ---------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
header()  { echo -e "\n${BOLD}=== $* ===${NC}\n"; }

# --- Helpers ---------------------------------------------------------------
generate_password() {
    local length="${1:-32}"
    tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$length" || true
}

generate_hex() {
    local length="${1:-64}"
    tr -dc 'a-f0-9' < /dev/urandom | head -c "$length" || true
}

command_exists() {
    command -v "$1" &>/dev/null
}

escape_env() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

clone_repo() {
    if command_exists gh && gh auth status &>/dev/null; then
        gh repo clone labclaw/lab-manager "$INSTALL_DIR"
        return 0
    fi

    if git clone "$REPO_URL" "$INSTALL_DIR"; then
        return 0
    fi

    error "Unable to clone labclaw/lab-manager automatically."
    error "This repository is private. Either:"
    error "  1. Run this installer from an existing local checkout, or"
    error "  2. Authenticate GitHub CLI and retry: gh auth login"
    exit 1
}

# --- Pre-flight checks -----------------------------------------------------
header "Lab Manager Installer"
info "This script will install Lab Manager with Docker Compose."
echo ""

# Must be root or have sudo
if [[ $EUID -ne 0 ]]; then
    if ! command_exists sudo; then
        error "This script requires root privileges. Run with sudo or as root."
        exit 1
    fi
    SUDO="sudo"
else
    SUDO=""
fi

# Detect OS
header "Checking System"
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_VERSION="${VERSION_ID:-unknown}"
    info "Detected OS: ${PRETTY_NAME:-$OS_ID $OS_VERSION}"
else
    OS_ID="unknown"
    OS_VERSION="unknown"
    warn "Cannot detect OS. /etc/os-release not found."
fi

if [[ "$OS_ID" != "ubuntu" && "$OS_ID" != "debian" ]]; then
    warn "This installer is designed for Ubuntu/Debian."
    warn "Your OS ($OS_ID) may work but is not officially supported."
    read -rp "Continue anyway? [y/N] " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        info "Aborted."
        exit 0
    fi
fi

# Check minimum RAM (4GB recommended)
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_MB=$((TOTAL_RAM_KB / 1024))
if [[ $TOTAL_RAM_MB -lt 3500 ]]; then
    warn "This machine has ${TOTAL_RAM_MB}MB RAM. 4GB+ is recommended."
    warn "Lab Manager may run slowly or fail to start."
fi
info "RAM: ${TOTAL_RAM_MB}MB"

# --- Docker Installation ---------------------------------------------------
header "Docker"

if command_exists docker; then
    DOCKER_VERSION=$(docker --version 2>/dev/null || echo "unknown")
    success "Docker is installed: $DOCKER_VERSION"
else
    info "Docker not found. Installing..."
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq ca-certificates curl gnupg lsb-release

    # Add Docker GPG key and repo
    $SUDO install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/${OS_ID}/gpg | $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null
    $SUDO chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${OS_ID} \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      $SUDO tee /etc/apt/sources.list.d/docker.list > /dev/null

    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Add current user to docker group
    if [[ $EUID -ne 0 ]]; then
        $SUDO usermod -aG docker "$USER"
        warn "Added $USER to docker group. You may need to log out and back in."
    fi

    success "Docker installed successfully."
fi

# Verify docker compose (v2 plugin)
if docker compose version &>/dev/null; then
    success "Docker Compose plugin: $(docker compose version --short 2>/dev/null || echo 'available')"
else
    error "Docker Compose plugin not found."
    error "Install it: sudo apt-get install docker-compose-plugin"
    exit 1
fi

# Ensure Docker daemon is running
if ! docker info &>/dev/null; then
    info "Starting Docker daemon..."
    $SUDO systemctl start docker
    $SUDO systemctl enable docker
fi

# --- Repository Setup -------------------------------------------------------
header "Repository"

# Determine working directory
# If we're already inside a lab-manager repo (docker-compose.yml exists), use it
if [[ -f "docker-compose.yml" && -f "Dockerfile" && -d "src/lab_manager" ]]; then
    PROJECT_DIR="$(pwd)"
    success "Using current directory: $PROJECT_DIR"
elif [[ -f "${INSTALL_DIR}/docker-compose.yml" ]]; then
    PROJECT_DIR="$INSTALL_DIR"
    info "Found existing installation at $PROJECT_DIR"
    cd "$PROJECT_DIR"
    info "Pulling latest changes..."
    git pull --ff-only || warn "Could not pull latest changes. Continuing with existing code."
else
    info "Cloning lab-manager to $INSTALL_DIR..."
    $SUDO mkdir -p "$(dirname "$INSTALL_DIR")"
    $SUDO chown "$USER:$(id -gn)" "$(dirname "$INSTALL_DIR")"
    clone_repo
    PROJECT_DIR="$INSTALL_DIR"
    cd "$PROJECT_DIR"
    success "Repository cloned."
fi

cd "$PROJECT_DIR"

# --- Environment Configuration ---------------------------------------------
header "Configuration"

ENV_FILE="$PROJECT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
    warn "Existing .env file found at: $ENV_FILE"
    read -rp "Overwrite with new configuration? [y/N] " overwrite
    if [[ "$overwrite" != "y" && "$overwrite" != "Y" ]]; then
        info "Keeping existing .env file."
        info "Skipping to deployment..."
        SKIP_ENV=true
    else
        # Back up existing .env
        BACKUP_NAME=".env.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$ENV_FILE" "$PROJECT_DIR/$BACKUP_NAME"
        info "Backed up existing .env to $BACKUP_NAME"
        SKIP_ENV=false
    fi
else
    SKIP_ENV=false
fi

if [[ "$SKIP_ENV" == "false" ]]; then
    # Generate secrets
    POSTGRES_PASSWORD=$(generate_password 32)
    POSTGRES_RO_PASSWORD=$(generate_password 32)
    MEILI_MASTER_KEY=$(generate_password 32)
    ADMIN_SECRET_KEY=$(generate_hex 64)
    ADMIN_PASSWORD=$(generate_password 16)

    # Interactive prompts
    echo ""
    info "Configure your Lab Manager instance."
    info "Press Enter to accept defaults shown in [brackets]."
    echo ""

    read -rp "Lab name [My Lab]: " LAB_NAME
    LAB_NAME="${LAB_NAME:-My Lab}"
    LAB_NAME_ESCAPED=$(escape_env "$LAB_NAME")

    read -rp "Domain (or 'localhost' for IP-only access) [localhost]: " DOMAIN
    DOMAIN="${DOMAIN:-localhost}"

    read -rp "Gemini API key (optional, press Enter to skip): " GEMINI_API_KEY
    GEMINI_API_KEY="${GEMINI_API_KEY:-}"

    # Determine cookie security
    if [[ "$DOMAIN" == "localhost" ]]; then
        SECURE_COOKIES="false"
    else
        SECURE_COOKIES="true"
    fi

    # Write .env file
    cat > "$ENV_FILE" <<ENVFILE
# Lab Manager — Generated by install.sh on $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# Lab: ${LAB_NAME}

# --- Domain ---
DOMAIN=${DOMAIN}
LAB_NAME="${LAB_NAME_ESCAPED}"
LAB_SUBTITLE=""

# --- PostgreSQL ---
POSTGRES_USER=labmanager
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=labmanager
POSTGRES_RO_PASSWORD=${POSTGRES_RO_PASSWORD}

# --- Application ---
ADMIN_SECRET_KEY=${ADMIN_SECRET_KEY}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
AUTH_ENABLED=true
SECURE_COOKIES=${SECURE_COOKIES}

# --- Meilisearch ---
MEILI_ENV=production
MEILI_MASTER_KEY=${MEILI_MASTER_KEY}

# --- AI/VLM ---
GEMINI_API_KEY=${GEMINI_API_KEY}
EXTRACTION_MODEL=gemini-3.1-flash-preview
RAG_MODEL=gemini-2.5-flash
ENVFILE

    chmod 600 "$ENV_FILE"
    success "Configuration saved to .env"
fi

# --- Deploy -----------------------------------------------------------------
header "Deploying"

info "Building and starting containers..."
docker compose up -d --build

# --- Health Check -----------------------------------------------------------
header "Health Check"

info "Waiting for Lab Manager to start (up to 60 seconds)..."

# Determine health check URL
if [[ "${DOMAIN:-localhost}" == "localhost" ]]; then
    HEALTH_URL="http://localhost/api/health"
else
    HEALTH_URL="http://localhost/api/health"
fi

ELAPSED=0
MAX_WAIT=60
HEALTHY=false

while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" ]]; then
        HEALTHY=true
        break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    echo -ne "\r  Waiting... ${ELAPSED}s / ${MAX_WAIT}s (HTTP ${HTTP_CODE})"
done
echo ""

if [[ "$HEALTHY" == "true" ]]; then
    success "Lab Manager is running and healthy!"
else
    warn "Health check did not return 200 within ${MAX_WAIT}s."
    warn "The services may still be starting. Check with: docker compose logs -f"
fi

# --- Success Message --------------------------------------------------------
header "Deployment Complete"

# Determine access URL
if [[ "${DOMAIN:-localhost}" != "localhost" ]]; then
    ACCESS_URL="http://${DOMAIN}"
else
    # Try to get the machine's IP
    MACHINE_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
    ACCESS_URL="http://${MACHINE_IP}"
fi

echo -e "${GREEN}${BOLD}"
echo "  Lab Manager is ready!"
echo -e "${NC}"
echo "  Access URL:  ${BOLD}${ACCESS_URL}${NC}"
echo ""
echo "  Visit the URL in your browser to complete setup."
echo "  You'll see a setup wizard - create your admin account and start using it."
echo ""
if [[ "$SKIP_ENV" == "false" ]]; then
    echo -e "  ${YELLOW}${BOLD}IMPORTANT: Save this password for the SQLAdmin panel (/admin/):${NC}"
    echo -e "  ${BOLD}ADMIN_PASSWORD: ${ADMIN_PASSWORD}${NC}"
    echo ""
fi
echo "  Useful commands:"
echo "    docker compose logs -f        # View live logs"
echo "    docker compose ps             # Check service status"
echo "    docker compose down            # Stop all services"
echo "    docker compose up -d           # Start all services"
echo ""
echo "  Configuration: ${ENV_FILE}"
echo "  Project dir:   ${PROJECT_DIR}"
echo ""
