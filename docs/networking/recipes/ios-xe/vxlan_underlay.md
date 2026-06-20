# Recipe: VXLAN Fabric Underlay (IOS-XE / Catalyst 9000)

## Intent
Build the routed underlay a VXLAN/EVPN fabric rides on: loopback reachability between all
VTEPs with ECMP and headroom MTU.

## Design Context
Underlay has one job — advertise loopbacks. OSPF point-to-point everywhere is the simple,
correct choice at campus/small-DC scale (see `../../architecture/dc_fabric.md` for the
eBGP-underlay alternative and when it pays off). Two loopbacks per leaf: Lo0 router-id /
protocol source, Lo1 VTEP source (NVE). BUM here uses ingress replication (configured in
the overlay recipe), so no PIM — one less subsystem; switch to multicast underlay only at
larger scale.

## Prerequisites
- Spine-leaf cabling, every leaf to every spine, p2p /31s.
- Loopback plan: spines 10.0.0.x/32, leaves 10.0.1.x/32 (Lo0), VTEPs 10.0.2.x/32 (Lo1).

## Topology Assumption
2 spines (S1 10.0.0.1, S2 10.0.0.2), 2 leaves (L1: Lo0 10.0.1.1, Lo1 10.0.2.1;
L2: Lo0 10.0.1.2, Lo1 10.0.2.2).

## Configuration (Leaf1 pattern)

System MTU first (VXLAN adds ~50 bytes — jumbo everywhere ends the topic):

```
system mtu 9198
```

Loopbacks:

```
interface Loopback0
 description router-id / BGP source
 ip address 10.0.1.1 255.255.255.255
 ip ospf 1 area 0
!
interface Loopback1
 description VTEP source (NVE)
 ip address 10.0.2.1 255.255.255.255
 ip ospf 1 area 0
```

Fabric links (one per spine):

```
interface TenGigabitEthernet1/0/49
 description to Spine1
 no switchport
 ip address 10.0.10.1 255.255.255.254
 ip ospf network point-to-point
 ip ospf 1 area 0
 ip ospf bfd
!
interface TenGigabitEthernet1/0/50
 description to Spine2
 no switchport
 ip address 10.0.10.3 255.255.255.254
 ip ospf network point-to-point
 ip ospf 1 area 0
 ip ospf bfd
```

OSPF process:

```
router ospf 1
 router-id 10.0.1.1
 passive-interface default
 no passive-interface TenGigabitEthernet1/0/49
 no passive-interface TenGigabitEthernet1/0/50
 timers throttle spf 50 200 5000
 bfd all-interfaces
```

Spines: same pattern — Lo0 only (spines have no VTEP), p2p links to every leaf.

## Verification

```
show ip ospf neighbor                      ! FULL to both spines
show ip route ospf | include /32           ! ALL leaf Lo0+Lo1 and spine Lo0 present
show ip route 10.0.2.2                     ! remote VTEP via 2 paths (ECMP through both spines)
show ip cef 10.0.2.2 detail                ! both next-hops installed
ping 10.0.2.2 source Loopback1             ! VTEP-to-VTEP reachability
ping 10.0.2.2 source Loopback1 size 9000 df-bit   ! MTU headroom proof
```

ECMP through both spines is part of the contract — one path means a link or OSPF problem.

## Rollback

Underlay rollback = removing OSPF/IPs; only relevant pre-production. After the overlay is
live, underlay changes are maintenance-window work (drain a spine by raising OSPF cost:
`ip ospf cost 10000` on its links).

## Failure Modes

| Break | First command |
| --- | --- |
| Adjacency stuck EXSTART | MTU mismatch (someone skipped system mtu): compare `show ip ospf interface` |
| VTEP loopback missing from a leaf's RIB | Lo1 not in OSPF (`ip ospf 1 area 0` on the loopback) |
| Only one ECMP path | link down or cost mismatch: `show ip ospf interface brief` |
| Jumbo ping fails | `system mtu` not applied (needs reload on some platforms): `show system mtu` |
| Flaps under load | BFD timers vs CoPP: `show bfd neighbors` |
