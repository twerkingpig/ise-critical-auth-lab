# ise-critical-auth-lab 

> Cisco ISE + IBNS 2.0 lab — real switch & ISE configs for critical-auth segmentation and failure-mode testing on Catalyst 9300.

A practical reference lab for building identity-based network access on a Cisco Catalyst 9300 with Cisco ISE 3.x, using IBNS 2.0 policy-maps, critical-auth VLAN fallback, and graceful failure handling when ISE or AD is unavailable.

This repo is built the way a network engineer actually learns: by designing, configuring, breaking, and observing — not by reading.

---

## Scenario

Greenfield campus, ~1,500 endpoints spread across six classes:

| Class | Count | Notes |
|---|---|---|
| Corp laptops | 700 | Windows, AD-joined, internal-CA certs |
| Corp VoIP phones | 400 | Cisco IP phones, CDP/LLDP-capable |
| BYOD phones | 200 | Personal iOS/Android |
| IoT cameras | 100 | No supplicant — MAB |
| Printers | 50 | No supplicant — MAB |
| Contractor laptops | 50 | Not AD-joined, no cert |

Access switches: Catalyst 9300, IOS-XE 17.x.
Identity: Cisco ISE 3.x (2 PAN/MnT + 2 PSN), AD-integrated.
Licensing: TrustSec available (SGTs considered, not used in this iteration).

### Constraints

- Wired and wireless users get the same policy.
- An ISE outage must not break the office.
- Contractors get internet + a couple of internal SaaS apps, nothing else.
- IoT cameras must never reach user subnets.

---

## Design principles

1. **Fail-closed for security, fail-graceful for availability.** DenyAccess is the default; critical-auth VLAN carries fresh sessions during an outage; already-authorized sessions coast through.
2. **Compound conditions at the policy layer.** A cert alone is not identity. An AD group alone is not identity. Identity is the *and* of several weak signals.
3. **Push over poll.** CoA drives real-time revocation; `Session-Timeout` is a safety net, not a control.
4. **Identity sources must degrade.** AD-down cannot mean campus-down. Identity Source Sequences with `proceed on process fail` matter.
5. **Monitor → Low-Impact → Closed.** Never go straight to closed mode in production.
6. **Probes that fail are safer than probes that succeed.** The switch only needs a RADIUS *response* to mark a server alive.

---

## Repository layout

```
ise-critical-auth-lab/
├── README.md                          # You are here
├── docs/
│   ├── 01-design-overview.md          # Mental model, endpoint classes, constraints
│   ├── 02-ibns2-policy-explained.md   # Policy-map walkthrough
│   ├── 03-ise-configuration.md        # NAD, probe user, profiles, policy set
│   ├── 04-failure-modes.md            # AD-down, ISE-down, MAC spoofing, graceful degradation
│   ├── 05-byod-redirect.md            # The three RADIUS attributes, and the gotchas
│   ├── 06-lab-build.md                # Real lab build: PSN configs + cleaned switch config
│   └── screenshots/                   # ISE admin UI captures
├── configs/
│   ├── switch-cat9300-base.ios        # Reference: AAA + RADIUS + server tracking
│   ├── switch-cat9300-ibns2.ios       # Reference: policy-map + service-templates
│   ├── switch-cat9300-interface.ios   # Reference: access port config
│   ├── lab-build/
│   │   └── lab-switch-running-config.ios  # Real lab switch, sanitized & cleaned
│   └── acls/
│       ├── acl-critical-auth.ios
│       ├── acl-webauth-redirect.ios
│       └── acl-contractor.ios
├── lab/
│   ├── topology.md                    # Home lab layout (Proxmox + ISE VM + 9300 + clients)
│   ├── test-plan.md                   # Seven-test failure-mode matrix
│   └── verification-commands.md       # show / debug commands worth living in
└── .gitignore
```

---

## Quick start (home lab)

1. Spin up ISE 3.x on Proxmox (eval license, 16 GB RAM, 200 GB disk).
2. Cable a Cat 9300 to the Proxmox host.
3. Paste `configs/switch-cat9300-base.ios` after editing IP/secrets.
4. Paste `configs/switch-cat9300-ibns2.ios`.
5. Apply `configs/switch-cat9300-interface.ios` to an access-port range.
6. In ISE: add the NAD, create the probe user, build the Policy Set per `docs/03-ise-configuration.md`.
7. Plug in a test client. Verify with `show access-session interface … details`.
8. Run `lab/test-plan.md` — especially the ISE-down drill.

---

## Status

Lab reference built in session with **Toni** (network engineering copilot). Iterations to come as real-lab results come in.

## License

Configs and docs are provided for educational purposes. Not affiliated with Cisco. Validate against your own environment before any production use.
