# Recipe: eBGP PE-CE with as-override / SoO (IOS-XE)

## Intent
Run eBGP between PE and customer CE — the right PE-CE choice for dual-homed sites or
anywhere the customer needs routing policy.

## Design Context
Standard problem: the customer uses the same AS (e.g. 65001) at every site. Site 2's CE
would reject site 1's routes (own AS in path). Two fixes: `as-override` on the PE
(rewrites customer AS with provider AS — customer sees provider AS twice) or `allowas-in`
on the CE (accepts its own AS). Pick PE-side as-override when you control the PEs.
Disabling AS-path loop protection reopens real loop risk on dual-homed sites — that's
what Site-of-Origin (SoO) is for: tag routes per site, refuse to send a site its own routes.

## Prerequisites
- VRF + VPNv4 working per `mpls_l3vpn_pe.md`.
- This recipe: provider AS 65000, customer AS 65001, VRF `CUST_A`,
  PE-CE link 172.16.1.0/30 (PE .1, CE .2), dual-homed site → SoO `65000:1`.

## Configuration

PE side:

```
router bgp 65000
 address-family ipv4 vrf CUST_A
  neighbor 172.16.1.2 remote-as 65001
  neighbor 172.16.1.2 activate
  neighbor 172.16.1.2 as-override
  neighbor 172.16.1.2 soo 65000:1
  neighbor 172.16.1.2 maximum-prefix 1000 80
  neighbor 172.16.1.2 route-map CUST_A-IN in
  neighbor 172.16.1.2 route-map CUST_A-OUT out
 exit-address-family
!
ip prefix-list CUST_A-PREFIXES seq 5 permit 192.168.0.0/16 le 24
!
route-map CUST_A-IN permit 10
 match ip address prefix-list CUST_A-PREFIXES
!
route-map CUST_A-OUT permit 10
```

Notes: `soo 65000:1` is the modern per-neighbor form (older form: route-map with
`set extcommunity soo`). Same SoO value on BOTH PEs serving the same site. Always
filter + max-prefix on eBGP, even to "trusted" customers.

CE side (plain IOS router, no VRF awareness):

```
router bgp 65001
 bgp router-id 192.168.1.1
 neighbor 172.16.1.1 remote-as 65000
 network 192.168.1.0 mask 255.255.255.0
```

(`network` needs an exact RIB match — ensure 192.168.1.0/24 exists, e.g. as a connected SVI.)

CE alternative if PE can't do as-override:

```
router bgp 65001
 neighbor 172.16.1.1 allowas-in 1
```

## Verification

```
show bgp vpnv4 unicast vrf CUST_A summary        ! PE: session Established, prefixes received
show bgp vpnv4 unicast vrf CUST_A neighbors 172.16.1.2 routes
show bgp vpnv4 unicast vrf CUST_A 192.168.2.0/24 ! AS-path shows 65000 65000 (override proof) + SoO
! On CE:
show ip bgp summary
show ip bgp                                       ! remote site routes present
ping 192.168.2.1 source 192.168.1.1
```

## Rollback

```
router bgp 65000
 address-family ipv4 vrf CUST_A
  no neighbor 172.16.1.2
```

(Site falls back to whatever static/connected redistribution remains — confirm before removing on a live customer.)

## Failure Modes

| Break | First command |
| --- | --- |
| CE rejects remote-site routes | `show ip bgp neighbors 172.16.1.1 received-routes` on CE — own AS in path → as-override missing on PE |
| Routing loop on dual-homed site | SoO missing/mismatched on the two PEs: `show bgp vpnv4 unicast vrf CUST_A <prefix>` check extcommunity |
| Session idle | TCP 179 over the PE-CE link; remember PE pings must use `ping vrf CUST_A` |
| CE advertises nothing | `network` statement has no exact RIB match |
| Prefixes received then session drops | max-prefix tripped: `show bgp vpnv4 unicast vrf CUST_A summary` (PfxRcd column / state) |
