# Recipe: Campus L2/L3 Boundary — SVIs + HSRP + DHCP Relay (IOS-XE)

## Intent
Terminate user VLANs at a distribution switch pair with redundant first-hop gateways.

## Design Context
The standard campus pattern (see `../../architecture/campus_enterprise.md`). Decisions
baked in here: HSRPv2 (supports v6 groups, ms timers), gateway load split by VLAN
(odd VLANs active on D1, even on D2), STP root aligned with HSRP active per VLAN
(misalignment = traffic crossing the inter-switch link for no reason), uplink tracking
so gateway failover follows upstream failures.

## Prerequisites
- VLANs exist on both distribution switches and access trunks carry them.
- Routed uplinks toward core (this recipe assumes L3 from distribution up).

## Topology Assumption
D1 + D2 distribution pair; VLAN 10 (users, 10.10.0.0/24) and VLAN 20 (voice, 10.20.0.0/24).
Virtual gateways .1; D1 real .2, D2 real .3. DHCP server 10.50.0.5.

## Configuration

D1 (active for VLAN 10, standby for VLAN 20; D2 mirrors with priorities swapped):

```
interface Vlan10
 description USERS
 ip address 10.10.0.2 255.255.255.0
 ip helper-address 10.50.0.5
 standby version 2
 standby 10 ip 10.10.0.1
 standby 10 priority 110
 standby 10 preempt delay minimum 60
 standby 10 timers msec 250 msec 750
 standby 10 authentication md5 key-string HSRP_KEY_10
 standby 10 track 100 decrement 25
!
interface Vlan20
 description VOICE
 ip address 10.20.0.2 255.255.255.0
 ip helper-address 10.50.0.5
 standby version 2
 standby 20 ip 10.20.0.1
 standby 20 priority 90
 standby 20 preempt delay minimum 60
 standby 20 timers msec 250 msec 750
 standby 20 authentication md5 key-string HSRP_KEY_20
!
track 100 interface TenGigabitEthernet1/0/48 line-protocol
```

D2: same but priority 90 on VLAN 10, 110 on VLAN 20, its own track object.

Notes:
- `preempt delay minimum 60` — without preempt the priority plan is decorative after the
  first failover; the delay stops a rebooting switch grabbing active before its routing converges.
- Track decrement must push priority BELOW the peer, not equal to it: 110 − 25 = 85 < 90
  triggers preempt takeover. A decrement of 20 (110 − 20 = 90, equal) would NOT fail over —
  equal priority does not preempt. This off-by-design mistake is common in real configs.
- Timers 250/750ms ≈ sub-second failover without BFD. Don't go lower on software-switched
  platforms.
- STP alignment (RPVST+): on D1 `spanning-tree vlan 10 priority 4096` and VLAN 20
  priority 8192; mirrored on D2 (see `stp_hardening.md`).

## Verification

```
show standby brief                 ! Active/Standby per group, virtual IP
show standby Vlan10                ! timers, preempt, track state
show track 100                     ! Up + tracked object
! From a host: default GW ping, then fail D1 uplink and confirm:
show standby brief                 ! D2 took Active for VLAN 10
! DHCP test from a client VLAN port (helper works)
```

Failover test target: < 1s gateway loss with the ms timers.

## Rollback

```
interface Vlan10
 no standby 10
 no ip helper-address 10.50.0.5
no track 100
```

(Hosts using .1 lose their gateway the moment HSRP is removed unless an SVI owns .1 — re-IP first.)

## Failure Modes

| Break | First command |
| --- | --- |
| Both switches Active (split brain) | trunk between D1/D2 not carrying the VLAN, or auth mismatch: `show standby`, check `%HSRP-4-BADAUTH` |
| Failover never happens on uplink loss | track object missing or decrement too small: `show standby Vlan10 | include Track|Priority` |
| Clients get no DHCP | `ip helper-address` present? server reachable from SVI source? `debug ip dhcp server packet` on server side |
| Random slow paths | STP root ≠ HSRP active: `show spanning-tree vlan 10` vs `show standby brief` |
| Flapping active/standby | timers too aggressive for platform / L2 instability underneath: `show standby` state-change counts |
