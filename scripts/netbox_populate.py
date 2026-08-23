#!/usr/bin/env python3
"""
Populate NetBox with the Store #001 data model.

Idempotent: uses get-or-create on natural keys, safe to re-run.

Usage:
    pip install pynetbox
    export NETBOX_URL=http://localhost:8000
    export NETBOX_TOKEN=<api token>
    python3 scripts/netbox_populate.py [--store-id 1]
"""
import argparse
import os
import sys

import pynetbox

STORE_OCTET_BASE = 10  # 10.<store-id>.0.0/20

VLANS = [
    (10, "MGMT", "branch-mgmt", 0),
    (20, "STAFF", "branch-user", 1),
    (30, "GUEST", "branch-guest", 2),
    (40, "POS", "branch-pos", 3),
]


def get_or_create(endpoint, lookup: dict, payload: dict):
    obj = endpoint.get(**lookup)
    if obj:
        return obj
    return endpoint.create(**payload)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--store-id", type=int, default=1)
    args = parser.parse_args()
    sid = args.store_id

    url = os.environ.get("NETBOX_URL", "http://localhost:8000")
    token = os.environ.get("NETBOX_TOKEN")
    if not token:
        sys.exit("NETBOX_TOKEN env var required")

    nb = pynetbox.api(url, token=token)

    # --- organization ---------------------------------------------------
    region = get_or_create(
        nb.dcim.regions, {"slug": "be-nl"},
        {"name": "Belgium-Netherlands", "slug": "be-nl"},
    )
    site = get_or_create(
        nb.dcim.sites, {"slug": f"branch-{sid:03d}"},
        {
            "name": f"Branch {sid:03d}",
            "slug": f"branch-{sid:03d}",
            "status": "active",
            "region": region.id,
            "facility": f"{sid:03d}",
        },
    )

    # --- manufacturers / platforms / roles / device types ---------------
    arista = get_or_create(nb.dcim.manufacturers, {"slug": "arista"},
                           {"name": "Arista", "slug": "arista"})
    frrouting = get_or_create(nb.dcim.manufacturers, {"slug": "frrouting"},
                              {"name": "FRRouting", "slug": "frrouting"})

    eos = get_or_create(nb.dcim.platforms, {"slug": "eos"},
                        {"name": "Arista EOS", "slug": "eos",
                         "manufacturer": arista.id, "napalm_driver": "eos"})
    frr = get_or_create(nb.dcim.platforms, {"slug": "frr"},
                        {"name": "FRRouting", "slug": "frr",
                         "manufacturer": frrouting.id})

    roles = {}
    for slug, name, color in [
        ("wan-edge", "WAN Edge Router", "ff5722"),
        ("dist-switch", "Distribution Switch (L3)", "2196f3"),
        ("access-switch", "Access Switch (L2)", "4caf50"),
    ]:
        roles[slug] = get_or_create(
            nb.dcim.device_roles, {"slug": slug},
            {"name": name, "slug": slug, "color": color, "vm_role": False})

    dt_ceos = get_or_create(nb.dcim.device_types, {"slug": "ceos-lab"},
                            {"manufacturer": arista.id, "model": "cEOS-lab",
                             "slug": "ceos-lab", "u_height": 0})
    dt_frr = get_or_create(nb.dcim.device_types, {"slug": "frr-container"},
                           {"manufacturer": frrouting.id,
                            "model": "FRR container", "slug": "frr-container",
                            "u_height": 0})

    # --- IPAM ------------------------------------------------------------
    vlangroup = get_or_create(
        nb.ipam.vlan_groups, {"slug": f"store-{sid:03d}-vlans"},
        {"name": f"Store {sid:03d} VLANs", "slug": f"store-{sid:03d}-vlans",
         "scope_type": "dcim.site", "scope_id": site.id})

    roles_ipam = {}
    for slug, name in [("branch-mgmt", "Branch management"),
                       ("branch-user", "Branch user"),
                       ("branch-guest", "Branch guest"),
                       ("branch-pos", "Branch POS"),
                       ("transit", "Point-to-point transit"),
                       ("infra", "Infrastructure loopbacks")]:
        roles_ipam[slug] = get_or_create(
            nb.ipam.roles, {"slug": slug}, {"name": name, "slug": slug})

    base = STORE_OCTET_BASE
    get_or_create(nb.ipam.prefixes, {"prefix": "10.0.0.0/8"},
                  {"prefix": "10.0.0.0/8", "status": "container",
                   "description": "Branch network supernet"})
    get_or_create(nb.ipam.prefixes, {"prefix": f"{base}.{sid}.0.0/20"},
                  {"prefix": f"{base}.{sid}.0.0/20", "status": "container",
                   "site": site.id, "description": f"Store {sid:03d} allocation"})

    for vid, name, role_slug, third in VLANS:
        get_or_create(nb.ipam.vlans, {"vid": vid, "group": vlangroup.id},
                      {"vid": vid, "name": name, "group": vlangroup.id,
                       "site": site.id, "status": "active"})
        get_or_create(
            nb.ipam.prefixes, {"prefix": f"{base}.{sid}.{third}.0/24"},
            {"prefix": f"{base}.{sid}.{third}.0/24", "site": site.id,
             "status": "active", "role": roles_ipam[role_slug].id,
             "vlan": nb.ipam.vlans.get(vid=vid, group_id=vlangroup.id).id})

    get_or_create(nb.ipam.prefixes, {"prefix": f"{base}.{sid}.255.0/31"},
                  {"prefix": f"{base}.{sid}.255.0/31", "site": site.id,
                   "status": "active", "role": roles_ipam["transit"].id})
    get_or_create(nb.ipam.prefixes, {"prefix": "10.255.0.0/16"},
                  {"prefix": "10.255.0.0/16", "status": "container",
                   "role": roles_ipam["infra"].id})
    get_or_create(nb.ipam.prefixes, {"prefix": "100.64.1.0/31"},
                  {"prefix": "100.64.1.0/31", "status": "active",
                   "role": roles_ipam["transit"].id,
                   "description": "WAN store-001 <-> HQ (lab)"})

    # --- devices ----------------------------------------------------------
    def device(name, role, dtype, platform):
        return get_or_create(
            nb.dcim.devices, {"name": name, "site": site.id},
            {"name": name, "site": site.id, "role": roles[role].id,
             "device_type": dtype.id, "platform": platform.id,
             "status": "active"})

    rtr1 = device("rtr1-edge", "wan-edge", dt_frr, frr)
    sw1 = device("sw1", "dist-switch", dt_ceos, eos)
    sw2 = device("sw2", "access-switch", dt_ceos, eos)

    vlan = lambda vid: nb.ipam.vlans.get(vid=vid, group_id=vlangroup.id).id

    # --- interfaces (name, device, type, mode, untagged, tagged, desc) ----
    interfaces = [
        ("eth1", rtr1, "1000base-t", None, None, None, "WAN to hq-core"),
        ("eth2", rtr1, "1000base-t", None, None, None, "Routed handoff to sw1"),
        ("lo", rtr1, "virtual", None, None, None, "Loopback / router-id"),
        ("Ethernet1", sw1, "1000base-t", None, None, None, "UPLINK-rtr1-edge"),
        ("Ethernet2", sw1, "1000base-t", "tagged", None, [10, 20, 30, 40], "TRUNK-sw2"),
        ("Ethernet3", sw1, "1000base-t", "access", 20, None, "ACCESS-host-staff"),
        ("Vlan10", sw1, "virtual", None, None, None, "SVI MGMT"),
        ("Vlan20", sw1, "virtual", None, None, None, "SVI STAFF"),
        ("Vlan30", sw1, "virtual", None, None, None, "SVI GUEST"),
        ("Vlan40", sw1, "virtual", None, None, None, "SVI POS"),
        ("Ethernet2", sw2, "1000base-t", "tagged", None, [10, 20, 30, 40], "TRUNK-sw1"),
        ("Ethernet3", sw2, "1000base-t", "access", 30, None, "ACCESS-host-guest"),
        ("Ethernet4", sw2, "1000base-t", "access", 40, None, "ACCESS-host-pos"),
        ("Vlan10", sw2, "virtual", None, None, None, "SVI MGMT"),
    ]
    iface_ids = {}
    for name, dev, itype, mode, untagged, tagged, desc in interfaces:
        payload = {"device": dev.id, "name": name, "type": itype,
                   "enabled": True, "description": desc}
        if mode:
            payload["mode"] = mode
        if untagged:
            payload["untagged_vlan"] = vlan(untagged)
        if tagged:
            payload["tagged_vlans"] = [vlan(v) for v in tagged]
        obj = get_or_create(nb.dcim.interfaces,
                            {"device_id": dev.id, "name": name}, payload)
        iface_ids[(dev.name, name)] = obj.id

    # --- IP addresses ------------------------------------------------------
    ips = [
        ("rtr1-edge", "eth1", f"100.64.1.1/31"),
        ("rtr1-edge", "eth2", f"{base}.{sid}.255.1/31"),
        ("rtr1-edge", "lo", f"10.255.{sid}.1/32"),
        ("sw1", "Ethernet1", f"{base}.{sid}.255.0/31"),
        ("sw1", "Vlan10", f"{base}.{sid}.0.1/24"),
        ("sw1", "Vlan20", f"{base}.{sid}.1.1/24"),
        ("sw1", "Vlan30", f"{base}.{sid}.2.1/24"),
        ("sw1", "Vlan40", f"{base}.{sid}.3.1/24"),
        ("sw2", "Vlan10", f"{base}.{sid}.0.3/24"),
    ]
    for dev_name, ifname, addr in ips:
        get_or_create(
            nb.ipam.ip_addresses, {"address": addr},
            {"address": addr, "status": "active",
             "assigned_object_type": "dcim.interface",
             "assigned_object_id": iface_ids[(dev_name, ifname)]})

    # --- cables ------------------------------------------------------------
    def cable(a_dev_name, a_name, b_dev_name, b_name):
        existing = list(nb.dcim.cables.filter(
            device=a_dev_name, interface=a_name))
        if existing:
            return
        nb.dcim.cables.create(
            a_terminations=[{"object_type": "dcim.interface",
                             "object_id": iface_ids[(a_dev_name, a_name)]}],
            b_terminations=[{"object_type": "dcim.interface",
                             "object_id": iface_ids[(b_dev_name, b_name)]}],
            status="connected")

    cable("rtr1-edge", "eth2", "sw1", "Ethernet1")
    cable("sw1", "Ethernet2", "sw2", "Ethernet2")

    print(f"NetBox populated for store {sid:03d} "
          f"(site branch-{sid:03d}, {base}.{sid}.0.0/20)")


if __name__ == "__main__":
    main()
