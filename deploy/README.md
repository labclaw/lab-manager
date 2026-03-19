# Deployment Guide

Three practical ways to get Lab Manager in front of a user, from fastest evaluation to a real deployment.

## Option 0: Local Trial On Your Laptop

Best for product evaluation, demos, and first-time users who want to try the app before adopting it.

```bash
cd lab-manager
bash scripts/bootstrap_local_env.sh "My Lab"
docker compose up -d --build
```

Then open `http://localhost` and complete the setup wizard in the browser.

This path is intentionally local-friendly:
- it generates secrets automatically
- it sets `SECURE_COOKIES=false` for localhost HTTP
- it does not require an AI API key to explore the core product

## Option 1: One-Command Install

Run on any Ubuntu/Debian machine (local server, VM, cloud instance):

```bash
git clone https://github.com/labclaw/lab-manager.git
cd lab-manager
bash deploy/install.sh
```

The installer will:
- Install Docker if needed
- Generate all secrets automatically
- Ask for your lab name, domain, and optional Gemini API key
- Start all services and verify they're healthy

Requirements: Ubuntu/Debian, 4GB+ RAM, root or sudo access.

## Option 2: DigitalOcean One-Click

Create a fully configured cloud server with one command:

```bash
# Install doctl: https://docs.digitalocean.com/reference/doctl/how-to/install/
doctl auth init
bash deploy/digitalocean/create-droplet.sh
```

This creates a $24/mo droplet (4GB RAM, 2 vCPUs) with:
- Lab Manager running and accessible via HTTP
- UFW firewall (ports 22, 80, 443 only)
- Daily database backups at 2 AM
- All secrets auto-generated

Options:
```bash
bash deploy/digitalocean/create-droplet.sh --region sfo3 --name my-lab
```

## Option 3: Manual Docker Compose

For custom setups, see [DEPLOY.md](../DEPLOY.md) in the project root.

```bash
cp .env.example .env
# Edit .env with your passwords and settings
docker compose up -d
```

## After Deployment

All three options end the same way:

1. Open the URL in your browser (the installer prints it)
2. You'll see a setup wizard -- enter your lab name and create an admin account
3. Start using Lab Manager immediately

The SQLAdmin panel is available at `/admin/` using the generated `ADMIN_PASSWORD` (printed by the installer or stored in `/opt/labclaw/.admin_password` on DigitalOcean).

To enable AI features later, add a Gemini API key to `.env` and restart:

```bash
# Edit .env and set GEMINI_API_KEY=your-key
docker compose up -d
```
