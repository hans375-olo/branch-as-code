# Design decisions — read this before the interview

Every choice in this repo answers a question an interviewer is likely to ask.
This doc pairs the decision with the answer.

## "Why NetBox — and why does the lab also work without it?"

NetBox is the industry-standard network Source of Truth: IPAM, DCIM, VLANs,
cables, a real REST API, and a mature Ansible collection. But the pipeline is
built around a **normalized variable contract**, not around NetBox: the
templates receive `device` / `vlans` / `interfaces`, and they cannot tell
whether those came from the NetBox API or from YAML files. The static
inventory under `ansible/inventories/static/` is not a toy fallback — it is
the same contract with zero infrastructure, which is also how you'd prototype
before the SoT exists.

The point this demonstrates: *the SoT is an implementation detail; the data
model is the design.*

## "Why is BGP policy in group_vars and not in NetBox?"

Deliberate separation of concerns:

- **NetBox owns topology and IPAM** — what exists, where, which addresses.
- **group_vars owns routing policy** — ASNs, neighbors, redistribution.

NetBox can store BGP sessions, but in practice routing *policy* is design
intent, not inventory. Keeping it in versioned vars keeps the SoT clean and
makes the policy reviewable in a pull request.

## "Isn't NetBox too heavy for a 16 GB laptop?"

Measured against the budget: netbox-docker (app + worker + PostgreSQL +
Redis) runs at roughly 2–2.5 GB. Together with the lab (~3.5 GB) that is
~6 GB total — comfortable. If it ever gets tight, in order of preference:

1. **Tune netbox-docker down** (fewer gunicorn workers, disable housekeeping
   intervals) — same tool, smaller footprint.
2. **Keep NetBox in the cloud / on a small VPS** and point the playbooks at
   it — arguably the *more realistic* architecture anyway; nobody runs the
   corporate SoT on a field laptop.
3. **Static YAML SoT** (included) — zero RAM, same pipeline, same templates.

What was rejected: phpIPAM (IPAM only — no device/interface/cable model, so
the templates would lose their input) and Nautobot — which deserves more
than a parenthesis, because it's the obvious challenger:

### Why NetBox over Nautobot, specifically

- **Market signal.** NetBox is the name that appears in job postings and the
  SoT most network teams — MSPs included — actually recognize. For a
  portfolio whose job is to start conversations, recognition matters.
- **Time-to-demo.** The `netbox-docker` + `nb_inventory` + `pynetbox` path
  is the most documented stack in network automation. More examples to stand
  on means fewer hours burned on tooling instead of the demo.
- **Data-model fit.** NetBox's DCIM/IPAM is exactly the shape of the branch
  standardization problem: sites, devices, interfaces, cables, prefixes,
  VLANs. Nautobot's differentiators — the jobs framework, GraphQL,
  Git-as-a-data-source, and especially the **Golden Config app** (which
  literally does render + compliance + remediation) — are genuinely
  excellent, but they solve problems this demo doesn't have yet, at the
  price of a steeper learning curve and a heavier platform.
- **Honest credit where due:** if a target org already runs Nautobot, that
  is a perfectly good reason to use it — Golden Config in particular is a
  production-grade version of what this repo demonstrates. The
  contract-first design here means swapping SoT is an inventory-plugin
  change, not a rewrite. Concepts transfer 1:1; that's the point of the
  abstraction.

## "Why cEOS and not Cisco images?"

- **Cisco IOL/CML images** are license-gated and not redistributable — a
  public portfolio repo cannot rely on them, and containerlab doesn't run
  CML VMs natively without vrnetlab wrappers (heavy: a full VM per node,
  1–2 GB+ each and slow boot).
- **cEOS** is free with registration, container-native (~1.5 GB, boots in
  seconds), and its CLI is close enough to IOS to demonstrate VLANs, trunks,
  SVIs, STP — plus it has eAPI, which makes the Ansible push *API-based*
  instead of screen-scraping SSH.
- **FRR** at ~100 MB per node covers routing/BGP where a Cisco CLI adds
  nothing.
- Honest answer for Simac: *"For IOS XE-specific behavior I'd keep the CML
  lab I already have; for a portable standardization demo, cEOS/FRR is the
  right trade."*

## "How does this scale to 5 000 stores?"

Three mechanisms, all demonstrable:

1. **Addressing algebra**: store *N* = `10.N.0.0/20`, VLANs are global
   constants. The store's entire IPAM is a function of one integer.
2. **The populate script takes `--store-id`**. Store #002 is a command, not
   a project. (Running `python3 scripts/netbox_populate.py --store-id 2`
   live in an interview is the money shot.)
3. **Templates are store-agnostic**: they consume whatever the SoT says.
   Adding a store adds zero template code.

## "How do you deploy safely?"

- `deploy.yml` uses **full-config replace with backup** on EOS
  (`replace: config, backup: true`) — declarative, idempotent, rollbackable.
- FRR configs are bind-mounted files; deployment is *render → redeploy*, a
  GitOps pattern: the repo is the desired state, the container is disposable.
- `verify.yml` is part of the change, not an afterthought: LLDP neighbor
  checks, a parsed JSON assertion that eBGP is `Established`, and
  end-to-end pings across every layer of the path.

## "Where do Meraki and Fortinet fit?"

- **Meraki**: cloud-managed — the SoT stays NetBox, but the *deploy* step
  targets the Meraki Dashboard API instead of a device CLI. Same data,
  different transport. Roadmap item with the slot already reserved.
- **Fortinet**: FortiGate = one more Jinja2 template + one more platform in
  NetBox. The contract (device/vlans/interfaces) already carries everything
  a FortiGate branch profile needs for L2/L3 handoff.

## Known limitations (say them before they ask)

- One IP per interface in the normalization logic (fine for this model;
  noted in `render.yml`).
- No secrets management yet — that's Vault/SOPS, next iteration.
- hq-core is deliberately **not** managed: it's the "provider". The SoT
  scopes your own estate, which is itself a design boundary worth naming.
