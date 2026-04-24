# Lab Topology

Home-lab setup used to build and test this scenario.

---

## Physical / hypervisor layout

```
                    +--------------------+
                    |  Proxmox Host      |
                    |  (single node)     |
                    |                    |
                    |  +--------------+  |
                    |  | ISE VM       |  |
                    |  | 16 GB / 200G |  |
                    |  | eth0: mgmt   |  |
                    |  +--------------+  |
                    |                    |
                    |  +--------------+  |
                    |  | AD DC VM     |  |
                    |  | Win Server   |  |
                    |  | 4 GB / 80G   |  |
                    |  +--------------+  |
                    |                    |
                    |  +--------------+  |
                    |  | Test Client  |  |
                    |  | Win 10       |  |
                    |  +--------------+  |
                    |                    |
                    |  +--------------+  |
                    |  | Linux "IoT"  |  |
                    |  | Ubuntu VM    |  |
                    |  +--------------+  |
                    +--------+-----------+
                             |
                             | trunk
                             |
                    +--------+-----------+
                    |  Catalyst 9300     |
                    |  IOS-XE 17.x       |
                    +--------------------+
```

## VLANs

| VLAN | Name | Subnet | Use |
|---|---|---|---|
| 10 | MGMT | 10.10.10.0/24 | Switch mgmt, Proxmox mgmt |
| 50 | SERVERS | 10.10.50.0/24 | ISE VM, AD DC VM |
| 100 | EMPLOYEES | 10.10.100.0/24 | Corp laptops |
| 200 | VOICE | 10.10.200.0/24 | Phones |
| 300 | IOT | 10.10.30.0/24 | Cameras |
| 350 | PRINTERS | 10.10.35.0/24 | Printers |
| 400 | CONTRACTOR | 10.10.40.0/24 | Contractors |
| 500 | BYOD | 10.10.70.0/24 | BYOD |
| 998 | CRITICAL_VOICE | 10.10.198.0/24 | Critical voice fallback |
| 999 | CRITICAL_DATA | 10.10.199.0/24 | Critical data fallback |

## IPs

| Host | IP |
|---|---|
| Switch mgmt SVI (Vlan10) | 10.10.10.5 |
| Proxmox host | 10.10.10.10 |
| ISE PSN-01 | 10.10.50.11 |
| ISE PSN-02 | 10.10.50.12 |
| AD DC | 10.10.50.20 |
| Internal CA | 10.10.50.30 |
| Help portal (critical ACL target) | 10.10.20.10 |

## Proxmox bridge layout

```
vmbr0  → trunk to Cat 9300 (all VLANs)
vmbr1  → internal-only, management
```

VMs attach to `vmbr0` with a VLAN tag matching their role (ISE → 50, test client → untagged for dot1x testing).

## Cost-optimized alternative

If a physical Cat 9300 is not available:

- **Cisco CML** on Proxmox with a virtual Cat 9K image (requires license).
- **Containerlab** for lightweight alternatives — Arista cEOS, Nokia SR Linux — but IBNS 2.0 syntax won't carry over. Use only for RADIUS-flow testing.

A real Cat 9300 is the fastest path because the whole point is validating IBNS 2.0 syntax and critical-auth behavior end-to-end.

---

Next: [Test plan](test-plan.md)
