# Recipe: OSPF + LDP MPLS Core Underlay (IOS-XE)

## Intent
Build the IGP + label-switching foundation that L3VPN rides on: every P/PE router has a
labelled path to every PE loopback.

## Design Context
Single area 0 is correct for cores under ~50 routers. Loopbacks are /32 and never
summarized (summarization breaks LSPs — FEC must match the /32). LDP-IGP sync and session
protection are not optional extras; they prevent the classic blackhole-after-flap outages.
New greenfield cores should evaluate SR-MPLS instead (no LDP at all); this recipe is the
LDP baseline that brownfield networks run.

## Prerequisites
- Routed point-to-point links between core nodes (use /31s).
- Loopback plan: 10.0.0.x/32 per node.

## Topology Assumption
PE1 (10.0.0.1) — P1 (10.0.0.3) — PE2 (10.0.0.2), p2p links from 10.0.1.0/31 range.

## Configuration (pattern per node; values for PE1)

Loopback and core interface:

```
interface Loopback0
 ip address 10.0.0.1 255.255.255.255
!
interface GigabitEthernet0/0/0
 description to P1
 ip address 10.0.1.0 255.255.255.254
 ip ospf network point-to-point
 ip ospf bfd
 mpls ip
 mtu 1600
 no shutdown
```

`ip ospf network point-to-point` skips DR election on the /31. `mtu 1600` covers the
label stack. `mpls ip` enables LDP on the link — every core link, no exceptions.

OSPF with LDP sync:

```
router ospf 1
 router-id 10.0.0.1
 passive-interface default
 no passive-interface GigabitEthernet0/0/0
 network 10.0.0.1 0.0.0.0 area 0
 network 10.0.1.0 0.0.0.1 area 0
 timers throttle spf 50 200 5000
 bfd all-interfaces
 mpls ldp sync
```

LDP global settings:

```
mpls ldp router-id Loopback0 force
mpls ldp session protection
mpls label protocol ldp
```

`force` resets sessions to use the loopback RID immediately — schedule accordingly on a
live core. LDP RID must be reachable via the IGP or sessions never establish.

Repeat the pattern on P1 (two core interfaces, no VRFs/BGP needed) and PE2.

## Verification

```
show ip ospf neighbor                       ! FULL on all core links
show ip route ospf | include /32            ! all PE/P loopbacks as /32s
show mpls interfaces                        ! every core link: Yes (ldp)
show mpls ldp discovery                     ! hellos both ways
show mpls ldp neighbor                      ! Oper; targeted = session protection
show mpls forwarding-table 10.0.0.2 detail  ! label out toward remote PE
ping mpls ipv4 10.0.0.2/32                  ! LSP end-to-end ('!' not 'Q')
ping mpls ipv4 10.0.0.2/32 size 1500        ! LSP with real payload (MTU proof)
traceroute mpls ipv4 10.0.0.2/32            ! label stack per hop
```

`Q` in MPLS ping output = no label at some hop; find it with the forwarding-table walk.

## Rollback

```
router ospf 1
 no mpls ldp sync
interface GigabitEthernet0/0/0
 no mpls ip
no mpls ldp router-id Loopback0 force
```

(Removing `mpls ip` from a live core link drops all VPN traffic on that path — drain first.)

## Failure Modes

| Break | First command |
| --- | --- |
| OSPF stuck EXSTART | MTU mismatch — compare both ends |
| LDP discovered, session down | TCP 646 between RIDs: `show mpls ldp neighbor` (check transport addrs), RID reachability |
| One hop has no label for a /32 | that hop missing `mpls ip`, or loopback got summarized upstream |
| Blackhole ~10s after link recovery | `mpls ldp sync` missing |
| MPLS ping fails at size 1500 | `mpls mtu` / interface MTU on the failing hop |
