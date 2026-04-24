# 02 — IBNS 2.0 Policy-Map Explained

A line-by-line walkthrough of the access-port policy. Read this with `configs/switch-cat9300-ibns2.ios` open next to it.

---

## Why IBNS 2.0 at all

IBNS 1.0 (the legacy `authentication ...` commands) was sequential and hard to reason about. IBNS 2.0 (`policy-map type control subscriber`) is **event-driven**:

- Events: `session-started`, `authentication-failure`, `aaa-available`, `agent-found`, `violation`, etc.
- Class-maps: match conditions on the current session state.
- Actions: `authenticate`, `authorize`, `activate service-template`, `pause reauthentication`, `terminate`, etc.

The switch runs the policy like a mini state machine. You get clearer logic, RADIUS-down handling, and critical-auth in one framework.

## The building blocks

### Class-maps (conditions)

```
class-map type control subscriber match-all AAA_SVR_DOWN_UNAUTHD_HOST
 match result-type aaa-server down
 match authorization-status unauthorized
```

Reads as: "the current session is unauthorized AND the last AAA attempt failed because the server is down."

Other class-maps we use:

| Class-map | What it matches |
|---|---|
| `AAA_SVR_DOWN_AUTHD_HOST` | Server down, session was already authorized |
| `DOT1X_FAILED` | Dot1X ran and gave an authoritative failure |
| `DOT1X_NO_RESP` | No EAPoL from the endpoint (no supplicant) |
| `MAB_FAILED` | MAB ran and failed |
| `IN_CRITICAL_AUTH` | Built-in, matches sessions currently in critical-auth state |
| `NOT_IN_CRITICAL_AUTH` | Built-in, the opposite |

### Service templates (what to apply)

```
service-template CRITICAL_AUTH_ACCESS
 vlan 999
 access-group ACL-CRITICAL-AUTH
 inactivity-timer 60
```

Equivalent of "local authz profile" — VLAN, ACL, timers, all bundled. Activated by the policy-map during critical auth.

### The policy-map

```
policy-map type control subscriber DOT1X_MAB_POLICY
 event session-started match-all
  10 class always do-until-failure
   10 authenticate using dot1x priority 10

 event authentication-failure match-first
  10 class AAA_SVR_DOWN_UNAUTHD_HOST do-until-failure
   10 activate service-template CRITICAL_AUTH_ACCESS
   20 activate service-template CRITICAL_AUTH_VOICE
   30 authorize
   40 pause reauthentication
  20 class AAA_SVR_DOWN_AUTHD_HOST do-until-failure
   10 pause reauthentication
   20 authorize
  30 class DOT1X_FAILED do-until-failure
   10 terminate dot1x
   20 authenticate using mab priority 20
  40 class DOT1X_NO_RESP do-until-failure
   10 terminate dot1x
   20 authenticate using mab priority 20
  50 class MAB_FAILED do-until-failure
   10 terminate mab
   20 authentication-restart 60

 event aaa-available match-all
  10 class IN_CRITICAL_AUTH do-until-failure
   10 clear-session
  20 class NOT_IN_CRITICAL_AUTH do-until-failure
   10 resume reauthentication

 event agent-found match-all
  10 class always do-until-failure
   10 terminate mab
   20 authenticate using dot1x priority 10

 event violation match-all
  10 class always do-all
   10 restrict
```

## Flow, in English

1. **Device plugs in.** `event session-started` fires. Start dot1x.
2. **Supplicant answers** → dot1x exchange runs against ISE. Success → ISE returns authz → session authorized.
3. **No supplicant** → after the EAPoL timeout, `DOT1X_NO_RESP` matches. Terminate dot1x, start MAB.
4. **Dot1X fails authoritatively** (bad cert, user creds wrong) → `DOT1X_FAILED` matches. Fall to MAB.
5. **MAB fails** → `MAB_FAILED` matches. Terminate MAB, wait 60 seconds, try again (back to dot1x).
6. **RADIUS dead, fresh device** → `AAA_SVR_DOWN_UNAUTHD_HOST` matches. Apply CRITICAL_AUTH templates. Authorize. Pause reauth so we're not hammering dead servers.
7. **RADIUS dead, existing session** → `AAA_SVR_DOWN_AUTHD_HOST` matches. Pause reauth. Keep the session as-is. User keeps working.
8. **RADIUS comes back** → `event aaa-available` fires. If the session is in critical auth → clear it and reauth cleanly. If not → resume the normal reauth timer.
9. **Late supplicant appears mid-MAB** → `event agent-found` fires. Kill MAB and switch to dot1x. Common for PXE/WoL flows.
10. **Policy violation** (a second MAC appears on a single-auth port, for instance) → restrict the port.

## Why ordering inside an event matters

Within `event authentication-failure match-first`, the first class to match wins. Order:

1. Server-down, unauthed (brand-new plug-in during outage) — **first** so we don't misclassify it as a dot1x failure.
2. Server-down, authed (reauth timer fired mid-outage) — **next** so we preserve the session.
3. Dot1x-failed → try MAB.
4. Dot1x-no-response → try MAB.
5. MAB-failed → restart timer.

If you reversed 1 and 3, a RADIUS timeout during a dot1x attempt could land in `DOT1X_FAILED` (the switch sees its own timeout as a failure) and you'd fall to MAB instead of critical-auth. Bad — you'd MAB a corp laptop into an unknown state.

## Parameters worth tuning later

- **`authentication-restart 60`** — seconds between retry cycles after a full failure. 60 is gentle; drop to 30 in labs for faster iteration.
- **`dot1x timeout tx-period 7`** / **`max-reauth-req 2`** — how long the switch waits for EAPoL responses. Tune down to 3–5 seconds in a lab to speed up MAB fallback.
- **Service-template `inactivity-timer`** — how long a session can be silent before the switch tears it down. 60 sec in CRITICAL is aggressive; raise in production.

## What to verify on a working port

```
show access-session interface Gi1/0/5 details
```

Look for:
- `Status: Authorized`
- `Domain: DATA` (or VOICE)
- `Server Policies: <your ISE authz profile>` (or `CRITICAL_AUTH_ACCESS` during an outage)
- `Handle: <some number>` (means there's an active session; missing handle = nothing attached)
- `Method status list: dot1x: Authc Success` (or MAB: Authc Success)

---

Next: [03 — ISE configuration](03-ise-configuration.md)
