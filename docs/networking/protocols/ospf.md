# OSPF Design Rules and Gotchas

## Design Rules

1. **Areas.** Area 0 is the backbone; all other areas must touch it. Under ~50 routers,
   single area 0 is the right answer — multi-area adds complexity before it adds value.
   Use areas to contain LSA flooding and enable summarization at ABRs, not for aesthetics.
2. **Area types.** Stub (no externals), totally stubby (`no-summary` — default route only),
   NSSA (stub that can originate externals as Type-7). Use totally stubby for branch/access
   areas: smallest LSDB, default route up.
3. **Network types.** Point-to-point on all routed links (`ip ospf network point-to-point`
   on /31s and Ethernet p2p) — skips DR election, halves adjacency time. Broadcast only on
   true multi-access segments; set DR priority deliberately there (`ip ospf priority`).
4. **Router ID.** Always hard-set (`router-id`) from a loopback. Dynamic RIDs change on
   reload and break documentation, LDP, and BGP peering assumptions.
5. **Passive by default.** `passive-interface default`, then `no passive-interface` on real
   adjacencies. Never form adjacencies toward user/server segments.
6. **Timers/convergence.** Defaults are 10/40 hello/dead. For sub-second: BFD
   (`bfd interval 300 min_rx 300 multiplier 3` + `ip ospf bfd`), not aggressive hellos.
   Also tune SPF throttle (`timers throttle spf 50 200 5000`) on modern CPUs.
7. **Authentication.** Use key-chain based: `ip ospf authentication key-chain` (IOS-XE
   supports SHA). MD5 interface auth is the legacy floor.
8. **Summarization.** Inter-area: `area X range` on the ABR. Externals: `summary-address`
   on the ASBR. Summaries hide instability — that's the point — but also hide specifics;
   mind longest-match interactions with VPN/leaked routes.

## Gotchas (CCIE-tier)

- **MTU mismatch sticks at EXSTART.** Both sides must agree or one must `ip ospf mtu-ignore`.
  Classic on VXLAN/GRE/MPLS-facing interfaces.
- **Network type mismatch** (one side p2p, other broadcast) forms adjacency but routes are
  unusable — next-hop resolution differs. Timers also differ (10 vs 30s hello) so it may
  not even form.
- **Forwarding address on Type-5/Type-7** can route externals around your expected path;
  NSSA ABR translation picks highest RID as translator.
- **OSPF in a VRF**: `router ospf X vrf NAME` — and on PE-CE links, the down-bit/domain-tag
  prevents re-import loops. If a CE doesn't get routes redistributed from another PE,
  check capability vrf-lite on a VRF-lite CE (`capability vrf-lite` disables down-bit
  checking — required when the "CE" is itself doing VRF-lite).
- **Default-information originate** needs an actual default in the RIB unless you add
  `always` — and `always` on two routers makes both advertise it forever, including during
  failures you wanted visible.
- **Distribute-lists don't filter LSAs** intra-area, only what enters the RIB. To filter
  routes you must filter at ABR/ASBR boundaries (area filter-list / summary with not-advertise).

## First Commands When Broken

| Symptom | Command |
| --- | --- |
| No adjacency | `show ip ospf neighbor`, `show ip ospf interface GiX` (timers, type, area) |
| Stuck EXSTART | check MTU both sides |
| Route missing | `show ip ospf database router/network` for the LSA, then RIB |
| Flapping | `show ip ospf neighbor` (dead-timer expiries), check BFD/L1 |
