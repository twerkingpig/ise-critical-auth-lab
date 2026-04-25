# 04 — Failure Modes

Every identity-based access design lives or dies by how it fails. This doc enumerates the specific failures, what the user sees, and what you do.

---

## 1. ISE PSN unreachable — fresh session

**Trigger:** New device plugs in while all PSNs are unreachable.

**Switch behavior:**
- `automate-tester` probes mark PSNs DEAD in ~15s.
- IBNS 2.0 `event authentication-failure` fires with class `AAA_SVR_DOWN_UNAUTHD_HOST`.
- Service-templates `CRITICAL_AUTH_ACCESS` and `CRITICAL_AUTH_VOICE` activate.
- Port authorized into VLAN 999 with `ACL-CRITICAL-AUTH`.
- Reauthentication paused.

**User sees:** Limited but functional access (DHCP, DNS, internal help portal, maybe internet via the critical ACL).

**Recovery:** When PSNs come back, `event aaa-available` fires, `IN_CRITICAL_AUTH` class matches, session is cleared, and the device reauths normally.

---

## 2. ISE PSN unreachable — existing session

**Trigger:** Session already authorized when PSNs go away. Session-timeout fires mid-outage, switch tries to reauth, RADIUS is dead.

**Switch behavior:**
- `event authentication-failure` fires with class `AAA_SVR_DOWN_AUTHD_HOST`.
- `pause reauthentication` — switch stops trying.
- `authorize` — session stays in its existing state.

**User sees:** Nothing. They keep working.

**Recovery:** When PSNs come back, `NOT_IN_CRITICAL_AUTH` class matches, reauth resumes on the next timer.

---

## 3. ISE up, AD integration broken

**Trigger:** AD join on PSN expires, DC unreachable, or AD service account locked out.

**Switch behavior:**
- Probe user is an *internal* user — probes still succeed.
- Switch marks PSN ALIVE.
- **No critical-auth fallback fires.**

**User sees:** DenyAccess. Can't get on the network.

**Mitigations:**
1. Identity Source Sequence with `proceed on process fail` → falls to `LDAP-CORP-FALLBACK` or `Internal Users`.
2. Parallel authz rule keyed on cert-only (`CORP-LAPTOPS-AD-DOWN` in `03-ise-configuration.md`) → grants a degraded employee profile.
3. ISE alarm on "Active Directory Connection Failed" → pages on-call before the helpdesk queue fills.
4. ISE alarm on rate-of-change of DenyAccess count → catches the silent-fail scenario.

**Lesson:** Fail-closed for security is correct, but without *detection* it becomes a silent user-facing outage.

---

## 4. Switch loses path to PSN-01 but PSN-02 reachable

**Trigger:** Routing flap, firewall rule, physical link. PSN-01 unreachable only from this switch.

**Switch behavior:**
- `automate-tester` on PSN-01 starts failing.
- After `dead-criteria time 5 tries 3` → PSN-01 marked DEAD on this switch.
- `aaa group server radius ISE-GROUP` has both PSNs → all auth fails over to PSN-02.
- `deadtime 15` prevents retry storms.

**User sees:** Nothing — auth works through PSN-02.

**Lesson:** Dead-criteria tuning and server-group ordering matter. Without them, the switch retries PSN-01 forever and adds 5-second delays to every auth.

---

## 5. MAB MAC spoofing

**Trigger:** Attacker unplugs an IoT camera, clones its MAC onto a laptop, plugs in.

**Base switch behavior:** Switch MABs the MAC, ISE authorizes → attacker lands in IOT VLAN.

**Defenses (layer them):**
- **Endpoint profiling** — ISE tracks DHCP fingerprint, HTTP User-Agent, CDP/LLDP, SNMP from switch. A "camera" that starts DHCPing Windows options and browsing HTTPS triggers **Anomalous Endpoint Detection**, which fires CoA and re-quarantines.
- **`ip device tracking`** on the switch plus **DHCP snooping** — fingerprint capture only works if the switch feeds ISE the data.
- **SGT enforcement** — even if the attacker lands in IOT VLAN, SGT-based ACLs at distribution prevent the IOT SGT from reaching sensitive segments.
- **Port security as belt-and-suspenders** — `switchport port-security maximum 1` on camera-only ports. Won't save you from a sophisticated attacker but raises the bar.
- **802.1X-with-MAB-first patterns** for devices that can actually do dot1x (printers: some support it).

**Trade-off:** Profiling-based detection is probabilistic. It catches obvious spoofs, not a patient attacker who mimics the endpoint's behavior exactly.

---

## 6. Certificate expiry (internal CA or ISE)

**Trigger:** ISE's admin cert, EAP cert, or an issuing CA cert expires.

**Switch behavior:** EAP-TLS handshake fails. Every dot1x attempt fails authoritatively. MAB fallback keeps MAB-only devices alive; dot1x devices (all corp laptops) are dead.

**User sees:** Mass auth failures.

**Mitigations:**
- ISE alarms on cert expiry at 60 / 30 / 14 days.
- Documented cert replacement runbook — *before* you need it.
- Never use the ISE "default self-signed" cert for EAP in production.

---

## 7. RADIUS load exceeds PSN capacity

**Trigger:** Short Session-Timeout + too many endpoints → PSN CPU pegs, TPS license exhausted.

**Switch behavior:** RADIUS requests start timing out. Dead-criteria may trip → critical-auth fires → cascade.

**Mitigations:**
- Long Session-Timeout for stable endpoints (8h+).
- CoA as the real revocation mechanism.
- Right-size PSN cluster: ~2,000 TPS per PSN node at healthy load.
- Load-balance PSNs (either native via server group, or with an F5/Nginx in front for wireless).

---

## 8. Infrastructure devices bypass auth on purpose

**Trigger:** Anything that affects ISE, RADIUS path, or AD.

**Switch behavior for ports outside the IBNS 2.0 framework:** Nothing. The port is unaffected. Traffic flows.

**User sees:** No impact.

**Why this is a feature, not a bug:** Routers, switches, APs, firewalls, and other infrastructure live on dedicated trusted ports configured *without* the `service-policy type control subscriber DOT1X_MAB_POLICY` line. Trust is enforced by which port the device plugs into, with `port-security` as a guardrail.

**Trade-off:** No ISE visibility for these devices — no Live Logs, no profiling, no CoA. This is acceptable because:

1. Infrastructure devices have stable, well-known identities anyway.
2. The reliability win is significant: an ISE outage cannot break routing.
3. Real-world enterprise practice draws this line at the same place: identity-based auth for users and endpoints, port-based trust for infrastructure.

**Revocation model:** Physical. Unplug the cable. There is no software equivalent on these ports, by design.

**Common infrastructure-bypass mistakes:**

- Forgetting `port-security` — then any device on that port gets infrastructure access.
- Using a global default port template that includes the IBNS 2.0 service-policy — the bypass port has to be explicitly different.
- Not labeling the port (description / cable label / patch panel sticker) — someone reuses it for a user device months later.

---

## The general pattern

Every failure mode has three layers:

1. **Detection** — switch and ISE both need to *know* something's wrong quickly.
2. **Degradation** — the system serves a reduced but functional experience automatically.
3. **Recovery** — when the underlying issue is fixed, sessions heal without manual intervention.

If any layer is missing, you have an outage instead of a degradation event.

---

Next: [05 — BYOD redirect](05-byod-redirect.md)
