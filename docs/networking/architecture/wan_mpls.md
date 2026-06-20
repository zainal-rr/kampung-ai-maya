# WAN / MPLS Architecture

## Service Models

**MPLS L3VPN (provider-managed or self-built)** — each customer/segment gets a VRF on the
PE; MP-BGP VPNv4 carries routes between PEs over an MPLS core. The enterprise either buys
this from a carrier (CE side only) or builds it on its own core (PE+P side). Strongest
isolation + any-to-any connectivity. See `../recipes/ios-xe/mpls_l3vpn_pe.md`.

**VRF-lite end-to-end** — VRFs without MPLS: per-VRF subinterfaces or VLANs on every link.
Fine up to roughly 5–10 VRFs and a handful of hops; beyond that the per-link per-VRF
configuration burden explodes. That scaling pain is the actual reason MPLS L3VPN exists.

**SD-WAN overlay** — IPsec/GRE tunnels over any transport (internet, LTE, MPLS), with
centralized policy (Cisco SD-WAN/vManage, Fortinet, Velo). Replaces carrier L3VPN at the
edge for most enterprises; the MPLS skill set remains for the DC/core side and for carriers.

**DMVPN/FlexVPN** — the pre-SD-WAN Cisco overlay: mGRE + NHRP + IPsec, hub-and-spoke with
dynamic spoke-to-spoke. Still common in brownfield. Phase 3 (`nhrp redirect`/`shortcut`)
is the only phase worth deploying new.

## Core Building Blocks (self-built MPLS)

| Role | Function |
| --- | --- |
| P (provider core) | Label switching only. No VRFs, no BGP needed. IGP + LDP. |
| PE (provider edge) | VRFs, MP-BGP VPNv4, PE-CE routing, label imposition. All the intelligence. |
| CE (customer edge) | Plain IP router in one VRF's world. Static/OSPF/eBGP to the PE. |
| RR (route reflector) | Scales iBGP: PEs peer to 2 RRs instead of full mesh. VPNv4 RRs need no VRFs and can be in the data path or out of it (prefer out). |

## Key Design Decisions

1. **IGP + label distribution.** OSPF or IS-IS for loopback reachability, LDP for labels
   (or SR-MPLS in new builds — segment routing removes LDP and its sync problems).
   LDP must be synchronized with the IGP (`mpls ldp sync`) or you blackhole traffic
   during reconvergence.
2. **RD and RT plan.** RD makes routes unique (`ASN:customer-id`), RT controls import/export
   policy. Decide upfront: unique RD per VRF per PE (needed for proper multipath with RRs)
   or same RD everywhere (simpler, hides paths behind RRs). RT scheme: `ASN:customer-id`
   for intra-VPN, dedicated RTs for shared services (see `../recipes/ios-xe/vrf_route_leaking.md`).
3. **PE-CE protocol.** Static for stub sites, eBGP for anything dual-homed or needing
   policy (use as-override or allowas-in for same-AS customer sites), OSPF when the
   customer insists (mind the down-bit and domain-id rules — sham-link territory).
4. **MTU.** MPLS adds 4 bytes per label; VPN traffic carries 2+ labels. Core links need
   MTU ≥ 1508, in practice set 1600+ (`mtu 1600` / `mpls mtu`) everywhere in the core.
   Most "MPLS is weirdly broken for big packets" tickets are this.
5. **QoS.** DSCP survives MPLS via EXP bits (3 bits = 8 classes). Map DSCP→EXP at
   ingress PE, EXP-based queuing in the core.

## What CCIE-level Answers Mention

- Full reachability chain for L3VPN: CE→PE (PE-CE routing) → VRF route table → VPNv4
  BGP (RD+RT+label) → remote PE import (RT match) → remote CE. Troubleshoot in that order.
- The two-label stack: top label gets the packet to the egress PE (IGP/LDP), bottom label
  picks the VRF/interface (VPN label from BGP). `show mpls forwarding-table` for the first,
  `show bgp vpnv4 unicast all labels` for the second.
- PHP (penultimate hop popping) means the last P router pops the top label —
  expected behaviour, not a bug, when you see one fewer label than you predicted.

Recipes: `mpls_l3vpn_pe.md`, `ospf_ldp_underlay.md`, `bgp_pe_ce.md`, `vrf_route_leaking.md`, `vrf_lite.md`.
