# Recipe: MPLS L3VPN PE Configuration (IOS-XE)

## Intent
Configure a PE router to carry a customer VRF across an MPLS core using MP-BGP VPNv4.

## Design Context
The standard multi-site any-to-any VPN. Requires a working MPLS core
(`ospf_ldp_underlay.md`) first. Key decisions: RD scheme (unique per PE per VRF enables
multipath via RRs; same RD everywhere is simpler), RT plan (`ASN:cust-id`), PE-CE protocol
(static here; eBGP variant in `bgp_pe_ce.md`).

## Prerequisites
- Core IGP up, LDP labels end-to-end between PE loopbacks (verify before starting:
  `ping mpls ipv4 <remote-PE>/32`).
- iBGP VPNv4 session plan (direct PE-PE here; RRs at scale).
- This recipe: AS 65000, PE1 loopback 10.0.0.1, PE2 loopback 10.0.0.2, customer `CUST_A`.

## Topology Assumption
CE_A1 -- PE1 ===(MPLS core)=== PE2 -- CE_A2, customer sites 192.168.1.0/24 and 192.168.2.0/24.

## Configuration (PE1)

VRF with RD and RT:

```
vrf definition CUST_A
 rd 65000:101
 address-family ipv4
  route-target export 65000:100
  route-target import 65000:100
 exit-address-family
```

(RD `65000:101` on PE1, `65000:102` on PE2 — unique-RD scheme. RT `65000:100` shared = the VPN.)

Customer-facing interface:

```
interface GigabitEthernet0/0/1
 description CUST_A site 1
 vrf forwarding CUST_A
 ip address 172.16.1.1 255.255.255.252
 no shutdown
```

PE-CE routing (static for a stub site):

```
ip route vrf CUST_A 192.168.1.0 255.255.255.0 172.16.1.2
```

MP-BGP VPNv4:

```
router bgp 65000
 bgp router-id 10.0.0.1
 neighbor 10.0.0.2 remote-as 65000
 neighbor 10.0.0.2 update-source Loopback0
 !
 address-family vpnv4
  neighbor 10.0.0.2 activate
  neighbor 10.0.0.2 send-community extended
 exit-address-family
 !
 address-family ipv4 vrf CUST_A
  redistribute static
  redistribute connected
 exit-address-family
```

`send-community extended` is mandatory — RTs are extended communities; without it the
remote PE imports nothing.

Mirror on PE2 with rd 65000:102, its own interface addressing, and static for 192.168.2.0/24.

## Verification

Order matters — walk the reachability chain:

```
show vrf CUST_A                                          ! 1. VRF + interface
show ip route vrf CUST_A                                 ! 2. local + remote routes (B = from BGP)
show bgp vpnv4 unicast all summary                       ! 3. VPNv4 session Established
show bgp vpnv4 unicast vrf CUST_A 192.168.2.0/24         ! 4. remote route w/ RT + label
show bgp vpnv4 unicast all labels                        ! 5. VPN labels
show mpls forwarding-table 10.0.0.2                      ! 6. transport label to remote PE
ping vrf CUST_A 192.168.2.1 source 172.16.1.1            ! 7. end-to-end data plane
```

Good output at step 4 includes `Extended Community: RT:65000:100` and a label; step 7 succeeds.

## Rollback

```
router bgp 65000
 no address-family ipv4 vrf CUST_A
no ip route vrf CUST_A 192.168.1.0 255.255.255.0 172.16.1.2
interface GigabitEthernet0/0/1
 no vrf forwarding CUST_A
no vrf definition CUST_A
```

(Leave the VPNv4 session itself if other VRFs use it.)

## Failure Modes

| Break | First command |
| --- | --- |
| Remote routes absent from VRF RIB | `show bgp vpnv4 unicast all` — present in BGP? If yes: RT import mismatch. If no: remote PE not exporting / session down |
| Routes have no RT attached | `send-community extended` missing |
| Routes in RIB, ping fails | label path: `show mpls forwarding-table <remote-PE-loopback>` hop by hop (LSP hole) |
| Ping works small, app traffic fails | core MTU — `ping mpls ipv4 10.0.0.2/32 size 1500` |
| BGP best path won't install | next-hop 10.0.0.2 must be the loopback /32 via IGP, not summarized |
