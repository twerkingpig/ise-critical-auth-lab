# Verification Commands

The commands a network engineer actually lives in when debugging IBNS 2.0 + ISE.

---

## Switch side — "what's happening on this port?"

```
show access-session interface Gi1/0/5 details
```

The single most useful command. Tells you: auth status, method, Server-assigned policies, Local (service-template) policies, Session-Timeout, reauth state, URL redirect parameters, dACL.

```
show authentication sessions interface Gi1/0/5 details
```

Legacy alias, same info. Useful if you're on IOS-XS running older policy-map style.

```
show access-session
```

One-liner per active session. Great for scanning a whole switch.

```
show authentication sessions interface Gi1/0/5 policy
```

Shows which IBNS 2.0 policy-map is applied and current class matches.

## Switch side — "is ISE reachable?"

```
show aaa servers
```

Look for `RADIUS: id 1, priority 1, host 10.10.50.11` with state `UP` or `DEAD`. This is how you confirm dead-detection and `automate-tester` are working.

```
show radius statistics
```

Request / response / timeout counts. A growing `Access-Request Timeouts` number means RADIUS is suffering.

```
test aaa group ISE-GROUP ise-probe X auth new-code
```

Manually fire a RADIUS auth from the switch. Useful during initial bring-up to confirm shared secrets and reachability.

## Switch side — "why is this port in trouble?"

```
debug radius authentication
debug radius failover
debug access-session errors
debug access-session fsm
debug dot1x all
debug mab all
debug authentication feature all all
```

Pipe to a log file or tail the console. Turn off when you're done — `undebug all`.

Less noisy alternative:

```
conditional debug condition mac-address aabb.ccdd.eeff
debug access-session all
```

Only debug for that specific endpoint. Way easier to read.

## Switch side — "what did ISE push me?"

```
show ip access-lists        ! downloaded (ACS) ACLs appear here
show ip access-lists dynamic
show access-session interface Gi1/0/5 details | include ACL|Redirect
```

## ISE side — "what happened to this auth attempt?"

**Operations → RADIUS → Live Logs**

Filter by:
- Calling Station ID (MAC)
- Endpoint Identity (hostname or MAC)
- NAS IP (your switch IP)
- Authentication Status (Pass / Fail)

Click the magnifying glass on a row to get the **authentication detail** — shows which policy rule matched, which identity store hit, which authz profile was returned, which RADIUS attributes went out.

## ISE side — "is AD healthy?"

**Administration → Identity Management → External Identity Sources → Active Directory → (your AD) → Connection**

Should say `Operational`. If not, start there — this is the #1 cause of silent DenyAccess.

## ISE side — "what's the PSN load?"

**Operations → System → Reports → Dashboard**

Or command line on the PSN:

```
show cpu usage
show memory
show tech-support
```

## ISE side — "replay an auth"

Right-click a Live Log entry → **Run Authentication Diagnostics**. ISE will re-run the policy against the same inputs and tell you exactly which rule matched and why. Powerful tool, underused.

## Quick diagnostic flow

When a port "isn't working":

1. `show access-session interface GiX/Y/Z details` — is there even a session?
2. If no session: check `show dot1x interface GiX/Y/Z` and physical link.
3. If session but unauthorized: check ISE Live Log.
4. If Live Log shows DenyAccess: click in, see which rule matched (or didn't).
5. If Live Log shows timeout: check `show aaa servers` on the switch.
6. If AAA servers DEAD: check path to ISE, shared secret, `automate-tester` config.
7. If AAA servers UP but still timing out: check ISE PSN CPU/memory and ACL on the path.

---

## Safety reminder

`debug all` on a production switch can brown out the CPU. Use `conditional debug condition` to scope. Always:

```
undebug all
show debug        ! confirm
```

when finished.
