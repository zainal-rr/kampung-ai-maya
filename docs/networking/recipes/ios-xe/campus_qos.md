# Recipe: Campus QoS Baseline — Trust Boundary + Marking + Queuing (IOS-XE)

## Intent
Classify and mark traffic at the access edge, trust nothing from users, and queue so
voice/video survive congestion.

## Design Context
The model: mark at the edge (trust boundary), queue everywhere. Phones mark their own
traffic (EF for voice RTP, CS3 for signaling) — extend trust only to phones via CDP/LLDP
or conditional trust. User PCs are never trusted: their DSCP is rewritten by policy.
Catalyst 9k uses MQC end-to-end (the old `mls qos` world is gone). Standard markings:
EF voice, AF41 interactive video, CS3 signaling, AF21 transactional data, default (0)
best effort, CS1 scavenger.

## Prerequisites
- Voice VLAN deployed; phones discoverable via CDP/LLDP.
- Agreement on the marking table above (keep it boring and standard).

## Topology Assumption
Cat9k access switch, host ports Gi1/0/1-44 (PC + phone), uplinks Te1/0/47-48.

## Configuration

Classification ACLs + class-maps (access edge, ingress):

```
ip access-list extended VOICE-RTP
 permit udp any any range 16384 32767
ip access-list extended SIGNALING
 permit tcp any any range 2000 2002
 permit udp any any eq 5060
 permit tcp any any eq 5061
!
class-map match-any VOICE
 match dscp ef
 match access-group name VOICE-RTP
class-map match-any SIGNALING-C
 match dscp cs3
 match access-group name SIGNALING
```

Ingress marking policy — trust phone markings conditionally, re-mark the rest:

```
policy-map EDGE-IN
 class VOICE
  set dscp ef
  police 128k conform-action transmit exceed-action drop
 class SIGNALING-C
  set dscp cs3
 class class-default
  set dscp default
!
interface range GigabitEthernet1/0/1 - 44
 switchport voice vlan 20
 trust device cisco-phone
 service-policy input EDGE-IN
```

(`trust device cisco-phone`: DSCP trusted only while a phone is detected via CDP;
otherwise the port falls back to untrusted + policy re-marking. The policer caps a single
"voice" flow — a PC spoofing EF gets 128k, not the priority queue's full bandwidth.)

Egress queuing (uplinks and access ports):

```
policy-map EDGE-OUT
 class VOICE
  priority level 1
  police rate percent 10
 class SIGNALING-C
  bandwidth remaining percent 10
 class class-default
  bandwidth remaining percent 80
  fair-queue
!
interface range TenGigabitEthernet1/0/47 - 48
 service-policy output EDGE-OUT
```

(Priority queue always policed — an unpoliced PQ can starve everything else. Percentages,
not absolute rates, so the policy ports across link speeds.)

## Verification

```
show policy-map interface GigabitEthernet1/0/5 input    ! class hit counters incrementing
show policy-map interface TenGigabitEthernet1/0/47 output   ! queue stats, PQ drops?
show interfaces Gi1/0/5 | include trust                  ! n/a -> use:
show platform hardware fed switch active qos queue stats interface Te1/0/47
! Live test: saturate the uplink with iperf, run a voice call -> MOS stays good,
! class-default shows drops, VOICE shows none
```

The proof is drops landing in class-default while VOICE stays clean under load.

## Rollback

```
interface range GigabitEthernet1/0/1 - 44
 no service-policy input EDGE-IN
 no trust device cisco-phone
interface range TenGigabitEthernet1/0/47 - 48
 no service-policy output EDGE-OUT
no policy-map EDGE-IN
no policy-map EDGE-OUT
```

(Removing QoS returns ports to default DSCP-trust-through behaviour on 9k — traffic flows, just unprotected.)

## Failure Modes

| Break | First command |
| --- | --- |
| Voice choppy under load | `show policy-map interface <uplink> output` — PQ drops? policer too small? marking lost upstream? |
| All counters zero on ingress policy | policy on wrong direction/port, or classification never matches: check ACL hits |
| PC traffic in priority queue | trust extended unconditionally (`trust device` missing, port trusts DSCP): verify with phone unplugged |
| Phone traffic remarked to 0 | CDP/LLDP not detecting phone: `show cdp neighbors detail`, voice VLAN config |
| Policy rejected on attach | platform queue limits (e.g. >1 priority level): simplify to the structure above |
