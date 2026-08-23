# NetBox data model — Branch #001

The model is designed so that **one store is data, not configuration**.
Adding store #002 = re-running the populate script with a different site
code. The Jinja2 templates never change.

## Addressing plan (the scaling story)

```
10.0.0.0/8                    container: "Branch network"
├── 10.<store>.0.0/20         per store   (store 1 -> 10.1.0.0/20)
│   ├── 10.<store>.0.0/24     VLAN 10  MGMT
│   ├── 10.<store>.1.0/24     VLAN 20  STAFF
│   ├── 10.<store>.2.0/24     VLAN 30  GUEST
│   ├── 10.<store>.3.0/24     VLAN 40  POS
│   └── 10.<store>.255.0/31   transit: rtr-edge <-> sw1
├── 10.255.0.0/16             infra loopbacks (router-IDs)
└── 100.64.1.0/31             WAN link store-001 <-> HQ (lab pseudo-WAN)
```

A /20 per store from 10/8 gives 4 096 stores per /8 block — plus the rest
of RFC1918 behind it. Store number = second octet, so the prefix *is* the
store identity (ops can read a store ID straight out of a traceroute).

VLAN IDs are **global constants** (10/20/30/40 mean the same thing in every
store); only the prefixes change. That is what makes one template serve
5 000 sites.

## Object tree

| Object | Value | Notes |
|---|---|---|
| Region | `be-nl` | one region for BE/NL estate |
| Site | `branch-001` (name "Branch 001", facility `001`) | site code drives IPAM math |
| Manufacturer | `Arista`, `FRRouting` | Cisco/Meraki/Fortinet added later |
| Device type | `ceos-lab`, `frr-container` | maps 1:1 to containerlab images |
| Platform | `eos` (napalm driver eos), `frr` | drives template + Ansible collection selection |
| Device role | `wan-edge`, `dist-switch`, `access-switch` | drives Ansible grouping |
| Devices | `rtr1-edge` (wan-edge/frr), `sw1` (dist-switch/eos), `sw2` (access-switch/eos) | |
| VLAN group | `store-001-vlans` (scope: site) | VID 10/20/30/40 |
| Prefixes | per table above, roles: `branch-mgmt`, `branch-user`, `branch-guest`, `branch-pos`, `transit`, `infra` | |
| VRF | `default` only | guest VRF is a roadmap item |
| Interfaces | routed / access / tagged (802.1q mode set per interface) | see below |
| IP addresses | SVIs, routed ports, WAN /31s | `assigned_object` = interface |
| Cables | eth pairs matching the clab topology | enables cable-trace validation |

## Interface modeling detail

| Device | Interface | 802.1Q mode | VLANs / IP |
|---|---|---|---|
| rtr1-edge | eth1 | routed | 100.64.1.1/31 |
| rtr1-edge | eth2 | routed | 10.1.255.1/31 |
| sw1 | Ethernet1 | routed | 10.1.255.0/31 |
| sw1 | Ethernet2 | tagged | 10,20,30,40 |
| sw1 | Ethernet3 | access | untagged 20 |
| sw1 | Vlan10/20/30/40 | SVI | .1 of each subnet |
| sw2 | Ethernet2 | tagged | 10,20,30,40 |
| sw2 | Ethernet3/4 | access | 30 / 40 |
| sw2 | Vlan10 | SVI | 10.1.0.3/24 |

The Ansible render playbook reads exactly these fields
(`mode.value`, `untagged_vlan.vid`, `tagged_vlans[].vid`, assigned IPs) —
nothing in the templates is hard-coded.

## What deliberately stays out (interview answers, not gaps)

- **Secrets**: NetBox keeps the data model; secrets belong in Vault/SOPS.
- **Wireless APs**: Meraki is API-managed; modeled here as a future
  `cloud-managed` device role synced via the Meraki dashboard API.
- **Full DHCP scope data**: IPAM reservations yes, lease engine no.
