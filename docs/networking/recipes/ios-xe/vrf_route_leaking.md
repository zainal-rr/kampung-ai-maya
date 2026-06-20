# Recipe: Inter-VRF Route Leaking / Shared Services (IOS-XE)

## Intent
Let multiple customer VRFs reach a shared-services VRF (DNS, AD, monitoring) without
letting customers reach each other.

## Design Context
The standard extranet pattern: asymmetric RT import/export. Shared VRF exports a
"services" RT that everyone imports; customers export their own RT which only the shared
VRF imports. Customers never import each other's RTs → no customer-to-customer path.
Use import maps when only specific prefixes (not the whole VRF) should leak.
For local leaking on a single box without BGP, see the static+BGP anchor at the end.

## Prerequisites
- Working L3VPN per `mpls_l3vpn_pe.md` (BGP is the leaking engine — RT exchange happens
  in VPNv4, even on a single router it requires the BGP VRF address-families).
- RT plan: CUST_A `65000:100`, CUST_B `65000:200`, SHARED `65000:500`.

## Topology Assumption
PE hosting CUST_A, CUST_B, and SHARED VRFs; shared services subnet 10.50.0.0/24 in SHARED.

## Configuration

Shared-services VRF — exports services RT, imports all customer RTs:

```
vrf definition SHARED
 rd 65000:501
 address-family ipv4
  route-target export 65000:500
  route-target import 65000:100
  route-target import 65000:200
 exit-address-family
```

Customer VRFs — keep their own RT, additionally import the services RT:

```
vrf definition CUST_A
 rd 65000:101
 address-family ipv4
  route-target export 65000:100
  route-target import 65000:100
  route-target import 65000:500
 exit-address-family
!
vrf definition CUST_B
 rd 65000:201
 address-family ipv4
  route-target export 65000:200
  route-target import 65000:200
  route-target import 65000:500
 exit-address-family
```

Limit the leak to specific prefixes (recommended — leak the service subnet, not the world):

```
ip prefix-list SHARED-SVCS seq 5 permit 10.50.0.0/24
!
route-map SHARED-IMPORT permit 10
 match ip address prefix-list SHARED-SVCS
!
vrf definition CUST_A
 address-family ipv4
  import map SHARED-IMPORT
 exit-address-family
```

(`import map` filters what the VRF accepts across ALL its import RTs — design prefix-lists accordingly.)

BGP must have the VRF AFs active (leaking rides on VPNv4 processing):

```
router bgp 65000
 address-family ipv4 vrf SHARED
  redistribute connected
 exit-address-family
```

### Variant: same-box leak without MP-BGP design (quick but blunt)

```
ip route vrf CUST_A 10.50.0.0 255.255.255.0 vrf SHARED 10.50.0.1
```

(Static inter-VRF route with explicit next-hop VRF. No return path — add the mirror route in SHARED. Use sparingly; RT leaking is the maintainable pattern.)

## Verification

```
show ip route vrf CUST_A 10.50.0.0          ! service route present in customer VRF
show ip route vrf CUST_B 10.50.0.0
show ip route vrf SHARED                     ! customer routes present in shared VRF
show bgp vpnv4 unicast vrf CUST_A 10.50.0.0/24   ! imported path + RTs visible
ping vrf CUST_A 10.50.0.10                   ! customer -> service
ping vrf CUST_A <CUST_B host>                ! MUST FAIL - customers still isolated
```

## Rollback

```
vrf definition CUST_A
 address-family ipv4
  no route-target import 65000:500
  no import map SHARED-IMPORT
vrf definition SHARED
 address-family ipv4
  no route-target import 65000:100
```

Leaked routes withdraw automatically once RT imports are removed.

## Failure Modes

| Break | First command |
| --- | --- |
| Service route not appearing in customer VRF | `show bgp vpnv4 unicast all 10.50.0.0/24` — exported with RT 65000:500? import map rejecting it? |
| Leak works one way only | return path: SHARED must import the customer RT too (routing is two unidirectional leaks) |
| Customers can reach each other | someone imported a customer RT into another customer VRF — audit `show run vrf` |
| Import map change has no effect | `clear bgp vpnv4 unicast all soft` to re-run import processing |
