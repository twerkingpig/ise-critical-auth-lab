# 01 — Design Overview

The mental model for this lab. Read this first.

---

## What we are actually building

A wired access-edge that:

1. Authenticates every endpoint using 802.1X where possible and MAB everywhere else.
2. Places each endpoint into an appropriate segment (VLAN + ACL).
3. Survives an ISE outage without bricking the office.
4. Survives an AD outage with a degraded but still-functional path.
5. Logs enough that an on-call engineer can figure out what happened at 2 AM.

## The endpoint classes

~1,500 endpoints total, six classes:

| Class | Auth method | Identity anchor | Segment |
|---|---|---|---|
| Corp laptops | 802.1X (EAP-TLS) | Cert from internal CA **AND** AD group `Domain Computers` **AND** endpoint profile `Windows-Workstation` | `EMPLOYEES` (VLAN 100) |
| Corp VoIP phones | 802.1X (EAP-TLS) with fallback to MAB + CDP | Cert or CDP/LLDP + endpoint profile `Cisco-IP-Phone` | `VOICE` (VLAN 200) |
| BYOD phones | 802.1X after onboarding; redirect to portal if unenrolled | AD user in `Employees` + registered endpoint | `BYOD` (VLAN 500) |
| IoT cameras | MAB | MAC + endpoint profile `IP-Camera-<Vendor>` + `Service-Type EQUALS Call-Check` | `IOT` (VLAN 300) |
| Printers | MAB | MAC + endpoint profile `Printer` | `PRINTERS` (VLAN 350) |
| Contractor laptops | 802.1X (PEAP-MSCHAPv2) | AD group `Contractors` | `CONTRACTOR` (VLAN 400) |

## Authentication order on the port

Under IBNS 2.0, authentication is **event-driven**, not sequential the way legacy `authentication order` was. Still, the effective flow is:

```
session-started
   └── try dot1x first
          ├── supplicant responds  → EAP exchange with ISE
          ├── no EAPoL response     → fall to MAB
          └── dot1x fails           → fall to MAB
```

Why dot1x first, always? Because if MAB ran first, an attacker could unplug a known device, clone its MAC, and never get challenged. Dot1x gives you a chance to demand a cert or credential *before* you trust the MAC.

## Segmentation model

This lab uses **VLAN-per-class + dACLs at the access switch**.

Rationale:

- Well understood, troubleshoots easily, works in every training environment.
- Doesn't require TrustSec propagation across the fabric.
- Works today even if TrustSec is "on the roadmap."

Trade-offs we accept:

- VLAN sprawl at access.
- ACL maintenance (centrally at distribution *or* pushed from ISE as dACLs).
- Segmentation is tied to L2 boundaries.

A future iteration can move enforcement into **SGTs** so that enforcement follows the user regardless of VLAN.

## Availability model

Three failure modes to plan for:

| Failure | What the switch does | What the user sees |
|---|---|---|
| ISE PSN fully unreachable, fresh session | Matches `AAA_SVR_DOWN_UNAUTHD_HOST` → CRITICAL_AUTH service-template → VLAN 999 + restricted ACL | Limited but functional |
| ISE PSN fully unreachable, existing session | Matches `AAA_SVR_DOWN_AUTHD_HOST` → `pause reauthentication` → session preserved | No change |
| ISE up but AD integration down | DenyAccess (no rule matches) | Rejected — see Failure Modes doc for mitigations |

## Revocation model

Real-time revocation happens via **CoA (Change of Authorization)**, not by polling.

- User disabled in AD → ISE detects → pushes CoA-Reauth → session killed or moved.
- Posture failure → CoA moves the client to quarantine.
- pxGrid event from SIEM or firewall → CoA kills the session.

`Session-Timeout` is long (8–12 h for corp, 24 h for IoT). It's a safety net, not the mechanism.

## Rollout posture

Three phases. Do not skip:

1. **Monitor Mode** — open authentication, policy evaluated but not enforced. Fix everything that fails before you enforce.
2. **Low-Impact Mode** — pre-auth ACL on the port allowing essentials (DHCP, DNS, AD, basic internet), dot1x enforced but not blocking non-matching traffic.
3. **Closed Mode** — no traffic until authorized. Production target.

Greenfield lets you be aggressive, but the rollout sequence still applies when you cut over real devices.

---

Next: [02 — IBNS 2.0 policy-map explained](02-ibns2-policy-explained.md)
