# Networking Knowledge Base

Truth layer for the `network_engineering` skill (`maya_skills/proposed/network_engineering.md`).
Maya retrieves from this tree instead of generating config from model weights.

## Rules

1. Recipes are the only source Maya may call "verified config".
2. Anything not covered here is answered as general knowledge and labelled unverified.
3. Every recipe must be reviewed once by Zainal (or proven in a lab) before it counts as verified.
4. Vendor scope today: Cisco IOS-XE. Other vendors get their own directory under `recipes/` when added.
5. Recipes use placeholder values in CAPS (e.g. `CUST_A`, `10.0.0.0/24`, `AS 65000`); Maya adapts them to the user's real addressing when answering.

## Layout

| Path | Content |
| --- | --- |
| `architecture/` | High-level design: campus, WAN/MPLS, DC fabric. The "why" layer. |
| `protocols/` | Protocol design rules and gotchas: OSPF, BGP, MPLS. The "how it behaves" layer. |
| `recipes/ios-xe/` | Worked, verified configurations. The "exact commands" layer. |

## Recipe Format (mandatory)

Every recipe contains, in order:

1. **Intent** — the task in one sentence.
2. **Design context** — when to use this, when not to, key decisions.
3. **Prerequisites** — what must already exist/work.
4. **Topology assumption** — the reference topology the config targets.
5. **Configuration** — complete IOS-XE config blocks, placeholders in CAPS.
6. **Verification** — exact `show`/`ping`/`traceroute` commands with what good output looks like.
7. **Rollback** — exact commands to undo the change.
8. **Failure modes** — the common ways this breaks and the first command to run for each.

## Current Recipes

### VRF / MPLS L3VPN
- `recipes/ios-xe/vrf_lite.md` — VRF-lite segmentation without MPLS
- `recipes/ios-xe/mpls_l3vpn_pe.md` — full PE config: VRF, RD/RT, MP-BGP VPNv4, PE-CE
- `recipes/ios-xe/vrf_route_leaking.md` — shared services / inter-VRF route leaking
- `recipes/ios-xe/ospf_ldp_underlay.md` — OSPF + LDP core for MPLS
- `recipes/ios-xe/bgp_pe_ce.md` — eBGP PE-CE with as-override, allowas-in, SoO

### Campus Enterprise
- `recipes/ios-xe/campus_l3_boundary_hsrp.md` — SVIs, HSRP with tracking, DHCP relay
- `recipes/ios-xe/stp_hardening.md` — RPVST+, root guard, BPDU guard, portfast
- `recipes/ios-xe/etherchannel_lacp.md` — L2 and L3 LACP port channels
- `recipes/ios-xe/campus_qos.md` — trust boundary, marking, queuing baseline

### DC Fabric
- `recipes/ios-xe/vxlan_underlay.md` — fabric underlay: OSPF, PIM BiDir-free BUM design, loopbacks
- `recipes/ios-xe/vxlan_evpn_overlay.md` — BGP EVPN, NVE, L2VNI/L3VNI
- `recipes/ios-xe/evpn_anycast_gw_tenant.md` — distributed anycast gateway + tenant VRF
