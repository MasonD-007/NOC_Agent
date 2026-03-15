export const MOCK_CONVERSATIONS = [
  {
    id: 'c-001',
    title: 'UDP Flood — edge-sw-02',
    timestamp: '14:32',
    severity: 'critical',
    unread: false,
  },
  {
    id: 'c-002',
    title: 'Brute Force Login Attempt',
    timestamp: '13:15',
    severity: 'warning',
    unread: false,
  },
  {
    id: 'c-003',
    title: 'High Threat Payload Detected',
    timestamp: '11:47',
    severity: 'critical',
    unread: false,
  },
  {
    id: 'c-004',
    title: 'Suspicious Endpoint Scanning',
    timestamp: 'Yesterday',
    severity: 'warning',
    unread: false,
  },
  {
    id: 'c-005',
    title: 'Traffic Spike — core-router',
    timestamp: 'Yesterday',
    severity: 'info',
    unread: false,
  },
]

export const MOCK_MESSAGES = [
  {
    id: 'm-001',
    role: 'user',
    content: 'BruteForceLoginAttempt firing on edge-sw-02. 847 failed SSH attempts in the last 5 minutes from 192.168.1.200.',
    timestamp: '14:30:12',
  },
  {
    id: 'm-002',
    role: 'assistant',
    timestamp: '14:30:14',
    phases: [
      {
        name: 'triage',
        label: 'Triage',
        content: 'Severity: CRITICAL\nType: Security — Brute Force\n\nThis alert represents an active brute-force SSH attack against edge-sw-02. The volume of 847 failed attempts in 5 minutes (≈2.8 attempts/sec) from a single source IP is consistent with automated credential stuffing. Immediate containment is required.',
      },
      {
        name: 'investigate',
        label: 'Investigation',
        content: 'Root Cause Analysis:\n• Source IP 192.168.1.200 is attempting dictionary-based SSH login against edge-sw-02\n• Rate of attack (2.8 req/s) suggests scripted tooling (Hydra / Medusa class)\n• No successful logins detected in current log window\n• edge-sw-02 is a network switch — compromise would grant full L2 access to demo-network\n\nRisk Factors:\n• Default credentials (admin/hackathon) are in use on this device\n• No existing rate-limit or IP ban rules observed\n• Lateral movement possible to core-router and edge-sw-01 if compromised',
      },
      {
        name: 'recommend',
        label: 'Recommendations',
        content: 'Immediate Actions (Priority 1):\n  1. Block 192.168.1.200 at firewall — block_ip("192.168.1.200")\n  2. Rate-limit SSH to max 3 attempts/60s from any single source\n  3. Force password rotation on edge-sw-02 admin account\n\nShort-term (Priority 2):\n  4. Enable SSH key-based auth only, disable password auth\n  5. Restrict SSH access to management VLAN only\n  6. Add alerting for >10 failed logins in 60s',
      },
      {
        name: 'report',
        label: 'Incident Report',
        content: '═══════════════════════════════════════\nNOC INCIDENT REPORT — INC-2024-0342\n═══════════════════════════════════════\nTime:     2024-11-15 14:30:12 UTC\nDevice:   edge-sw-02\nSeverity: CRITICAL\nType:     Brute Force SSH Attack\n\nSummary:\nAn automated SSH brute-force attack was detected originating from internal IP 192.168.1.200 targeting the edge switch edge-sw-02. 847 failed authentication attempts were recorded over a 5-minute window. No successful logins were observed. The attacking host (rogue-device) appears to be a previously unknown device on the demo-network segment.\n\nStatus: AWAITING CONTAINMENT ACTION',
      },
    ],
  },
  {
    id: 'm-003',
    role: 'user',
    content: 'Can you also check if there are any related traffic spikes around that same timeframe?',
    timestamp: '14:31:55',
  },
  {
    id: 'm-004',
    role: 'assistant',
    timestamp: '14:32:01',
    phases: [
      {
        name: 'investigate',
        label: 'Investigation',
        content: 'Correlating traffic data around 14:25–14:35 UTC...\n\n• edge-sw-02 inbound packets: 50,000 pps (baseline: ~200 pps) — 250× spike\n• UDP traffic: 1.0 Gbps sustained from unknown-device (192.168.1.200)\n• TCP/SSH traffic: 2.8 req/s (the brute force)\n• core-router: no anomalous traffic observed\n• edge-sw-01: no anomalous traffic observed\n\nConclusion: The same rogue device (192.168.1.200) is simultaneously running a UDP flood AND an SSH brute force. This is a coordinated dual-vector attack — the flood may be a distraction or resource exhaustion tactic while the brute force attempts to gain access.',
      },
      {
        name: 'report',
        label: 'Updated Assessment',
        content: 'UPDATED: This is a dual-vector attack:\n  Vector 1: UDP Flood (1 Gbps) — Volumetric DDoS against edge-sw-02\n  Vector 2: SSH Brute Force (847 attempts) — Credential attack on edge-sw-02\n\nBoth originate from 192.168.1.200 (container: rogue-device).\n\nBlocking this IP will neutralize both attack vectors simultaneously.',
      },
    ],
  },
]

export const SYSTEM_STATUS = [
  { label: 'AI Agent', status: 'online', detail: 'port 5050' },
  { label: 'Prometheus', status: 'online', detail: 'port 9090' },
  { label: 'AlertManager', status: 'online', detail: 'port 9093' },
  { label: 'Log Aggregator', status: 'degraded', detail: 'port 8000' },
  { label: 'MCP Server', status: 'offline', detail: 'stdio' },
]
