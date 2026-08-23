     1	# branch-as-code
     2	
     3	**How I would standardize 5 000 branch sites: one reference store, fully
     4	data-driven, rendered from a Source of Truth, deployed and verified by
     5	Ansible, running as a lightweight Containerlab topology on a laptop.**
     6	
     7	```
     8	                       ┌───────────┐
     9	                       │  hq-core  │  FRR · AS65000 · "HQ / provider"
    10	                       └─────┬─────┘
    11	                             │  100.64.1.0/31 · eBGP
    12	                       ┌─────┴─────┐
    13	                       │ rtr1-edge │  FRR · AS65001 · store WAN edge
    14	                       └─────┬─────┘
    15	                             │  10.1.255.0/31 · routed handoff
    16	                       ┌─────┴─────┐
    17	                  ┌────│    sw1    │  cEOS · L3 distribution (SVIs, gateway)
    18	                  │    └───────────┘
    19	                  │ trunk (VLAN 10/20/30/40)
    20	             ┌────┴────┐
    21	             │   sw2   │  cEOS · L2 access
    22	             └─┬────┬──┘
    23	          guest    pos
    24	```
    25	
    26	**VLANs are global constants** — 10 MGMT / 20 STAFF / 30 GUEST / 40 POS mean
    27	the same thing in every store. **Only the prefix changes**:
    28	store *N* gets `10.N.0.0/20`. The templates never change; a new store is
    29	data, not configuration.
    30	
    31	## The pipeline
    32	
    33	```
    34	NetBox (or static YAML)          Jinja2 golden configs         Containerlab
    35	┌──────────────────┐            ┌────────────────────┐        ┌─────────────┐
    36	│ site / devices   │  render    │ configs/sw1/...    │ deploy │ cEOS, FRR   │
    37	│ VLANs / prefixes │ ─────────► │ configs/rtr1-edge/ │ ─────► │ alpine      │
    38	│ interfaces / IPs │            │                    │ verify │             │
    39	└──────────────────┘            └────────────────────┘        └─────────────┘
    40	```
    41	
    42	Same templates, same playbooks — swap the inventory to swap the SoT:
    43	
    44	```bash
    45	make render            # static YAML SoT (zero infrastructure)
    46	make render-netbox     # NetBox SoT (dynamic inventory + API lookups)
    47	```
    48	
    49	## Quickstart (from a bare Ubuntu/Debian machine or VM)
    50	
    51	```bash
    52	# 0. Install the toolchain (containerlab's setup script also installs
    53	#    Docker itself if it's missing)
    54	sudo apt update && sudo apt install -y git make ansible python3-jmespath
    55	curl -sL https://containerlab.dev/setup | sudo -E bash -s all
    56	sudo usermod -aG docker $USER   # then log out & back in
    57	
    58	# 1. Get the repo
    59	git clone https://github.com/hans375-olo/branch-as-code.git
    60	cd branch-as-code
    61	
    62	# 2. Import the cEOS image (one-time, free arista.com account — see below).
    63	#    docker import accepts .tar / .tar.gz / .tar.xz alike.
    64	docker import cEOS64-lab-4.33.1F.tar ceos:4.33.1F
    65	
    66	# 3. Bring up the reference branch — comes up fully configured
    67	#    (baseline configs in configs/ are bind-mounted)
    68	make lab-up
    69	
    70	# 4. Render golden configs from the SoT and deploy them
    71	cd ansible && ansible-galaxy collection install -r requirements.yml && cd ..
    72	make render && make deploy
    73	
    74	# 5. Prove it: LLDP, VLANs, BGP state assertion, end-to-end pings
    75	make verify
    76	
    77	# 6. Add the real SoT (optional — lab works fine without it)
    78	git clone https://github.com/netbox-community/netbox-docker ../netbox-docker
    79	make netbox-up
    80	export NETBOX_URL=http://localhost:8000 NETBOX_TOKEN=<token>
    81	pip install --break-system-packages pynetbox   # or use a venv
    82	make populate          # builds the entire branch-001 data model
    83	make render-netbox     # same templates, data now from NetBox
    84	```
    85	
    86	No `make`? Every target is a one-liner — read the Makefile and run the
    87	commands directly.
    88	
    89	## RAM budget (designed for 4 cores / 16 GB)
    90	
    91	| Component | Image | Count | ~RAM each | Subtotal |
    92	|---|---|---|---|---|
    93	| Store edge + HQ | `quay.io/frrouting/frr` | 2 | ~100 MB | 0.2 GB |
    94	| Switches | `ceos:4.33.1F` | 2 | ~1.5 GB | 3.0 GB |
    95	| Endpoints | `alpine` | 3 | ~10 MB | ~0 GB |
    96	| NetBox | netbox-docker (app, worker, PostgreSQL, Redis) | 1 stack | — | ~2.5 GB |
    97	| **Total** | | | | **≈ 6 GB** |
    98	
    99	Leaves headroom for the OS and an IDE. Free-alternative swap if you want
    100	to skip the Arista download: replace cEOS with Nokia SR Linux
    101	(`ghcr.io/nokia/srlinux`, free to pull, ~1 GB) — only `templates/eos.j2`
    102	and two lines of the topology change.
    103	
    104	## Getting the cEOS image (the only non-trivial prerequisite)
    105	
    106	cEOS is free but gated behind a (free) arista.com account:
    107	
    108	1. Register at arista.com → *Software Downloads* → cEOS-lab → download
    109	   `cEOS64-lab-4.33.1F.tar`
    110	2. `docker import cEOS64-lab-4.33.1F.tar ceos:4.33.1F`
    111	
    112	The download is a plain `.tar` (earlier cEOS releases shipped as `.tar.xz`) —
    113	`docker import` handles both transparently. The important thing is that the
    114	tag (`ceos:4.33.1F`) matches the `image:` lines in
    115	`containerlab/branch-001.clab.yml`.
    116	
    117	## Repo map
    118	
    119	```
   120	├── containerlab/branch-001.clab.yml   # the reference store topology
   121	├── configs/                           # golden configs (bind-mounted into nodes)
   122	│   ├── hq-core/  rtr1-edge/  sw1/  sw2/
   123	├── netbox/data-model.md               # the data model, in words and tables
   124	├── scripts/netbox_populate.py         # idempotent NetBox builder (pynetbox)
   125	├── templates/                         # Jinja2 golden-config templates per platform
   126	│   ├── eos.j2
   127	│   └── frr.j2
   128	├── ansible/
   129	│   ├── render.yml                     # SoT -> normalized contract -> template -> configs/
   130	│   ├── deploy.yml                     # eAPI config replace (EOS), vtysh reload (FRR)
   131	│   ├── verify.yml                     # state collection + BGP assertion + e2e pings
   132	│   ├── inventories/
   133	│   │   ├── netbox.yml                 # dynamic inventory from NetBox
   134	│   │   └── static/                    # zero-infra fallback SoT (same contract!)
   135	│   └── group_vars/                    # routing policy + platform connection vars
   136	├── dev/                               # the workstation container (code-server IDE,
   137	│   │                                  # Python, Ansible, pyATS, containerlab, docker CLI)
   138	│   ├── Dockerfile.dev
   139	│   └── docker-compose.dev.yml
   140	└── docs/
   141	    ├── design-decisions.md            # design rationale and trade-offs
   142	    └── host-and-toolchain.md          # Windows -> VMware -> Ubuntu VM -> containers
   143	```
   144	
   145	## Roadmap
   146	
   147	- [ ] `svc-dhcp` node + `ip helper-address` — centralized DHCP, NetBox as IPAM
   148	- [ ] Meraki dashboard API module — cloud-managed WLAN profile from the same SoT
   149	- [ ] FortiGate/HP template — proving vendor extensibility of the contract
   150	- [ ] CI with GitHub Actions: render + batfish/pyntc validation on every PR
   151	- [ ] Guest VRF + segmentation policy
   152	- [ ] `--store-id 2` run of `netbox_populate.py` — the scaling demo, live
   153	
