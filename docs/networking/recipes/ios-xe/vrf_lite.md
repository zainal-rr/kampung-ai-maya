# Recipe: VRF-lite Segmentation (IOS-XE)

## Intent
Create isolated routing tables on one device (and extend them between devices) without MPLS.

## Design Context
Use for: separating guest/IoT/OT/PCI traffic on a campus core, multi-tenant edge routers,
lab isolation. Avoid when: more than ~5–10 VRFs need to cross many links — per-link
per-VRF subinterfaces stop scaling; build MPLS L3VPN instead (`mpls_l3vpn_pe.md`).
Key decision: VRF-lite has no RD/RT signalling between devices — isolation is only as
good as the per-VRF link configuration on every hop.

## Prerequisites
- L3 device with IOS-XE (Catalyst 9k, ISR, ASR).
- Trunk or separate links available between devices for per-VRF transport.

## Topology Assumption
Two core switches, VRFs `GUEST` and `IOT`, extended over an 802.1Q trunk using one
subinterface (or SVI) per VRF.

## Configuration

Define the VRFs (modern `vrf definition` syntax — not legacy `ip vrf`):

```
vrf definition GUEST
 description Guest internet-only segment
 address-family ipv4
 exit-address-family
!
vrf definition IOT
 description IoT/OT segment
 address-family ipv4
 exit-address-family
```

Assign interfaces (NOTE: adding `vrf forwarding` ERASES the interface IP — re-enter it):

```
interface Vlan100
 description GUEST users
 vrf forwarding GUEST
 ip address 10.100.0.1 255.255.255.0
!
interface Vlan200
 description IOT devices
 vrf forwarding IOT
 ip address 10.200.0.1 255.255.255.0
```

Extend between switches — routed subinterfaces per VRF:

```
interface TenGigabitEthernet1/0/1
 description Core2 link
 no switchport
!
interface TenGigabitEthernet1/0/1.100
 encapsulation dot1Q 100
 vrf forwarding GUEST
 ip address 10.255.100.0 255.255.255.254
!
interface TenGigabitEthernet1/0/1.200
 encapsulation dot1Q 200
 vrf forwarding IOT
 ip address 10.255.200.0 255.255.255.254
```

Routing per VRF (OSPF example, one process or one instance per VRF):

```
router ospf 100 vrf GUEST
 router-id 10.255.100.1
 capability vrf-lite
 passive-interface default
 no passive-interface TenGigabitEthernet1/0/1.100
 network 10.100.0.0 0.0.255.255 area 0
!
router ospf 200 vrf IOT
 router-id 10.255.200.1
 capability vrf-lite
 passive-interface default
 no passive-interface TenGigabitEthernet1/0/1.200
 network 10.200.0.0 0.0.255.255 area 0
```

Static default per VRF (e.g. toward a firewall):

```
ip route vrf GUEST 0.0.0.0 0.0.0.0 10.100.255.1
```

## Verification

```
show vrf                                  ! VRFs + assigned interfaces
show ip route vrf GUEST                   ! per-VRF RIB
show ip ospf neighbor                     ! adjacency per process
ping vrf GUEST 10.100.0.10                ! data-plane test inside VRF
ping vrf GUEST 10.200.0.10                ! MUST FAIL - isolation proof
```

Good output: each VRF shows only its own routes; the cross-VRF ping fails.

## Rollback

```
interface Vlan100
 no vrf forwarding GUEST
 ip address 10.100.0.1 255.255.255.0     ! re-add, removal wiped it
no router ospf 100
no vrf definition GUEST                   ! removes VRF and all its routes
```

## Failure Modes

| Break | First command |
| --- | --- |
| Interface lost its IP after VRF assignment | (expected behaviour) re-enter `ip address` |
| OSPF adjacency up but routes rejected on a VRF-lite "CE" | check `capability vrf-lite` (down-bit) |
| Ping fails inside VRF | `show ip route vrf X` then `show ip cef vrf X <dest>` |
| Cross-VRF traffic works when it shouldn't | look for leaked statics: `show run | include ip route vrf` |
