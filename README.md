# branch-as-code

**How I would standardize 5 000 branch sites: one reference store, fully
data-driven, rendered from a Source of Truth, deployed and verified by
Ansible, running as a lightweight Containerlab topology on a laptop.**

```
                       ┌───────────┐
                       │  hq-core  │  FRR · AS65000 · "HQ / provider"
                       └─────┬─────┘
                             │  100.64.1.0/31 · eBGP
                       ┌─────┴─────┐
                       │ rtr1-edge │  FRR · AS65001 · store WAN edge
                       └─────┬─────┘
                             │  10.1.255.0/31 · routed handoff
                       ┌─────┴─────┐
                  ┌────│    sw1    │  cEOS · L3 distribution (SVIs, gateway)
                  │    └───────────┘
                  │ trunk (VLAN 10/20/30/40)
             ┌────┴────┐
             │   sw2   │  cEOS · L2 access
             └─┬────┬──┘
          guest    pos
```

**VLANs are global constants** — 10 MGMT / 20 STAFF / 30 GUEST / 40 POS mean
the same thing in every store. **Only the prefix changes**:
store *N* gets `10.N.0.0/20`. The templates never change; a new store is
data, not configuration.

## The pipeline

```
NetBox (or static YAML)          Jinja2 golden configs         Containerlab
┌──────────────────┐            ┌────────────────────┐        ┌─────────────┐
│ site / devices   │  render    │ configs/sw1/...    │ deploy │ cEOS, FRR   │
│ VLANs / prefixes │ ─────────► │ configs/rtr1-edge/ │ ─────► │ alpine      │
│ interfaces / IPs │            │                    │ verify │             │
└──────────────────┘            └────────────────────┘        └─────────────┘
```

Same templates, same playbooks — swap the inventory to swap the SoT:

```bash
make render            # static YAML SoT (zero infrastructure)
make render-netbox     # NetBox SoT (dynamic inventory + API lookups)
```

## Quickstart (Ubuntu/Debian, Docker + containerlab installed)

```bash
# 1. Import the cEOS image (one-time, free arista.com account — see below)
docker import cEOS64-lab-4.33.0F.tar.xz ceos:4.33.0F

# 2. Bring up the reference store — comes up fully configured
#    (baseline configs in configs/ are bind-mounted)
make lab-up

# 3. Render golden configs from the SoT and deploy them
cd ansible && ansible-galaxy collection install -r requirements.yml
make render && make deploy

# 4. Prove it: LLDP, VLANs, BGP state assertion, end-to-end pings
make verify

# 5. Add the real SoT (optional — lab works fine without it)
git clone https://github.com/netbox-community/netbox-docker ../netbox-docker
make netbox-up
export NETBOX_URL=http://localhost:8000 NETBOX_TOKEN=<token>
make populate          # builds the entire Store-001 data model
make render-netbox     # same templates, data now from NetBox
```

## RAM budget (designed for 4 cores / 16 GB)

| Component | Image | Count | ~RAM each | Subtotal |
|---|---|---|---|---|
| Store edge + HQ | `quay.io/frrouting/frr` | 2 | ~100 MB | 0.2 GB |
| Switches | `ceos:4.33.0F` | 2 | ~1.5 GB | 3.0 GB |
| Endpoints | `alpine` | 3 | ~10 MB | ~0 GB |
| NetBox | netbox-docker (app, worker, PostgreSQL, Redis) | 1 stack | — | ~2.5 GB |
| **Total** | | | | **≈ 6 GB** |

Leaves headroom for the OS and an IDE. Free-alternative swap if you want
to skip the Arista download: replace cEOS with Nokia SR Linux
(`ghcr.io/nokia/srlinux`, free to pull, ~1 GB) — only `templates/ceos.j2`
and two lines of the topology change.

## Getting the cEOS image (the only non-trivial prerequisite)

cEOS is free but gated behind a (free) arista.com account:

1. Register at arista.com → *Software Downloads* → cEOS-lab → download
   `cEOS64-lab-4.33.0F.tar.xz`
2. `docker import cEOS64-lab-4.33.0F.tar.xz ceos:4.33.0F`

Every serious network-automation lab does this dance.

## Repo map

```
├── containerlab/branch-001.clab.yml   # the reference store topology
├── configs/                           # golden configs (bind-mounted into nodes)
│   ├── hq-core/  rtr1-edge/  sw1/  sw2/
├── netbox/data-model.md               # the data model, in words and tables
├── scripts/netbox_populate.py         # idempotent NetBox builder (pynetbox)
├── templates/                         # Jinja2 golden-config templates per platform
│   ├── ceos.j2
│   └── frr.j2
├── ansible/
│   ├── render.yml                     # SoT -> normalized contract -> template -> configs/
│   ├── deploy.yml                     # eAPI config replace (EOS), vtysh reload (FRR)
│   ├── verify.yml                     # state collection + BGP assertion + e2e pings
│   ├── inventories/
│   │   ├── netbox.yml                 # dynamic inventory from NetBox
│   │   └── static/                    # zero-infra fallback SoT (same contract!)
│   └── group_vars/                    # routing policy + platform connection vars
├── dev/                               # the workstation container (code-server IDE,
│   │                                  # Python, Ansible, pyATS, containerlab, docker CLI)
│   ├── Dockerfile.dev
│   └── docker-compose.dev.yml
└── docs/
    ├── design-decisions.md            # the why — read this before the interview
    └── host-and-toolchain.md          # Windows -> VMware -> Ubuntu VM -> containers
```

## Roadmap (deliberate next steps, each a talking point)

- [ ] `svc-dhcp` node + `ip helper-address` — centralized DHCP, NetBox as IPAM
- [ ] Meraki dashboard API module — cloud-managed WLAN profile from the same SoT
- [ ] FortiGate/HP template — proving vendor extensibility of the contract
- [ ] CI with GitHub Actions: render + batfish/pyntc validation on every PR
- [ ] Guest VRF + segmentation policy
- [ ] `--store-id 2` run of `netbox_populate.py` — the scaling demo, live
