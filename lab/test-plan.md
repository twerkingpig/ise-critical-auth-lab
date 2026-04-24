# Test Plan

A seven-test matrix to prove the design works end-to-end. Run each, capture output, and compare against Expected. Every row should pass before you call this done.

---

## Prep

- `configs/switch-cat9300-base.ios` applied and edited for real IPs/secrets.
- `configs/switch-cat9300-ibns2.ios` applied.
- `configs/switch-cat9300-interface.ios` applied to at least one port (say Gi1/0/5).
- ISE configured per `docs/03-ise-configuration.md`.
- At least three test endpoints ready:
  - **Win 10 VM** with a cert from the internal CA (corp laptop role).
  - **Linux VM** with a static MAC pre-registered in ISE Internal Endpoints (IoT role).
  - **Unknown MAC** device — anything with no ISE record (negative test).

---

## The matrix

### Test 1 — Dot1X happy path

**Action:** Plug Win 10 VM into Gi1/0/5. ISE is up. User has valid cert.

**Expected:**
- `show access-session interface Gi1/0/5 details` shows:
  - `Status: Authorized`
  - `Method: dot1x, Authc Success`
  - `Server Policies: EMPLOYEE-FULL-ACCESS`
  - VLAN = 100

**Capture:** output of `show access-session interface Gi1/0/5 details`.

---

### Test 2 — MAB happy path

**Action:** Plug Linux "IoT" VM into Gi1/0/5. ISE is up. MAC pre-registered.

**Expected:**
- Port falls through dot1x (no supplicant) → MAB succeeds.
- `show access-session` shows:
  - `Method: mab, Authc Success`
  - `Server Policies: IOT-CAMERAS`
  - VLAN = 300

**Capture:** `show access-session interface Gi1/0/5 details`.

---

### Test 3 — Unknown MAC / unauthorized device

**Action:** Plug unknown MAC device into Gi1/0/5. ISE is up.

**Expected:**
- Dot1X times out (no supplicant) → MAB tried → fails (no ISE record) → `MAB_FAILED` class matches → `authentication-restart 60` kicks in.
- Port is unauthorized; no VLAN assigned.
- In 60s, switch retries.

**Capture:** `show access-session`, ISE Live Log showing DenyAccess.

---

### Test 4 — ISE down, fresh session (critical-auth)

**Action:** Shut the ISE VM. Wait 30 seconds for probes to mark PSN DEAD (confirm with `show aaa servers`). Plug Win 10 VM into Gi1/0/5 fresh.

**Expected:**
- `show aaa servers` shows both ISE servers in `DEAD` state.
- IBNS 2.0 hits `AAA_SVR_DOWN_UNAUTHD_HOST`.
- `show access-session` shows:
  - `Status: Authorized`
  - `Method: dot1x` (or mab, depending on what ran)
  - `Local Policies: Service Template: CRITICAL_AUTH_ACCESS`
  - VLAN = 999
- Client can reach the help portal (10.10.20.10) and nothing else.

**Capture:** `show aaa servers`, `show access-session interface Gi1/0/5 details`.

---

### Test 5 — ISE down, existing session (pause reauth)

**Action:** Do Test 1 (happy dot1x auth). Confirm session is authorized in VLAN 100. Then shut ISE. Wait for PSNs to hit DEAD. Wait for the reauth timer to fire (or lower it in a test profile to 120s).

**Expected:**
- `AAA_SVR_DOWN_AUTHD_HOST` class matches.
- `show access-session` still shows `Status: Authorized`, still in VLAN 100.
- Reauth counter does not advance; debug shows `pause reauthentication`.

**Capture:** `show access-session` before and after, `show aaa servers` while ISE is down.

---

### Test 6 — ISE recovery

**Action:** With Test 4's client sitting in critical-auth (VLAN 999), bring ISE back online. Wait ~30 seconds for probes to mark it ALIVE.

**Expected:**
- `show aaa servers` shows ALIVE.
- IBNS 2.0 fires `event aaa-available`.
- `IN_CRITICAL_AUTH` class matches → `clear-session`.
- Client reauths cleanly; lands in VLAN 100 with EMPLOYEE-FULL-ACCESS.
- ISE Live Log shows a fresh Authentication Succeeded for the client.

**Capture:** `show aaa servers`, `show access-session` before and after recovery, ISE Live Log screenshot.

---

### Test 7 — Phone (voice VLAN) during outage

**Action:** Plug a Cisco IP phone into Gi1/0/5 while ISE is down (ideally with a test client on the data side behind it).

**Expected:**
- `CRITICAL_AUTH_VOICE` service-template activates.
- Voice VLAN = 998; data VLAN = 999.
- Phone registers (or at least gets DHCP and CUCM reachability).

**Capture:** `show access-session`, phone registration state.

---

## Pass/fail tracking

Make a local `results-<date>.md` with this format:

```
| # | Test                         | Run at       | Result | Notes                 |
|---|------------------------------|--------------|--------|-----------------------|
| 1 | Dot1X happy path             | YYYY-MM-DD   | PASS   |                       |
| 2 | MAB happy path               | YYYY-MM-DD   | PASS   |                       |
| ...                                                                              |
```

Keep results files per test run — they're your evidence that the design works and your diff when something regresses later.

---

## What failure usually means

| Symptom | Likely cause |
|---|---|
| Test 1 fails with `Authc Failure` | Cert chain wrong, supplicant misconfigured, or EAP profile mismatch |
| Test 2 fails with DenyAccess in ISE | MAC not in Endpoint Identity Group, or authz rule condition wrong |
| Test 4 lands in `DOT1X_FAILED` instead of `AAA_SVR_DOWN_UNAUTHD_HOST` | `automate-tester` not working → switch doesn't know ISE is dead → treats as auth failure |
| Test 5 session is torn down instead of preserved | `event authentication-failure` class order is wrong, or `AAA_SVR_DOWN_AUTHD_HOST` class-map missing |
| Test 6 doesn't recover automatically | `event aaa-available` missing from policy-map, or `deadtime` too long — reduce deadtime for testing |

---

Next: [Verification commands](verification-commands.md)
