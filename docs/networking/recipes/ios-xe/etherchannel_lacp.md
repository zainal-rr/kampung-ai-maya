# Recipe: LACP EtherChannel — L2 and L3 (IOS-XE)

## Intent
Bundle parallel links into one logical interface: L2 trunk bundles access↔distribution,
L3 routed bundles distribution↔core.

## Design Context
Always LACP (`mode active`), never PAgP (Cisco-only) and never `mode on` (static —
no protocol means no protection against miscabling; a wrong cable becomes a loop).
Load-balancing is per-flow, not per-packet: a single flow never exceeds one member's
bandwidth. Member configs must match exactly (speed, duplex, VLANs, MTU) or the port
suspends.

## Prerequisites
- 2+ equal links between the same two devices (or a StackWise/SVL pair for MLAG-style).

## Topology Assumption
Access → distribution: 2×10G L2 trunk (Po1). Distribution → core: 2×10G routed (Po10).

## Configuration

L2 trunk bundle (configure the port-channel FIRST, then members — config syncs down):

```
interface Port-channel1
 switchport mode trunk
 switchport trunk allowed vlan 10,20,30
!
interface range TenGigabitEthernet1/0/47 - 48
 switchport mode trunk
 switchport trunk allowed vlan 10,20,30
 channel-group 1 mode active
```

L3 routed bundle:

```
interface Port-channel10
 no switchport
 ip address 10.255.1.0 255.255.255.254
 ip ospf network point-to-point
!
interface range TenGigabitEthernet1/1/1 - 2
 no switchport
 no ip address
 channel-group 10 mode active
```

(`no switchport` on members BEFORE `channel-group`, and no IP on members — the Po owns the IP.)

Load-balance hash — include L4 so many flows between two hosts still spread:

```
port-channel load-balance src-dst-mixed-ip-port
```

(Platform-dependent keyword; `show etherchannel load-balance` reveals options. Default
src-dst-ip polarizes traffic between two heavy talkers.)

Fast failure detection on the bundle:

```
interface Port-channel10
 lacp fast-switchover
! and per-member fast LACP PDUs:
interface range TenGigabitEthernet1/1/1 - 2
 lacp rate fast
```

## Verification

```
show etherchannel summary            ! flags: P = bundled, want (SU) on Po
show etherchannel 1 detail           ! LACP partner system-id (same on all members!)
show lacp neighbor                   ! partner state
show interfaces Po1 trunk            ! VLANs forwarding on the bundle
test etherchannel load-balance interface Po1 ip 10.10.0.5 10.20.0.7   ! which member a flow takes
! Failover: shut one member -> traffic continues, (SU) stays, member shows (D)
```

Bad flags: `s` (suspended — config mismatch), `w` (waiting), `I` (stand-alone — LACP not
negotiating, likely `mode on` mismatch or no LACP on peer).

## Rollback

```
interface range TenGigabitEthernet1/0/47 - 48
 no channel-group 1
no interface Port-channel1
```

(Members keep their individual config after removal — verify they don't form a loop as
independent trunks; shut them first on a live network.)

## Failure Modes

| Break | First command |
| --- | --- |
| Member suspended (s) | `show etherchannel 1 detail` — find the mismatched attribute (VLAN list, speed, MTU) |
| Bundle forms but one member to wrong switch | LACP saved you (different partner system-id): `show lacp neighbor` — fix cabling |
| All traffic on one member | hash polarization: `show etherchannel load-balance`, change to mixed-ip-port |
| Po flaps when one member flaps | `lacp min-links` set too high, or single member carrying the SU state: `show etherchannel summary` |
| OSPF won't form on routed Po | `no switchport` order botched — members hold stale L2 state: default the members and rebuild |
