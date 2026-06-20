# Campus Enterprise Architecture

## Models

**Three-tier (access / distribution / core)** — for large campuses (multiple buildings,
thousands of endpoints). Access provides port density and L2 services; distribution
aggregates access and is the L2/L3 boundary; core is pure L3 transport, fast and dumb.

**Collapsed core (two-tier)** — distribution and core merge. Correct choice for most
single-building or small multi-building sites. Don't build three tiers to look enterprise;
build them when distribution-to-distribution east-west traffic or geographic spread demands it.

**Routed access** — push L3 down to the access layer (each access switch is a router).
Kills spanning-tree dependence and halves convergence complexity, at the cost of needing
L3 licenses everywhere and making VLAN spanning across closets impossible. Choose it when
no VLAN must span multiple access switches.

## Key Design Decisions

1. **L2/L3 boundary placement.** Default: distribution. Every VLAN terminates on an SVI
   pair at distribution with HSRP/VRRP. The boundary decision drives everything else —
   STP scope, gateway redundancy, where policy/QoS marking happens.
2. **VLAN spanning.** A VLAN that spans more than one access switch forces L2 trunks
   through distribution and enlarges the STP failure domain. Modern designs avoid it
   (wireless tunnels to controllers anyway). If a VLAN must span, run MST or RPVST+ with
   deliberate root placement and FHRP alignment (STP root = HSRP active, same switch).
3. **First-hop redundancy.** HSRP (Cisco-only shops), VRRP (multi-vendor), GLBP (rare,
   load-balancing gateways). Track uplinks so the gateway fails over when the upstream dies,
   not just when the switch dies.
4. **Uplink design.** Access→distribution: prefer L2 LACP port-channels (or routed links in
   routed access). Distribution→core: always routed, always ECMP pairs, no STP in the core.
5. **Segmentation.** VLANs per function (users, voice, printers, IoT, management, guest).
   VRF-lite at distribution/core when segments must stay separated end-to-end
   (guest, OT/IoT, PCI). See `../recipes/ios-xe/vrf_lite.md`.
6. **Resilience math.** Two of everything at distribution/core; single supervisor access
   switches are acceptable, stacked or chassis where closet uptime matters. Target
   sub-second convergence: tuned OSPF/HSRP timers or BFD, not defaults.

## Reference Failure Domains

- STP domain = one VLAN's L2 reach. Keep it inside one closet pair where possible.
- OSPF area = distribution block. Core is area 0; each distribution block can be its own
  area if the campus is large enough to care (>50 routers, otherwise single area 0 is fine).
- HSRP group = one SVI. Active gateways balanced across the distribution pair by VLAN
  (odd VLANs active on D1, even on D2) so neither box idles.

## What CCIE-level Answers Mention

- STP root, FHRP active, and traffic path must align or you get triangle-shaped suboptimal
  flows and unicast flooding.
- Unidirectional links kill L2: UDLD aggressive or STP Bridge Assurance on trunks.
- Convergence: access uplink failure should be carried by port-channel (no reconvergence),
  distribution failure by HSRP + routed ECMP (~1s with tuned timers, ms with BFD).

Recipes: `campus_l3_boundary_hsrp.md`, `stp_hardening.md`, `etherchannel_lacp.md`, `campus_qos.md`.
