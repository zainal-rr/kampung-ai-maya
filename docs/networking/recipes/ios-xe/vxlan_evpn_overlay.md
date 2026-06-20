# Recipe: VXLAN BGP EVPN Overlay (IOS-XE / Catalyst 9000)

## Intent
Bring up the EVPN control plane and VXLAN data plane: iBGP EVPN with spines as route
reflectors, NVE interface, one L2VNI mapped to a VLAN.

## Design Context
iBGP EVPN, spines = RRs, leaves = clients — the standard small/mid fabric. Spines run no
NVE (pure transport + RR). BUM via ingress replication (matches the underlay recipe — no
PIM). L2VNI numbering convention: 10000 + VLAN (VLAN 10 → VNI 10010). Routing between
segments comes next in `evpn_anycast_gw_tenant.md`; this recipe delivers L2 stretch.

## Prerequisites
- Underlay complete and verified (`vxlan_underlay.md`) — VTEP-to-VTEP jumbo ping passes.
- AS 65100 for the fabric; VLAN 10 exists on both leaves.

## Topology Assumption
S1/S2 spines (RRs, 10.0.0.1/.2), L1/L2 leaves (Lo0 10.0.1.1/.2, Lo1 = VTEP 10.0.2.1/.2).
Host A on L1 VLAN 10, host B on L2 VLAN 10.

## Configuration

### Spine (RR — S1 pattern)

```
router bgp 65100
 bgp router-id 10.0.0.1
 bgp log-neighbor-changes
 neighbor FABRIC-LEAVES peer-group
 neighbor FABRIC-LEAVES remote-as 65100
 neighbor FABRIC-LEAVES update-source Loopback0
 neighbor 10.0.1.1 peer-group FABRIC-LEAVES
 neighbor 10.0.1.2 peer-group FABRIC-LEAVES
 !
 address-family l2vpn evpn
  neighbor FABRIC-LEAVES activate
  neighbor FABRIC-LEAVES send-community both
  neighbor FABRIC-LEAVES route-reflector-client
 exit-address-family
```

(`send-community both` — EVPN uses extended communities for RTs; standard for everything else.)

### Leaf (L1 pattern)

EVPN instance for the VLAN:

```
l2vpn evpn
 replication-type ingress
 router-id Loopback0
!
l2vpn evpn instance 10 vlan-based
 encapsulation vxlan
 replication-type ingress
```

VLAN→EVI/VNI stitching:

```
vlan configuration 10
 member evpn-instance 10 vni 10010
```

NVE interface (VTEP):

```
interface nve1
 no ip address
 source-interface Loopback1
 host-reachability protocol bgp
 member vni 10010 ingress-replication
 no shutdown
```

BGP to both RRs:

```
router bgp 65100
 bgp router-id 10.0.1.1
 neighbor FABRIC-RRS peer-group
 neighbor FABRIC-RRS remote-as 65100
 neighbor FABRIC-RRS update-source Loopback0
 neighbor 10.0.0.1 peer-group FABRIC-RRS
 neighbor 10.0.0.2 peer-group FABRIC-RRS
 !
 address-family l2vpn evpn
  neighbor FABRIC-RRS activate
  neighbor FABRIC-RRS send-community both
 exit-address-family
```

Access port into the stretched VLAN:

```
interface GigabitEthernet1/0/5
 switchport mode access
 switchport access vlan 10
 spanning-tree portfast edge
```

L2 mirrors the leaf config with its own IDs.

## Verification

Control plane first, then data plane:

```
show bgp l2vpn evpn summary                     ! Established to both RRs
show bgp l2vpn evpn route-type 3                ! IMET routes = VTEP discovery (one per VTEP per VNI)
show bgp l2vpn evpn route-type 2                ! MAC/IP routes for learned hosts
show l2vpn evpn evi 10 detail                   ! EVI up, VNI 10010 bound
show nve peers                                  ! remote VTEP 10.0.2.2 UP with VNI
show nve vni                                    ! VNI 10010 Up, ingress-replication
show l2vpn evpn mac evi 10                      ! host MACs local + remote
! Data plane: host A pings host B (same subnet, different leaves)
```

Sequence meaning: no Type-3 = BGP/EVI problem; Type-3 but no NVE peer = NVE/VNI mismatch;
peers up but no Type-2 = hosts not learned (check access port/VLAN).

## Rollback

```
interface nve1
 no member vni 10010
vlan configuration 10
 no member evpn-instance 10 vni 10010
no l2vpn evpn instance 10
! Full removal: no interface nve1, remove l2vpn evpn AF from BGP
```

(VLAN 10 keeps working locally on each leaf — rollback only kills the stretch.)

## Failure Modes

| Break | First command |
| --- | --- |
| EVPN session idle | Lo0 reachability (underlay), `update-source` correct |
| No Type-3 routes from a leaf | EVI not bound to VLAN/VNI: `show l2vpn evpn evi 10 detail`, replication-type set? |
| NVE peer missing despite Type-3 | VNI number mismatch between leaves, or Lo1 not advertised in underlay |
| MACs learned locally, not remotely | RT mismatch on EVI (auto-RT derives from AS:EVI — manual overrides must match), `send-community both` missing on a spine |
| Ping fails with everything green | MTU: jumbo VTEP-to-VTEP ping from `vxlan_underlay.md` verification |
| Host flaps between leaves | duplicate MAC / loop below the fabric: `show bgp l2vpn evpn route-type 2` mobility sequence climbing |
