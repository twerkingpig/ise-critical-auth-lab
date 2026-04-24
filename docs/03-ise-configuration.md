# 03 — ISE Configuration

The ISE side of the design. Matches the switch policy in `02-ibns2-policy-explained.md`.

Tested against ISE 3.1 and 3.2. Paths may shift slightly in later releases.

---

## 1. Add the switch as a Network Device

**Administration → Network Resources → Network Devices → +Add**

```
Name:                CAMPUS-ACCESS-9300-01
IP Address:          10.10.30.5/32
Device Profile:      Cisco
Model:               Catalyst 9300
Software:            IOS-XE
Network Device Groups:
  Device Type:       Access-Switch
  Location:          Campus-Building-A

RADIUS Authentication Settings:
  Enable RADIUS:     yes
  Shared Secret:     <same as switch>
  CoA Port:          1700
```

Write all future policies against the **device groups**, not the individual device. Scaling to switch #2 becomes tagging, not rewriting.

## 2. Create the probe user

**Administration → Identity Management → Identities → Users → +Add**

```
Name:             ise-probe
Password Type:    Internal Users
Password:         <random 32 chars>
User Groups:      (empty)
Description:      Switch liveness probe — DO NOT ASSIGN ACCESS
```

No group membership. No authz rule matches it. DenyAccess catches it by default. The switch still gets a RADIUS response, which is all it needs to mark the server alive.

## 3. Authorization profiles

**Policy → Policy Elements → Results → Authorization → Authorization Profiles**

### EMPLOYEE-FULL-ACCESS

```
Access Type:      ACCESS_ACCEPT
VLAN:             EMPLOYEES (100)
Reauth Timer:     28800    ! 8 hours
```

### VOICE-ACCESS

```
Access Type:      ACCESS_ACCEPT
VLAN:             VOICE (200)
Advanced Attributes:
  cisco-av-pair = device-traffic-class=voice    ! CRITICAL
  cisco-av-pair = dACL=VOICE-PHONE-ACL          ! optional
```

`device-traffic-class=voice` is what tells the switch "use voice VLAN, not data." Without it, phones land on the data VLAN.

### IOT-CAMERAS

```
VLAN:             IOT (300)
dACL:             ACL-IOT-LIMITED
Reauth Timer:     86400    ! 24 hours
```

### PRINTERS-ACCESS

```
VLAN:             PRINTERS (350)
dACL:             ACL-PRINTER
Reauth Timer:     86400
```

### CONTRACTOR-LIMITED

```
VLAN:             CONTRACTOR (400)
dACL:             ACL-CONTRACTOR-INTERNET-ONLY
Reauth Timer:     3600
```

### BYOD-ACCESS (post-enrollment)

```
VLAN:             BYOD (500)
dACL:             ACL-BYOD
Reauth Timer:     28800
```

### BYOD-REDIRECT (pre-enrollment)

```
Common Tasks:
  Web Redirection:  Native Supplicant Provisioning
  ACL:              ACL-WEBAUTH-REDIRECT       ! must exist on switch by exact name
  Value:            BYOD Portal (default)
Advanced Attributes:
  Access Type:      ACCESS_ACCEPT
  dACL:             ACL-BYOD-REDIRECT-LIMITED
```

This is the three-legged stool from `05-byod-redirect.md`: url-redirect-acl, url-redirect, and a dACL pinning the client down during enrollment.

### CRITICAL-AUTH-RETURN

```
Access Type:      ACCESS_ACCEPT
VLAN:             CRITICAL_DATA (999)
dACL:             ACL-CRITICAL-AUTH
Reauth Timer:     3600
```

Used as a fallback when you want ISE to formally classify sessions that returned from a critical-auth state, for reporting and consistency. The *real* critical VLAN assignment still comes from the switch service-template during the actual outage.

## 4. Identity Source Sequence

**Administration → Identity Management → Identity Source Sequences → +**

```
Name:              CORP-ISS
Authentication Search List:
  1. AD-CORP
  2. LDAP-CORP-FALLBACK       ! generic LDAP connector to same DCs
  3. Internal Users           ! break-glass only
Advanced:
  If a selected identity store cannot be accessed:
     Treat as "User not found" and proceed to next
```

That last checkbox is what makes AD outages survivable.

## 5. Policy Set

**Policy → Policy Sets → +**

```
Name:              CAMPUS-WIRED-DOT1X
Conditions:        DEVICE:Device Type EQUALS Access-Switch
                   AND Radius:Service-Type EQUALS Framed
Allowed Protocols: Default Network Access
```

### Authentication rules

| # | Name | Condition | Identity Source | On Fail |
|---|---|---|---|---|
| 1 | MAB | `Wired_MAB` | Internal Endpoints | Continue |
| 2 | Dot1X | `Wired_802_1X` | CORP-ISS (incl. Certificate Store) | Drop |
| Default | — | — | — | DenyAccess |

### Authorization rules (top-down, first match wins)

| # | Name | Conditions | Profile |
|---|---|---|---|
| 1 | DENY-PROBE | `InternalUser:Name EQUALS ise-probe` | DenyAccess |
| 2 | CORP-LAPTOPS | `Certificate:Issuer CN EQUALS Internal-CA` AND `AD:ExternalGroups EQUALS Domain Computers` AND `EndPoints:LogicalProfile EQUALS Windows-Workstation` | EMPLOYEE-FULL-ACCESS |
| 3 | CORP-LAPTOPS-AD-DOWN | `Certificate:Issuer CN EQUALS Internal-CA` AND `Certificate:Template Name EQUALS Workstation-Authentication` AND `AD-CORP:ADHostExists EQUALS False` | EMPLOYEE-LIMITED-ACCESS |
| 4 | CORP-VOICE-PHONES | `EndPoints:LogicalProfile EQUALS Cisco-IP-Phone` | VOICE-ACCESS |
| 5 | IOT-CAMERAS | `EndPoints:LogicalProfile EQUALS IP-Camera-<Vendor>` AND `Radius:Service-Type EQUALS Call-Check` | IOT-CAMERAS |
| 6 | PRINTERS | `EndPoints:LogicalProfile EQUALS Printer` AND `Radius:Service-Type EQUALS Call-Check` | PRINTERS-ACCESS |
| 7 | CONTRACTORS | `AD:ExternalGroups EQUALS Contractors` | CONTRACTOR-LIMITED |
| 8 | BYOD-ENROLLED | `EndPoints:BYODRegistration EQUALS Yes` AND `AD:ExternalGroups EQUALS Employees` | BYOD-ACCESS |
| 9 | BYOD-REDIRECT | `AD:ExternalGroups EQUALS Employees` AND `EndPoints:BYODRegistration NOT_EQUALS Yes` | BYOD-REDIRECT |
| Default | — | — | DenyAccess |

### Why this order

- Probe-deny first so there's zero chance it matches anything else.
- Corp laptops with full AD check come before AD-down fallback; when AD is healthy, we use the stricter rule.
- Endpoint-profile-based rules come before generic AD rules so a BYOD user doesn't accidentally match something else.
- BYOD redirect is last among employee rules so enrolled devices hit the BYOD-ACCESS profile first.

## 6. Alarms to enable before go-live

**Administration → System → Alarms → Alarm Configuration**

Make these email/syslog:

- Active Directory Connection Failed
- No Accounting Start Received
- RADIUS Request Dropped
- Authentication Failure count above threshold (rate-of-change, not absolute)
- Certificate about to Expire (60 / 30 / 14 days)

## 7. Verification in ISE

**Operations → RADIUS → Live Logs** is the first place you look. Filter by:

- Calling Station ID (endpoint MAC)
- NAS IP (your switch)
- Authentication Status
- Identity (user or MAC)

**Operations → Reports → Endpoint and User → RADIUS Authentications** — historical trend. Useful after a scheduled outage to confirm most sessions survived.

---

Next: [04 — Failure modes](04-failure-modes.md)
