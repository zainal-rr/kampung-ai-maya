# Recipe: EVPN Distributed Anycast Gateway + Tenant VRF (IOS-XE / Catalyst 9000)

## Intent
Add routing to the EVPN fabric: every leaf hosts the same gateway IP/MAC per subnet
(anycast GW), and a tenant VRF with an L3VNI routes between subnets across the fabric
(symmetric IRB).

## Design Context
Tenant model: 1 tenant = 1 VRF = 1 L3VNI (+ N L2VNIs for its subnets). Symmetric IRB —
both directions route via the L3VNI, so only the tenant's L3VNI (not every L2VNI) must
exist on every leaf. The same SVI IP/MAC on all leaves means first-hop is always local:
hosts move between leaves with no gateway change. Convention here: L3VNI = 50000 + tenant
number; L2VNIs = 10000 + VLAN as before.

## Prerequisites
- Working L2 overlay per `vxlan_evpn_overlay.md`.
- Tenant `TEN1`: VLAN 10 (10.10.0.0/24) + VLAN 20 (10.20.0.0/24), L3VNI 50001 on
  dedicated core VLAN 901.

## Configuration (identical on every leaf — that's the point)

Tenant VRF (RTs in EVPN use the `stitching` keyword):

```
vrf definition TEN1
 rd 65100:1
 address-family ipv4
  route-target export 65100:50001 stitching
  route-target import 65100:50001 stitching
 exit-address-family
```

Anycast gateway MAC (fabric-wide, one value everywhere):

```
l2vpn evpn
 default-gateway advertise
!
interface nve1
 host-reachability protocol bgp
```

Core VLAN + SVI for the L3VNI:

```
vlan 901
!
vlan configuration 901
 member vni 50001
!
interface Vlan901
 description TEN1 L3VNI core SVI
 vrf forwarding TEN1
 ip unnumbered Loopback0
 no autostate
```

Subnet SVIs — same IP and MAC on every leaf:

```
interface Vlan10
 vrf forwarding TEN1
 ip address 10.10.0.1 255.255.255.0
 mac-address 0000.beef.cafe
!
interface Vlan20
 vrf forwarding TEN1
 ip address 10.20.0.1 255.255.255.0
 mac-address 0000.beef.cafe
```

(The shared `mac-address` makes the gateway anycast. Pick one locally-administered MAC
for the whole fabric and never reuse it elsewhere.)

Stitch the L3VNI into NVE and BGP:

```
interface nve1
 member vni 50001 vrf TEN1
!
router bgp 65100
 address-family ipv4 vrf TEN1
  advertise l2vpn evpn
  redistribute connected
 exit-address-family
```

L2VNI 20 (VLAN 20) follows the `vxlan_evpn_overlay.md` pattern (EVI 20, VNI 10020) on
leaves that host VLAN 20 ports.

## Verification

```
show nve vni                                    ! 50001 type L3CP, associated VRF TEN1
show bgp l2vpn evpn route-type 2 | include 10.10.  ! MAC+IP routes (host /32s) with both labels
show bgp l2vpn evpn route-type 5                ! IP prefix routes (subnets) per tenant
show ip route vrf TEN1                          ! remote-leaf subnets + host /32s via the fabric
show ip cef vrf TEN1 10.20.0.5 detail           ! resolves via VXLAN encap, L3VNI 50001
! Host tests:
! A (VLAN10, L1) pings its GW 10.10.0.1          -> local leaf answers (always)
! A pings B (VLAN20, L2)                          -> inter-subnet across fabric (symmetric IRB)
! Move a VM L1->L2: gateway ping keeps working with zero reconfig
```

Type-2 routes for routed hosts must carry TWO labels (L2VNI + L3VNI) — one label means
the L3VNI stitching is broken on the advertising leaf.

## Rollback

```
interface nve1
 no member vni 50001 vrf TEN1
router bgp 65100
 no address-family ipv4 vrf TEN1
no interface Vlan901
interface Vlan10
 no vrf forwarding TEN1     ! re-add IP after (vrf assignment wipes it)
no vrf definition TEN1
```

(Per-leaf rollback breaks routing symmetry for the tenant on that leaf only; tenant-wide
removal goes leaf by leaf with hosts drained.)

## Failure Modes

| Break | First command |
| --- | --- |
| Same-subnet works, inter-subnet fails | L3VNI: `show nve vni` (50001 present on BOTH leaves? VRF bound?) |
| Inter-subnet works one direction | asymmetric config — a leaf missing the L3VNI or Vlan901 SVI down (`no autostate` missing) |
| GW unreachable after VM move | anycast MAC differs between leaves: compare `show run interface Vlan10` |
| Type-5 routes absent | `advertise l2vpn evpn` missing under the VRF AF |
| Routes import nowhere | stitching RTs mismatch: `show bgp l2vpn evpn` route detail, compare RT values |
| Silent drops to remote hosts | `show ip cef vrf TEN1 <dest>` — if not VXLAN-encapped, RIB chose a wrong path (leaked default?) |
