# Host & toolchain — Windows 11 → VMware Workstation → Linux VM → containers

The target architecture:

```
Windows 11 (laptop, Ryzen 7 / 16 GB)
└── VMware Workstation Pro            (free since 2024 — just download it)
    └── Ubuntu 24.04 LTS Server VM    (4 vCPU · 12 GB · 80 GB thin disk)
        └── dockerd                   (the VM is an appliance: sshd + docker only)
            ├── dev-ide               ← THE WORKSTATION: code-server, Python,
            │                            Ansible, pyATS, containerlab, docker CLI
            ├── netbox-docker stack   (app, worker, PostgreSQL, Redis)
            └── clab-branch-001-*     (the lab: cEOS ×2, FRR ×2, alpine ×3)
```

One VM, one control-plane container, everything else is payload.

## Which Linux? Ubuntu 24.04 LTS **Server** — the others were considered and rejected

| Candidate | Verdict | Why |
|---|---|---|
| **Ubuntu Server 24.04 LTS** | ✅ **Use this** | Reference platform for containerlab and netbox-docker docs; every guide assumes it; server image wastes no RAM on a GUI you'll never open (browser/SSH access instead) |
| Ubuntu Desktop | ❌ | GNOME burns ~1–1.5 GB of your 12 GB VM budget to render a desktop inside a VM console you'll access twice. The IDE runs in a container and is used through the browser — a desktop adds nothing |
| Fedora | ❌ (close second) | Works fine — containerlab and docker have Fedora packages — but you'll be the one translating every Debian-flavoured guide. No upside for this use case |
| Alpine | ❌ | Wrong layer. Alpine is an excellent *container payload* (this repo uses it for endpoints) but a poor *platform host*: musl libc, OpenRC instead of systemd, and containerlab's install path targets deb/rpm. You'd be debugging the platform instead of building labs |

**Rule of thumb:** the VM is an appliance — boring, minimal, LTS. All
interesting software lives in containers, where it's reproducible and
disposable.

## VMware Workstation settings

| Setting | Value | Why |
|---|---|---|
| vCPU | 4 (all cores) | the lab is container-based; no nested VMs needed |
| RAM | 12 GB | leaves ~4 GB for Windows; lab + NetBox + IDE ≈ 7 GB inside the VM |
| Disk | 80 GB, thin, single file | cEOS image + NetBox + Docker layers grow; thin provisioning means you only pay for what you use |
| Network | NAT | simplest; bridged only if you want to reach code-server from other devices on your LAN |
| **Virtualize Intel VT-x/EPT (AMD-V)** | ✅ enable | not needed today — cEOS and FRR are *containers*, not VMs — but costs nothing and unlocks vrnetlab/Cisco images later without reconfiguring the VM |

Note: Workstation Pro has been free (including for commercial use) since
Broadcom's 2024 change — no license gymnastics needed.

## VM bootstrap (once)

```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # re-login after this

# Repo at the canonical path (see the path rule in dev/docker-compose.dev.yml)
sudo mkdir -p /opt/branch-as-code
sudo chown $USER:$USER /opt/branch-as-code
git clone https://github.com/hans375-olo/branch-as-code /opt/branch-as-code

# Build + start the workstation container
cd /opt/branch-as-code
docker compose -f dev/docker-compose.dev.yml up -d --build
```

Then from Windows: `http://<vm-ip>:8443` → VS Code in the browser, with
Python, Ansible, pyATS, containerlab and the Docker CLI already inside.
Change `PASSWORD` in `dev/docker-compose.dev.yml` first.

## Why a workstation *container* instead of installing tools on the VM?

- **Reproducibility**: the toolchain is a Dockerfile — versioned, rebuildable,
  and it travels with the repo. The VM stays a clean appliance.
- **Blast radius**: breaking your Python environment is a container rebuild,
  not a VM rebuild.
- **It's the same story as the lab itself**: data/config/tooling as code.

### The one gotcha that will bite you if you skip it

The dev container drives the VM's docker daemon through the mounted
`/var/run/docker.sock`. That daemon resolves bind-mount paths **on the VM's
filesystem** — so when containerlab expands `../configs/sw1/startup-config`
to an absolute path, that path must exist on the VM. Hence the hard rule,
already baked into the compose file: **the repo lives at
`/opt/branch-as-code` on both sides.** Forget this and you'll chase
"file not found" ghosts.

### code-server extension note

`ms-python.python` and `redhat.ansible` are on Open VSX (code-server's
registry) and install automatically on first start. If the containerlab
extension (`srl-labs.vscode-containerlab`) isn't found there, grab the VSIX
from the GitHub releases page of the extension and install via the
code-server UI (*Extensions → ... → Install from VSIX*).

### Alternative worth knowing (and a fine nuance)

VS Code on Windows → *Remote-SSH* into the VM → *Dev Containers* into
`dev-ide` gives the full desktop VS Code experience with the same container.
code-server was chosen as the default because it's one less moving part and
works from any browser. Both are legitimate; knowing the difference is the
point.

## Updated RAM budget (inside the 12 GB VM)

| Component | ~RAM |
|---|---|
| Lab (2× cEOS, 2× FRR, 3× alpine) | ~3.5 GB |
| NetBox stack | ~2.5 GB |
| dev-ide (code-server + toolchain) | ~0.5–1 GB |
| Ubuntu Server base + dockerd | ~0.7 GB |
| **Total / budget** | **≈ 8 GB of 12 GB** — comfortable |

## pyATS — quick win

pyATS/Genie is installed in the container. The natural evolution of
`verify.yml`: replace the FRR JSON parsing and EOS text checks with Genie
parsers (`genie parse "show ip interface brief" ...`) and a pyATS testbed
YAML — structured state diffing ("did this change break anything?") is
exactly what pyATS is for.
