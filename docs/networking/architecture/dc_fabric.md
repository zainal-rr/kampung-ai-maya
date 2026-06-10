# Data Center Fabric Architecture

## Model

**Spine-leaf (Clos)** — every leaf connects to every spine, nothing connects spine-to-spine
or leaf-to-leaf (except MLAG/vPC peer links). Predictable 3-stage path (leaf→spine→leaf),
ECMP across all spines, scale out by adding spines (bandwidth) or leaves (ports).
This replaced three-tier in the DC because east-west traffic dominates and STP-based
designs waste half the links.

**Overlay: VXLAN + BGP EVPN** — the de facto standard.

- VXLAN gives L2-over-L3 (24-bit VNI ≈ 16M segments vs 4K VLANs) so the fabric core is
  pure routed IP with no STP.
- BGP EVPN is the control plane: MAC/IP reachability advertised in BGP instead of
  flood-and-learn. Route types that matter: Type-2 (MAC/IP host routes), Type-3
  (BUM/ingress-replication membership), Type-5 (IP prefixes between fabrics/external).

On Cisco: NX-OS (Nexus) is the native platform; IOS-XE (Catalyst 9000) supports the same
design for campus-fabric-style deployments — our recipes use IOS-XE syntax per KB scope.

## Key Design Decisions

1. **Underlay routing.** OSPF (simple, fine to ~100 switches) or eBGP per-link
   (hyperscale style, one private AS per leaf). Point-to-point /31s or unnumbered.
   Loopbacks for VTEP and protocol sources. Underlay's only job: advertise loopbacks.
2. **Overlay BGP design.** iBGP EVPN with spines as route reflectors (most common), or
   eBGP EVPN leaf-spine. Spines run no VTEPs; they are pure transport + RR.
3. **BUM traffic.** Ingress replication (each VTEP unicasts copies — simple, fine at small
   scale) vs multicast underlay (PIM ASM/BiDir — efficient, more moving parts). Default to
   ingress replication unless the fabric is large or BUM-heavy.
4. **Gateway model.** Distributed anycast gateway: every leaf hosts the same SVI IP/MAC
   for each subnet, so the first hop is always local. This is the EVPN killer feature —
   VM mobility without hairpinning. See `../recipes/ios-xe/evpn_anycast_gw_tenant.md`.
5. **Multi-tenancy.** Tenant = VRF = L3VNI. Each tenant gets: a VRF, one L3VNI for routed
   traffic between leaves, N L2VNIs for its subnets. Symmetric IRB (Cisco's model) routes
   via the L3VNI both directions.
6. **External connectivity.** Border leaves run Type-5 routes toward the WAN/firewall.
   Keep border function on dedicated leaves, not spines.
7. **Dual-homing.** Servers dual-home to leaf pairs: vPC (NX-OS), StackWise Virtual
   (Cat9k), or EVPN multihoming (ESI — the standards path). Pick one per pod, don't mix.

## What CCIE-level Answers Mention

- Symmetric vs asymmetric IRB: Cisco does symmetric (both VTEPs route via L3VNI);
  asymmetric (route on ingress, bridge on egress) requires all VNIs on all leaves — scales worse.
- Host mobility: EVPN MAC mobility sequence numbers (a MAC moving leaves increments the
  counter; flapping counters = duplicate MAC/loop somewhere).
- ARP suppression: leaves answer ARP locally from EVPN Type-2 data, cutting fabric-wide
  broadcast. Verify with `show ip arp suppression-cache` equivalents.
- MTU again: VXLAN adds ~50 bytes. Underlay MTU ≥ 1600 (or jumbo 9216 — just set jumbo).

Recipes: `vxlan_underlay.md`, `vxlan_evpn_overlay.md`, `evpn_anycast_gw_tenant.md`.
