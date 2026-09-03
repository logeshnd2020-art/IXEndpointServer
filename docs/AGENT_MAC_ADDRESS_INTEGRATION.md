# Agent-side MAC Address Collection — Reference (not yet applied)

**Status: reference only.** This document describes what the *real* Mac
agent (deployed as v7.7.8 on IXMAC007 and others) would need to do to
report a hardware MAC address. It has **not** been applied to anything —
the actual agent source code is not reachable from this development
machine (confirmed: `ssh IXMAC007` cannot resolve; no agent source
exists anywhere on this Mac or in this repo beyond the inert
`src/bin/lib/managers/sync_manager.sh` stub, which this document does
**not** modify). Apply this to the real agent repository once its
location is available.

The server-side pipeline that will *receive* this value is already
built, tested, and live-verified — see the bottom of this document.

---

## 1. Determining the primary active physical interface

"Primary interface" means the same thing System Preferences → Network's
service order means: whichever interface macOS is *currently* using to
reach the internet. It must not be hardcoded to `en0`, because that
assumption breaks on any Mac where Wi-Fi isn't `en0` (common with
docks/adapters) or where Ethernet is the active connection instead.

```bash
get_primary_mac_address() {
    # Step 1: Ask the kernel routing table which interface currently
    # owns the default route. This reflects real-time reality (Wi-Fi if
    # connected over Wi-Fi, Ethernet/Thunderbolt if connected that way)
    # and requires no hardcoded interface name.
    local iface
    iface=$(route -n get default 2>/dev/null | awk '/interface: /{print $2}')

    if [ -z "$iface" ]; then
        return 1   # no active default route right now -- nothing to report
    fi

    # Step 2: Reject anything that is not a real physical NIC.
    # A VPN connection makes a *virtual* tunnel interface (utunN) the
    # default route; loopback/bridge/AWDL/VMware/etc. interfaces can
    # also appear in edge cases. None of these have a meaningful
    # hardware MAC.
    case "$iface" in
        lo*|utun*|bridge*|awdl*|llw*|gif*|stf*|vmnet*|vnic*|ap[0-9]*|ipsec*)
            return 1
            ;;
    esac

    # Step 3: Cross-check against networksetup's own hardware-port list
    # (which only ever lists real physical ports -- Wi-Fi, Ethernet,
    # Thunderbolt Ethernet -- never virtual interfaces) and confirm the
    # interface is actually active.
    if ! networksetup -listallhardwareports | grep -q "Device: $iface$"; then
        return 1
    fi

    if ! ifconfig "$iface" | grep -q "status: active"; then
        return 1
    fi

    # Step 4: Read the hardware ("ether") address of that interface.
    local mac
    mac=$(ifconfig "$iface" | awk '/ether /{print $2; exit}')

    [ -z "$mac" ] && return 1

    # Step 5: Normalize to uppercase "XX:XX:XX:XX:XX:XX".
    echo "$mac" | tr '[:lower:]' '[:upper:]'
}
```

## 2. Exact macOS commands/APIs used

- `route -n get default` — kernel routing table lookup, gives the interface currently used for outbound traffic.
- `networksetup -listallhardwareports` — enumerates only real, kernel-recognized physical hardware ports (Wi-Fi, Ethernet, Thunderbolt Ethernet, etc.); used here purely as a cross-check, never as the primary source.
- `ifconfig <iface>` — reads interface status (`status: active`) and hardware address (`ether xx:xx:xx:xx:xx:xx`).

No ARP table, no `arp -a`, no IP-to-MAC lookup of any kind. No `device_uuid`. No `serial_number`. No generated/random value. If any step fails or returns empty, the function returns non-zero and the caller should simply omit `mac_address` from the payload (matches the schema's `Optional[str] = None` — a heartbeat with no MAC is exactly as valid as every heartbeat sent today).

## 3. How it avoids loopback / virtual / bridge / VPN / inactive interfaces

| Risk | How it's excluded |
|---|---|
| Loopback (`lo0`) | Explicit `case` pattern match |
| VPN tunnel (`utunN`) becoming the default route | Explicit `case` pattern match — this is the one that actually matters most in practice, since VPN *does* commonly take over the default route |
| Bridge (`bridge0`, Thunderbolt Bridge) | Explicit `case` pattern match |
| AWDL/peer-to-peer (`awdl0`, `llw0`) | Explicit `case` pattern match |
| Virtual machine adapters (`vmnet*`, `vnic*`) | Explicit `case` pattern match |
| Not a real hardware port at all | Cross-checked against `networksetup -listallhardwareports` |
| Present but not actually connected/up | Requires `ifconfig` to report `status: active` |

## 4. Exact MAC address format returned

`AA:BB:CC:DD:EE:FF` — six uppercase hex octets, colon-separated. `ifconfig` reports it lowercase by default; the script uppercases it explicitly. (The server's display formatter, `IXFormat.macAddress()`, is lenient and would also accept lowercase or dash-separated input and normalize it — but the agent should send the canonical uppercase-colon form.)

## 5. Exact heartbeat JSON field to send

`mac_address` — a new, optional key alongside the agent's existing heartbeat fields, matching `AgentHeartbeatRequest.mac_address: Optional[str] = None` in `app/schemas/heartbeat.py` on the server. Sent in the **same** `POST /api/agent/heartbeat` request as everything else — no new endpoint, no new request.

## 6. Example expected payload

```json
{
  "cpu_usage": 32.7,
  "memory_usage": 81.7,
  "disk_usage": 4.0,
  "battery_level": 100,
  "logged_in_user": "logesan",
  "hostname": "IXMAC007",
  "ip_address": "192.168.1.162",
  "network_name": "Office-WiFi",
  "mac_address": "AC:DE:48:00:11:22",
  "agent_version": "7.7.8",
  "uptime_seconds": 101136
}
```

Sent with the existing `Authorization: Device <token>` header — no change to authentication.

## 7. What to change in the real agent repository

The exact file/function path **cannot be confirmed from here** — the real repository isn't reachable from this machine (see top of this document). Based on this project's own naming convention (this repo's `src/bin/lib/managers/sync_manager.sh` calls a `send_payload` function for heartbeat, per its structure), the real agent likely has an analogous module — something like a `modules/heartbeat.sh` or `lib/payload.sh` containing the function that builds the heartbeat JSON body currently sent to `POST /api/agent/heartbeat` (the one already populating `cpu_usage`, `ip_address`, `network_name`, `uptime_seconds`, etc.). Once that file is located:

1. Add the `get_primary_mac_address()` function above (or equivalent) to the agent's shell library.
2. Call it when building the heartbeat payload, and add its result as `"mac_address": "$mac"` alongside the existing fields — only if non-empty, so a failed lookup simply omits the key rather than sending an empty string.
3. No other agent behavior needs to change.

---

## Server-side status (already complete, tested, and live-verified)

| Layer | State |
|---|---|
| Migration | `alembic/versions/d4e5f6a7b8c9_add_mac_address_to_device_heartbeats.py` — applied to production DB |
| Model | `app/models/device_heartbeat.py::DeviceHeartbeat.mac_address` |
| Request schema | `app/schemas/heartbeat.py::AgentHeartbeatRequest.mac_address` (Optional, backward compatible) |
| Service/Repository | `app/services/agent_service.py`, `app/repositories/device_heartbeat_repository.py` — pass-through, no computation |
| API | `GET /api/device/{id}/health` → `"mac_address"` field |
| Frontend | `templates/device.html` NETWORK card, formatted via `static/js/format.js::macAddress()` |
| Tests | `tests/test_agent_heartbeat_mac_address.py` (4), regression guard in `tests/test_device_health.py` |

The moment a real agent sends `mac_address` in its heartbeat, it will appear on the dashboard with zero further server changes.
