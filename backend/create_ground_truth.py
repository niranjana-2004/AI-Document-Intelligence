import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path

# Manually verified ground truth transcriptions for all 7 pages of text-to-handwriting.pdf
GROUND_TRUTH_PAGES = {
    1: """Niranjana A S 21BIT042 Notes on TCP Attacks
1. TCP SYN Flood
TCP SYN Flood is a denial-of-service (DoS/DDoS) attack that exploits the TCP three-way handshake (SYN, SYN-ACK, ACK). TCP is connection-oriented, so a server must reserve memory for every connection request it receives. The attacker abuses this by starting many handshakes and never finishing them, until the server has no room left for genuine users. It is called a half-open attack because the connection is left in the SYN_RECEIVED state waiting for an ACK that never comes.
How the attack works:
1. The attacker sends a very large number of SYN packets to the target port, usually with spoofed (fake) source IP addresses.
2. For each SYN packet, the server allocates a Transmission Control Block (TCB) entry in its backlog queue and replies with a SYN-ACK.
3. That SYN-ACK goes to the spoofed address, so no ACK ever returns.
The server keeps retransmitting and holding""",

    2: """the entry until it times out.
4. The backlog queue fills up. New SYN packets from legitimate clients are dropped or ignored.
Impact:
- Service unavailability: Web servers and APIs stop accepting new connections.
- Resource exhaustion: Memory and connection-table space are consumed even at modest traffic rates.
- Hard to trace: Spoofed source addresses hide the real attacker.
Mitigation:
- SYN cookies: Server encodes connection state in the SYN-ACK sequence number and stores nothing until a valid ACK returns.
- Tuning: Larger backlog queue, shorter SYN_RECEIVED timeout, fewer SYN-ACK retries.
- Network defence: Rate limiting, firewall filtering, and ingress filtering (BCP 38) against spoofed IPs.

2. TCP Session Hijacking
TCP Session Hijacking is an attack in which the attacker takes control of an already established session between a client and a server.
Authentication normally happens only at the start of a session, so whoever takes over""",

    3: """afterwards inherits the legitimate user's session (for example a logged-in Telnet, SSH or web session) without needing the password. TCP identifies packets by IP addresses, port numbers and sequence/acknowledgment numbers. If an attacker learns or predicts these values, the server cannot tell the attacker's packets from the real client's.
How the attack works:
1. Sniff / Track: The attacker monitors the session (e.g. man-in-the-middle position or same network segment) and records IP, ports and current sequence numbers.
2. Desync: The real client is disrupted or its packets are blocked so that its sequence numbers fall out of step with the server.
3. Injection: The attacker sends a spoofed packet using the client's IP and a valid expected sequence number. The server accepts it as genuine.
4. Takeover: The attacker now talks to the server as the client, while the real client loses the connection.
Impact:
- Unauthorized access: Attacker can read data,""",

    4: """execute commands, or modify traffic without password cracking.
- ACK storm: The out-of-sync client and server keep exchanging ACKs, causing extra network load.
Mitigation:
- End-to-end encryption: TLS/SSL, SSH, and IPSec make payload sniffing and injection ineffective.
- Randomised initial sequence numbers: Make prediction hard (blind hijacking).
- Session hygiene: Secure, expiring session tokens, re-authentication for sensitive actions, avoiding unencrypted protocols like Telnet.

3. TCP RST Attack
A TCP RST (Reset) flag in TCP header tells the receiver to abort a connection immediately without the normal FIN-based closing procedure. It is meant for error conditions, such as data arriving for a port with no listener. In a TCP RST attack (also called connection reset or reset spoofing attack), the attacker forges an RST segment so that a healthy connection is terminated. It is a targeted form of denial of service because it kills specific connections rather than flooding the whole host.""",

    5: """How the attack works:
1. Sniff / Guess: The attacker observes the connection (or guesses it) and determines the IP addresses and port numbers of both endpoints.
2. Forged RST: The attacker crafts an RST packet with the source IP of one endpoint and a sequence number that falls inside the receiver's acceptable window.
3. Disconnection: The receiver validates the segment, believes the peer wants to reset, and immediately closes the connection.
4. Denial of Service: The other endpoint finds the connection broken and any in-progress transfer fails.
Impact:
- Dropped connections: Long-lived sessions such as BGP, video streaming, file transfers and SSH tunnels are most affected.
- Censorship / Interference: Forged resets have also been used by middleboxes to cut specific connections.
- Low cost for attackers: One small packet can end a session.
Mitigation:
- Stricter RST validation (RFC 5961): Stack accepts a reset only if the sequence number exactly matches, otherwise sends a challenge ACK.
- Cryptographic protection: IPSec, TCP MD5 or TCP-AO sessions prevent forged segments being accepted.
- Monitoring: IDS/IPS rules to flag unexpected bursts of""",

    6: """RST packets, random sequence numbers, etc.

4. TCP ACK Flood
A TCP ACK Flood is a volumetric DDoS attack in which the attacker sends an overwhelming number of TCP packets with the ACK flag set to the target.
Under normal operation, ACK packets only make sense as part of an existing connection. Because the packets are unsolicited, the target has to inspect each one, search its connection state tables, find no match, and then drop it or answer with an RST.
Doing this millions of times per second consumes processing power and bandwidth.
How the attack works:
1. The attacker (often a botnet) sends a continuous stream of TCP ACK packets, usually with random or spoofed source addresses and ports.
2. The packet arrives at the server or a device in front of it, such as a stateful firewall or load balancer.
3. The device checks its state table for a matching connection. None exists, so the packet is discarded or an RST is""",

    7: """returned.
4. The heavy lookup load and traffic volume exhaust CPU and link capacity, so legitimate traffic is delayed or dropped.
Impact:
- Network congestion: Bandwidth is saturated by junk traffic.
- Device overload: Stateful firewalls, NAT, and load balancers are hit hardest because they perform per-packet state checks.
- Collateral effect: RST replies add outbound traffic and can reveal the target to the attacker.
Mitigation:
- Stateful inspection: Drop ACKs that do not belong to a tracked connection as early as possible.
- Rate limiting and filtering: Limit packets per source, deploy SYN/ACK proxies and upstream blackholing.
- DDoS protection: Scrubbing services, CDNs, and Anycast absorb large floods before they reach origin servers."""
}

if __name__ == "__main__":
    gt_dir = Path("ground_truth")
    gt_dir.mkdir(parents=True, exist_ok=True)
    for p_num, text in GROUND_TRUTH_PAGES.items():
        (gt_dir / f"page_{p_num:03d}.txt").write_text(text, encoding="utf-8")
        print(f"Saved ground truth for Page {p_num} ({len(text)} chars, {len(text.splitlines())} lines, {len(text.split())} words)")
