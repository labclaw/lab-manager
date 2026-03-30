# Tailscale Device Connectivity Tutorial

> Connect all lab devices to lab-manager via Tailscale mesh VPN.
> Tested: 2026-03-30 | Shen Lab (MGH/Harvard)

## Overview

Lab-manager uses Tailscale to create a zero-config encrypted mesh network between all lab devices. Each device gets a stable `100.x.x.x` IP and can communicate with every other device — no VPN, no port forwarding, no firewall rules.

```
                    Tailscale Mesh (WireGuard encrypted)
                    ┌─────────────────────────────────┐
                    │                                  │
  ┌─────────┐       │   ┌─────────┐  ┌─────────┐     │
  │ robot-  │◄──────┼──►│ my-open │  │ sylvie- │     │
  │ intel   │       │   │ claw    │  │ claw    │     │
  │ (Local) │       │   │ (DO)    │  │ (DO)    │     │
  └─────────┘       │   └─────────┘  └─────────┘     │
                    │                                  │
                    │   ┌─────────────────────────┐   │
                    │   │ shen-6604b-c1           │   │
                    │   │ SpectraMax Plate Reader  │   │
                    │   │ (Lab PC, Windows 11)     │   │
                    │   └─────────────────────────┘   │
                    └─────────────────────────────────┘
```

## Prerequisites

- A Tailscale account (free plan supports up to 100 devices)
- Admin access to the Tailscale admin console
- SSH or physical access to each device

## Step 1: Install Tailscale on Each Device

### Linux (Ubuntu/Debian)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

### Windows

1. Download from https://tailscale.com/download/windows
2. Install and log in with your Tailscale account
3. Or via PowerShell:
   ```powershell
   winget install Tailscale.Tailscale
   tailscale up
   ```

### macOS

```bash
brew install --cask tailscale
```

Verify on each device:
```bash
tailscale status
tailscale ip -4   # Should show 100.x.x.x
```

## Step 2: Configure SSH Access

### 2a. Enable Tailscale SSH on Linux/macOS

On each Linux/macOS device, run:

```bash
# If no custom flags set previously:
tailscale up --ssh --accept-routes

# If you have existing flags (e.g., hostname), include them all:
tailscale up --ssh --accept-routes --hostname=my-device-name
```

**Windows does NOT support Tailscale SSH.** Use OpenSSH Server instead (Step 2c).

### 2b. Configure SSH ACL Policy

Go to https://login.tailscale.com/admin/acls and switch to **JSON editor**.

The SSH section should look like this:

```json
{
    "grants": [
        {"src": ["*"], "dst": ["*"], "ip": ["*"]}
    ],
    "ssh": [
        {
            "action": "accept",
            "src":    ["autogroup:member"],
            "dst":    ["autogroup:self"],
            "users":  ["autogroup:nonroot", "root"]
        }
    ],
    "nodeAttrs": [
        {
            "target": ["autogroup:member"],
            "attr":   ["funnel"]
        }
    ]
}
```

**Critical ACL notes** (learned from debugging):

| Rule | Correct | Wrong | Why |
|------|---------|-------|-----|
| SSH src | `autogroup:member` | `autogroup:members` | No trailing 's' |
| SSH dst | `autogroup:self` | `autogroup:member` | `autogroup:member` is invalid for SSH dst |
| SSH action | `accept` | `check` | `check` requires browser auth every session |
| SSH dst wildcard | not supported | `*` | Bare wildcard is invalid for SSH dst |
| Policy style | `grants` only | `grants` + `acls` | Mixing old/new style causes errors |

> **Why `autogroup:self` works for all-to-all**: In a single-user tailnet (all devices owned by one account), `autogroup:self` = "all devices owned by this user" = all devices. For multi-user tailnets, you'd need tags.

### 2c. Enable OpenSSH Server on Windows

Run in **Administrator PowerShell** on the Windows device:

```powershell
# Install OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# Start and set auto-start
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic

# Verify
Get-Service sshd
```

### 2d. Add SSH Public Key to Windows

From a Linux machine, get your public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

Then on the Windows device, run in PowerShell (replace `<pubkey>` and `<username>`):

```powershell
mkdir C:\Users\<username>\.ssh -Force
Add-Content -Path C:\Users\<username>\.ssh\authorized_keys -Value '<pubkey>'
icacls C:\Users\<username>\.ssh\authorized_keys /inheritance:r /grant "<username>:R"
icacls C:\Users\<username>\.ssh /inheritance:r /grant "<username>:(OI)(CI)R"
```

### 2e. Configure Local SSH Config

On your local machine, add entries to `~/.ssh/config`:

```
Host my-openclaw
    HostName 100.86.84.5
    User root
    ConnectTimeout 10

Host sylvie-claw
    HostName 100.97.27.96
    User root
    ConnectTimeout 10

Host shen shen-6604b-c1
    HostName 100.105.226.46
    User wangc
    ConnectTimeout 10
```

Now you can connect with just `ssh shen` or `ssh my-openclaw`.

### 2f. Verify All Connections

```bash
# Tailscale SSH (Linux to Linux)
tailscale ssh root@my-openclaw hostname
tailscale ssh root@sylvie-claw hostname

# Regular SSH over Tailscale (to Windows)
ssh shen hostname
```

## Step 3: Install the Device Daemon

The device daemon reports heartbeats to lab-manager, providing real-time status and system metrics.

### 3a. Copy the Daemon to Each Device

```bash
# From the repo
scp labclaw-device-daemon/device_daemon.py root@my-openclaw:/opt/labclaw-daemon/
scp labclaw-device-daemon/device_daemon.py wangc@shen:C:/labclaw-daemon/
```

### 3b. Create Config File

Create `/etc/labclaw-daemon/config.yaml` (Linux) or `C:\labclaw-daemon\config.yaml` (Windows):

```yaml
manager_url: "http://<LAB-MANAGER-TAILSCALE-IP>:8000"
device_name: "SpectraMax-6604B"      # Human-readable name
interval: 60                          # Heartbeat every 60 seconds
tags:
  - "plate-reader"
  - "room-6604"
```

### 3c. Install as System Service

**Linux (systemd):**

```bash
sudo cp labclaw-device-daemon/labclaw-daemon.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now labclaw-daemon
sudo systemctl status labclaw-daemon
```

**Windows (Task Scheduler or NSSM):**

```powershell
# Option A: Task Scheduler
schtasks /create /tn "LabClawDaemon" /tr "python C:\labclaw-daemon\device_daemon.py --config C:\labclaw-daemon\config.yaml" /sc onstart /ru SYSTEM

# Option B: NSSM (recommended)
nssm install LabClawDaemon python C:\labclaw-daemon\device_daemon.py --config C:\labclaw-daemon\config.yaml
nssm start LabClawDaemon
```

### 3d. Verify in lab-manager

Open the lab-manager UI → **Devices** page. The new device should appear within 60 seconds with:
- Hostname, Tailscale IP, platform info
- CPU/memory/disk metrics (if psutil installed)
- Online status

## Step 4: Link Device to Equipment (Optional)

In lab-manager, link the Tailscale-connected device to an equipment entry:

1. Go to **Equipment** page
2. Find or create the instrument (e.g., "SpectraMax 6604B")
3. Edit → set `system_id` to match the device hostname
4. Now the equipment card shows real-time device status

## Troubleshooting

### "Tailscale SSH requires an additional check" (browser auth)

The ACL action is set to `check` instead of `accept`. Fix in the admin console:
```json
"action": "accept"   // NOT "check"
```

### "invalid dst 'autogroup:member'" in SSH ACL

`autogroup:member` is valid for `src` but not for `dst`. Use `autogroup:self`:
```json
"dst": ["autogroup:self"]   // NOT "autogroup:member"
```

### "ACLs contain a mix of old-style and new-style"

You have both `grants` and `acls` sections. Remove the `acls` section — `grants` replaces it.

### Windows SSH "Permission denied"

The public key wasn't added to the correct user's `authorized_keys`, or file permissions are wrong. Verify:
```powershell
icacls C:\Users\wangc\.ssh\authorized_keys
# Should show: wangc:(R)
```

### Device not appearing in lab-manager

1. Check daemon is running: `systemctl status labclaw-daemon` (Linux) or Task Scheduler (Windows)
2. Check network: `tailscale ping <lab-manager-ip>`
3. Check logs: `journalctl -u labclaw-daemon -f`
4. Verify manager URL in config uses Tailscale IP (not localhost)

### Device stays "online" after shutdown

The offline detection relies on the daemon sending a shutdown heartbeat. If the daemon crashes, the device stays "online." Manually mark offline via API or wait for the planned "missed heartbeat" detection feature.

## Network Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Lab Manager Server                  │
│              (FastAPI + PostgreSQL)                   │
│                  Tailscale IP: 100.x.x.x             │
│                       ▲                              │
│         Heartbeat POST /api/v1/devices/heartbeat     │
│                       │                              │
│          ┌────────────┼────────────┐                 │
│          │            │            │                 │
│     ┌────┴────┐ ┌────┴────┐ ┌────┴─────┐           │
│     │ Linux   │ │ Linux   │ │ Windows  │           │
│     │ Daemon  │ │ Daemon  │ │ Daemon   │           │
│     │ (SSH)   │ │ (SSH)   │ │ (OpenSSH)│           │
│     └─────────┘ └─────────┘ └──────────┘           │
│                                                       │
│     All traffic encrypted via WireGuard (Tailscale)   │
│     No ports exposed to public internet               │
└──────────────────────────────────────────────────────┘
```

## Security Notes

- All traffic is end-to-end encrypted (WireGuard)
- No ports need to be opened on any device
- SSH access is controlled by Tailscale ACLs (single policy file)
- Tailscale SSH uses Tailscale identity (no SSH keys to manage for Linux)
- Windows uses SSH key auth (keys added to `authorized_keys`)
- Devices can be removed from the mesh instantly via admin console

## Reference

- Tailscale docs: https://tailscale.com/kb/1018/acls
- Tailscale SSH: https://tailscale.com/docs/features/tailscale-ssh
- Device daemon spec: `labclaw-private/docs/lab-manager-features/device-daemon-spec.md`
- Mesh production spec: `labclaw-private/docs/lab-manager-features/tailscale-mesh-production-spec.md`
