# BGP Design Rules and Gotchas

## Design Rules

1. **iBGP needs full mesh or route reflectors.** iBGP does not re-advertise iBGP-learned
   routes. RRs solve it: PEs/clients peer to two RRs (`neighbor X route-reflector-client`).
   Keep RRs out of the data path when possible (control-plane only boxes).
2. **Peer on loopbacks for iBGP** (`update-source Loopback0`) so sessions survive link
   failures; the IGP carries loopback reachability. eBGP peers on the link address
   (loopback eBGP needs `ebgp-multihop`/`ttl-security` and a static/IGP route to reach it).
3. **Next-hop handling.** iBGP does not rewrite next-hop: either `next-hop-self` on the
   border/PE routers or carry the external link subnet in the IGP. Most "route in BGP table
   but not RIB" tickets are unresolvable next-hops.
4. **Path selection order (memorize):** weight (local, Cisco) → local-pref (IGP-wide,
   outbound policy) → locally-originated → AS-path length → origin → MED (compares only
   same neighbor-AS by default) → eBGP over iBGP → lowest IGP metric to next-hop →
   oldest/lowest RID tiebreaks.
5. **Policy direction.** Local-pref for choosing how traffic *leaves* (set inbound on the
   routes you prefer). AS-path prepend / MED for influencing how traffic *enters*
   (applied outbound). Communities to signal policy across the network instead of
   per-router route-maps.
6. **Always filter eBGP.** Inbound and outbound prefix-lists/route-maps on every eBGP
   session. IOS-XE default for eBGP without policy: with `bgp enhanced-error` and modern
   defaults, undefined policy can mean advertise/accept everything — never rely on it.
   Max-prefix (`neighbor X maximum-prefix`) on all eBGP.
7. **VPNv4 specifics.** `address-family vpnv4` with `send-community extended` (RTs are
   extended communities — forget this and VPN routes carry no RTs and import nothing).
   RRs for VPNv4 need `retain route-target all` only if they're not also PEs (no VRFs).
8. **Convergence.** BFD for fast peer-down, `bgp fast-external-fallover` is on by default
   for directly connected eBGP. PIC/Add-Path for pre-installed backup paths where supported.

## Gotchas (CCIE-tier)

- **MED only compares between the same neighboring AS.** `bgp always-compare-med` changes
  it network-wide; deterministic-med should be on in any MED-using network.
- **as-override vs allowas-in** (PE-CE, customer reuses one AS at all sites): as-override
  on the PE rewrites the customer AS; allowas-in on the CE accepts its own AS. Pick one
  side, document it. Loop protection is what you're disabling — add SoO to compensate
  on dual-homed sites.
- **Synchronization is dead** (off by default since IOS 12.2(8)T) but auto-summary still
  appears in old templates — both should be absent/`no` in any modern config.
- **`network` statements need an exact RIB match** (prefix + mask). Redistribute or use a
  static-to-null anchor for aggregates (`ip route 10.0.0.0 255.255.0.0 Null0` + `network 10.0.0.0 mask 255.255.0.0`).
- **Communities don't propagate unless configured**: `neighbor X send-community both`.
  Silent policy failures across AS boundaries are usually this.
- **iBGP between VRFs doesn't exist** — routes between VRFs move via RT import/export,
  not peering. Don't "fix" inter-VRF reachability with loopback eBGP hacks; leak properly.
- **Aggregation:** `aggregate-address ... summary-only` suppresses specifics; without
  `as-set` the aggregate loses path info (potential loops in multi-AS topologies).

## First Commands When Broken

| Symptom | Command |
| --- | --- |
| Session down | `show bgp summary` / `show bgp vpnv4 unicast all summary`, then TCP 179 reachability |
| Route missing remotely | `show bgp ... advertised-routes` vs `received-routes` (policy?), next-hop validity |
| VPN route not importing | RTs: `show bgp vpnv4 unicast all X/Y` (extended communities present? import map?) |
| Wrong path chosen | `show bgp ... X/Y` best-path reasons, check local-pref/MED/IGP metric |
