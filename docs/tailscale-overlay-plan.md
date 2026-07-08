# Plan: Tailscale overlay for efficient personal access, relay for zero-setup sharing

## Goal

Two access planes that coexist, chosen by **audience**, not by which physical
network anyone happens to be on:

1. **Sharing plane — `https://files.mugyen.com` (the relay).** Unchanged.
   Anyone, anywhere, with **zero setup** (no app, no account on their device):
   open a link in a browser. This stays the path for sharing with other people.
2. **Efficiency plane — a Tailscale overlay (`*.ts.net`).** For *your own*
   devices (laptop, phone, the server box). A stable network identity that
   follows the devices regardless of which WiFi they're on or what private IP
   DHCP hands out. Direct device-to-device — local-LAN speed when co-located,
   private peer-to-peer (or relayed) when apart.

The user requirement this solves: *"my laptop and phone talking through the
same network regardless of which actual network I'm on and regardless of the
assigned IP."* An overlay network gives each device a fixed identity
(`100.x.y.z` + a stable MagicDNS name) decoupled from the underlying L2/L3
network. This is precisely what a per-network DNS→private-IP record
(`lan.mugyen.com`, see [deployment.md](deployment.md)) could **not** do, because
that pins a name to one network's IP layout. **This plan retires the
`lan.mugyen.com` DNS-01 idea** and replaces it with Tailscale.

## Why this needs almost no app code

The client is already origin-agnostic. `client/src/utils/remoteMount.ts`
derives every API and WebSocket URL from `window.location` (protocol → `ws/wss`,
host, and the optional `/m/{code}` prefix). The same bundle already serves three
surfaces unchanged: `http://localhost`, `https://files.mugyen.com/m/<code>/`,
and `http://<lan-ip>:<port>/`. Serving it at `https://<box>.<tailnet>.ts.net/`
is just one more origin it already handles.

The existing CLI mode `network-file-server lan <folder>` (`scripts/run.sh lan`)
is exactly the direct file server we put on the overlay. Tailscale is a reverse
proxy in front of it — the same role Caddy plays for the relay. This preserves
the project's core principle (see deployment.md): **TLS always lives in a
reverse proxy; the app only ever speaks plain HTTP.** Tailscale `serve` is just
a second instance of that proxy, and it supplies the cert for free.

## Topology

```
                    Tailnet (WireGuard overlay, MagicDNS)
   ┌──────────────────────────────────────────────────────────────┐
   │  laptop ──────────┐                                           │
   │  100.x.x.2        │  direct (LAN-fast when co-located,        │
   │                   │  P2P/DERP when apart)                     │
   │  phone ───────────┤                                           │
   │  100.x.x.3        ▼                                           │
   │            ┌────────────────────────────────────────┐        │
   │            │ server box  (home NAS / laptop / VM)    │        │
   │            │  tailscaled  + MagicDNS name            │        │
   │            │  https://box.<tailnet>.ts.net  ──┐      │        │
   │            │    (tailscale serve, TLS here)   │      │        │
   │            │                                  ▼      │        │
   │            │  network-file-server lan  127.0.0.1:8000│        │
   │            │            (plain HTTP, localhost-bound)│        │
   │            └────────────────────────────────────────┘        │
   └──────────────────────────────────────────────────────────────┘

   Same folder ALSO shareable to the public, zero-setup:
   network-file-server mount <folder> --relay https://files.mugyen.com
        agent ── wss ──► files.mugyen.com (Caddy → relay → tunnel) ──► browser
```

The same directory can be served **both** ways at once (two processes pointing
at one folder): the `lan` server for your tailnet, and a `mount` agent for the
public relay. Concurrent access is fine subject to the usual concurrent-write
caveats already inherent to the file service.

## Decision matrix — which plane, when

| Who is accessing | Path | URL they open | Setup on their device | Speed |
|---|---|---|---|---|
| Someone else (guest, client) | Relay | `https://files.mugyen.com/m/<code>` | **none** | cloud round-trip |
| You, co-located with the box | Tailnet | `https://box.<tailnet>.ts.net` | Tailscale once | **direct LAN** |
| You, on a different network | Tailnet | `https://box.<tailnet>.ts.net` | Tailscale once | direct P2P / DERP |
| You, but box is asleep/off | Relay | `https://files.mugyen.com/m/<code>` | none | cloud round-trip |

"Use Tailscale when possible, relay when needed" = open the `ts.net` bookmark
for your own devices; hand out the `files.mugyen.com` link to everyone else. The
relay remains the universal fallback whenever the overlay isn't applicable
(other people, or the box being offline).

---

## Phase 0 — Tailnet bring-up (operational, no code)

1. Create a Tailscale account (or self-host the control plane with **Headscale**
   if you want zero third-party dependency — same model, more ops). Hosted
   Tailscale is free for personal use and recommended to start.
2. Admin console → enable **MagicDNS** and **HTTPS Certificates** (Settings →
   Features). HTTPS certs are what make `serve` issue a real Let's Encrypt cert
   for `*.ts.net` → a genuine browser **secure context**.
3. Install Tailscale and `tailscale up` on: the **server box**, your **laptop**,
   your **phone** (iOS/Android apps). One SSO login per device, one time.
4. Confirm MagicDNS names resolve: `tailscale status` lists each node; the box
   is reachable as `box.<tailnet>.ts.net` from the other devices.

Outcome: your three devices share a stable private network. No app code yet.

## Phase 1 — Put the existing `lan` server on the overlay (operational, no code)

On the server box:

1. Run the standalone file server bound to **localhost only** (TLS terminates in
   the Tailscale proxy, not the app):
   ```bash
   network-file-server lan /path/to/folder --host 127.0.0.1 --port 8000
   ```
   - Verify the `lan` subcommand accepts `--host`; the relay path already uses
     `--host 127.0.0.1` (deployment.md). If `lan` lacks it, add it (trivial,
     same uvicorn wiring) — binding localhost is what keeps the plain-HTTP app
     off every interface but the proxy.
2. Expose it on the tailnet over HTTPS:
   ```bash
   tailscale serve --bg --https=443 http://127.0.0.1:8000
   ```
   (Older CLIs: `tailscale serve https / http://127.0.0.1:8000`. Check
   `tailscale serve status`.) This serves **only to tailnet members** — it is
   NOT `tailscale funnel`, which would expose it publicly; we deliberately do
   not use Funnel.
3. From your laptop/phone open `https://box.<tailnet>.ts.net/` → the SPA loads
   over HTTPS, secure context, talking directly to the box.

Make it durable with a systemd unit mirroring `network-relay` (see
deployment.md for the pattern): `ExecStart` runs `scripts/run.sh lan <folder>
--host 127.0.0.1 --port 8000`, plus a one-time `tailscale serve` config (it
persists across reboots once set with `--bg`).

At this point the efficiency plane works end-to-end with **zero application
changes** — the URL-relative client handles the new origin natively.

## Phase 2 — Advertise the tailnet URL in QR / server-info (small code change)

Today the standalone server's `GET /api/server-info`
(`server/app/routers/server_info.py:98`) hardcodes the non-mount URL as
`http://{ip}:{port}` — so the in-app QR and "server info" panel would show the
raw LAN IP, not the stable `ts.net` name. Fix it exactly the way the relay's
`public_url` was just done (commit `9ce8853`):

- **`server/app/config.py`** — add `public_url: str | None = None` to
  `ServerConfig` (trailing, defaulted; current call sites are positional so the
  default keeps them working).
- **`server/app/routers/server_info.py`** — in the non-mount branch use
  `url = config.public_url or f"http://{ip}:{port}"`, and derive `port`
  from the public URL (443 default) when it is set, mirroring the relay-mount
  branch at lines 91–96.
- **CLI / bootstrap** — thread a `--public-url` flag and `WFS_PUBLIC_URL` env
  through `create_config_from_args` (`server/app/config.py:80`) and
  `server/app/bootstrap.py:46` into `ServerConfig`. On the box you'd set
  `WFS_PUBLIC_URL=https://box.<tailnet>.ts.net`.
- **Tests** — add server-info coverage that the advertised `url`/QR equals
  `public_url` when set, and falls back to `http://ip:port` when not. Mirror the
  relay `public_url` precedence tests added in `tests/relay/test_config.py` and
  the dropbox server-info tests.

Scope: ~1 field + ~6 lines of logic + flag wiring + tests. No client change.

## Phase 3 — Automatic "prefer Tailscale when reachable" (OPTIONAL — recommend deferring)

Phases 1–2 are a **manual two-bookmark** model, which fully meets the stated
goal. An automatic upgrade is possible but adds real complexity for marginal
gain (your own devices can just bookmark the `ts.net` URL). Documented here so
the trade-off is on record; **do not build it first**.

Sketch if pursued later:
- The relay-served page (`isRemoteMount() === true`,
  `client/src/utils/remoteMount.ts`) reads server-info, which optionally
  advertises a `direct_url` (the box's `ts.net` URL).
- Client probes it with a short-timeout `HEAD`/health fetch. If reachable (i.e.
  this device is on the tailnet), surface a "Switch to fast direct connection"
  action — or auto-navigate.
- Caveats that make this non-trivial: the `ts.net` origin is a **different
  origin** from `files.mugyen.com`, so session/localStorage/auth state does not
  carry over (full re-navigation, possibly re-auth); cross-origin probe must
  fail fast and silently for non-tailnet devices; and the box must be online.
  These are why a bookmark is the better default.

---

## Security & identity notes

- `tailscale serve` (not `funnel`) keeps the efficiency plane **private to the
  tailnet** — no public exposure, no inbound firewall holes. The box's app stays
  localhost-bound regardless.
- Use **tailnet ACLs** to scope who/what can reach the box's `:443` serve if you
  ever add non-owner devices to the tailnet.
- The relay's existing auth (accounts, restricted mounts, the `X-WFS-*` identity
  signing via `identity_secret`) is **unchanged** and still governs the sharing
  plane. The tailnet plane is network-level private; if you want app-level auth
  there too, run the `lan` server with a password/accounts the same as any
  direct deployment.
- Optionally enroll the **GCP relay VM** in the tailnet as well, so admin/SSH and
  relay-internal traffic can ride the overlay privately — secondary, not
  required for this plan.

## What to retire / update

- **Retire** the `lan.mugyen.com` DNS-01 section in
  [deployment.md](deployment.md) ("LAN-direct server over HTTPS (planned)") —
  superseded by this overlay. Replace it with a pointer to this document.
- Add a fourth row to the deployment.md context table: *Tailnet-direct* →
  `https://<box>.<tailnet>.ts.net` → secure context: Yes → TLS by: Tailscale
  (`serve`).
- Update the deployment memory note (pending-items list) to mark LAN DNS-01 as
  replaced by Tailscale rather than outstanding.

## Verification checklist

- [ ] `tailscale status` shows box + laptop + phone online.
- [ ] `curl https://box.<tailnet>.ts.net/api/server-info` from the laptop →
      `200`, trusted cert (secure context).
- [ ] Phone on **cellular** (not the box's WiFi) still opens the `ts.net` URL
      and browses files → proves network-independence.
- [ ] Phone + laptop on the **same WiFi** as the box → connection is direct
      (`tailscale ping <peer>` shows a direct, not DERP, path) → proves
      local-speed path when co-located.
- [ ] Secure-context APIs work natively over `ts.net` (clipboard copy,
      device-ID generation) with no reliance on the HTTP fallbacks.
- [ ] `https://files.mugyen.com/m/<code>` still works for a device **not** on
      the tailnet → proves the zero-setup sharing plane is intact.
- [ ] (Phase 2) In-app QR/server-info on the box advertises the `ts.net` URL,
      not the raw LAN IP.

## Rollout order

1. Phase 0 + Phase 1 — operational only; gets the efficiency plane live with no
   code. Validate the checklist above.
2. Phase 2 — small server-info `public_url` change so the in-app QR/share UI
   names the box by its stable `ts.net` URL. Ship with tests.
3. Update deployment.md + memory; retire the `lan.mugyen.com` plan.
4. Phase 3 — only if the manual two-bookmark model proves insufficient in
   practice.
