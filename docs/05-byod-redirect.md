# 05 — BYOD Redirect

The three-legged stool. Most BYOD breakage is one of these three pieces being wrong.

---

## What the flow actually looks like

1. Employee's personal iPhone associates to corp Wi-Fi (or plugs into a wired port).
2. EAP-PEAP to ISE using the user's AD creds succeeds.
3. ISE runs authz: user is in `Employees`, endpoint is not registered (`BYODRegistration != Yes`) → matches `BYOD-REDIRECT` rule.
4. ISE sends Access-Accept with **three** RADIUS attributes.
5. Switch/WLC:
   - Applies the dACL → locks the endpoint down to essentials.
   - Intercepts HTTP/HTTPS traffic matching the redirect ACL.
   - Sends the user's browser to the ISE portal URL.
6. User completes device registration (SCEP cert issuance + profile install).
7. ISE fires CoA-Reauth.
8. Switch reauths → new session → `BYOD-ENROLLED` rule matches → full BYOD VLAN.

## The three attributes

### 1. `url-redirect-acl`

```
cisco-av-pair = url-redirect-acl=ACL-WEBAUTH-REDIRECT
```

**Meaning:** "Which traffic should I intercept and redirect?"

**ISE does not push the ACL.** It references an ACL **that must already exist on the switch by exact name**. If the ACL is missing, RADIUS succeeds but redirection silently fails. Classic onboarding breakage.

Typical ACL:

```
ip access-list extended ACL-WEBAUTH-REDIRECT
 deny   udp any any eq domain
 deny   udp any any eq bootps
 deny   ip any host 10.10.50.11      ! ISE PSN-01 — don't redirect to ISE itself
 deny   ip any host 10.10.50.12
 permit tcp any any eq www
 permit tcp any any eq 443
```

**Read it backward:** `permit = redirect this`, `deny = leave it alone`. Counterintuitive and the biggest conceptual trip-up for engineers new to the feature.

### 2. `url-redirect`

```
cisco-av-pair = url-redirect=https://ise-psn.corp.local:8443/portal/gateway?sessionId=...&portal=BYOD
```

**Meaning:** "When you intercept matching traffic, redirect the browser to this URL."

ISE builds this URL dynamically for each session. The session ID in the URL is how ISE correlates the browser hit back to the active RADIUS session.

### 3. dACL

```
cisco-av-pair = ACS:CiscoSecure-Defined-ACL=#ACSACL#-IP-ACL-BYOD-REDIRECT-LIMITED-<id>
```

**Meaning:** "While this session is pending enrollment, here's what the endpoint is allowed to actually do."

Without a dACL, the endpoint can reach everything. With a dACL, the endpoint is pinned to only what's needed for the portal flow:

- DHCP / DNS
- ISE PSNs (the portal itself)
- Maybe the BYOD provisioning payload host

Example dACL pushed from ISE:

```
permit udp any any eq domain
permit udp any any eq bootps
permit tcp any host 10.10.50.11 eq 8443
permit tcp any host 10.10.50.12 eq 8443
permit tcp any any eq 80             ! so the redirect can fire
permit tcp any any eq 443            ! so the redirect can fire
deny   ip any any
```

## Why all three are needed

| Missing piece | What breaks |
|---|---|
| `url-redirect-acl` | Switch accepts auth but doesn't know what to redirect. User lands in a pre-auth limbo. |
| `url-redirect` | Switch knows what to redirect but has no destination. HTTP traffic black-holed. |
| dACL | Endpoint has full network access while "pending enrollment." Security hole. |

## Switch config for BYOD redirect

On a Cat 9300, enable HTTP/HTTPS services (the redirect engine):

```
ip http server
ip http secure-server
ip http active-session-modules none
ip http secure-active-session-modules none
```

The two `active-session-modules none` lines disable all interactive HTTP on the switch *except* the redirect engine. Keeps the switch from being a web target.

## Debugging tips

When it doesn't work:

```
show access-session interface <port> details
```

Look for:
- `URL Redirect ACL: ACL-WEBAUTH-REDIRECT`
- `URL Redirect: https://.../portal/...`
- `Server Policies:` — should include the redirect-related dACL

If those lines are missing, ISE isn't sending the attributes — check the authz profile.

If they're present but the browser never redirects:
- Verify the ACL **exists on the switch** with that exact name (`show ip access-list ACL-WEBAUTH-REDIRECT`).
- Verify HTTP/HTTPS is enabled on the switch.
- Verify the client is actually generating HTTP/HTTPS traffic (try hitting a known HTTP site, not an HSTS one).
- Check for HSTS / cert-pinned domains — modern browsers will *refuse* redirects from HSTS sites. Tell the user to hit a plain HTTP URL like `http://neverssl.com`.

## Certificate considerations

The ISE portal cert **must be trusted by the BYOD device**:
- For corporate-managed devices, push the internal CA root via MDM.
- For truly unmanaged BYOD, use a public-CA cert on the portal so the browser doesn't warn.

A portal cert warning is the #1 reason BYOD onboarding gets abandoned by users.

---

Next: head to `configs/` for the deployable files, or `lab/` for the test plan.
