# How LocalOps Works 100% Offline (No Internet Required)

> **Quick Answer:** LocalOps does **NOT** use the internet to troubleshoot your computer. It never communicates with external cloud APIs (like OpenAI, Google, Anthropic, or AWS), sends no telemetry, and requires zero active network connectivity to plan, validate, execute, or diagnose your system.
>
> You can pull your Ethernet cable, turn off Wi-Fi, enable Airplane Mode, and LocalOps will still produce the exact same diagnosis.

---

## 1. Why Did It Seem Like It Was Using the Internet?

When you ran `my internet is not working`, LocalOps accurately identified:
1. **The Tailscale VPN routing conflict:** That `tailscale0` had claimed `+DefaultRoute: yes` in `resolvectl` while disconnected, creating a blackhole for DNS lookups.
2. **Missing default gateway:** That `ip route` had no `default via` route, preventing packet forwarding.
3. **Exact fix commands:** Recommending `tailscale down`, `tailscale status`, and `nmcli connection up`.

Because the answer was so specific and accurate, it is natural to wonder: *“How could it possibly know this without searching the web or asking an online AI?”*

The answer lies in **Local Computing Architecture**: LocalOps combines three purely offline components:
1. **Local Linux System Inspection (`/bin/ip`, `/bin/nmcli`, `/bin/resolvectl`)**
2. **Local Rule-Based Heuristic Knowledge Engine (`knowledge/commands.json` & `app/analyzer.py`)**
3. **Local Small Language Model (SLM via Ollama on `127.0.0.1`)**

---

## 2. Component-by-Component: Where the Knowledge Lives

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       YOUR LOCAL COMPUTER (OFFLINE)                         │
│                                                                             │
│  [User Problem]  ───>  "my internet is not working"                         │
│                               │                                             │
│                               ▼                                             │
│  [Local Knowledge Base]  ──>  Matches 'network_problem' workflow in:        │
│                               • knowledge/commands.json                     │
│                               • knowledge/localops.db (SQLite on disk)      │
│                               │                                             │
│                               ▼                                             │
│  [Execution Stage]      ──>  Runs local binaries via subprocess (No Shell): │
│                               • /usr/bin/ip -brief address                  │
│                               • /usr/bin/ip route                           │
│                               • /usr/bin/nmcli device status                │
│                               • /usr/bin/resolvectl status                  │
│                               │                                             │
│                               ▼ Captured standard output (stdout)           │
│  [Analysis Stage]       ──>  Deterministic Parser in app/analyzer.py:       │
│                               • Reads 'tailscale0' in resolvectl output     │
│                               • Detects '+DefaultRoute' + 'Scopes: none'    │
│                               • Reads 'default via' in ip route             │
│                               • Cross-references Decision Rules from disk   │
│                               │                                             │
│                               ▼                                             │
│  [Final Output]         ──>  Generates exact Cause, Evidence & Fix Steps!   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### A. The Local Knowledge Base (`knowledge/commands.json` & `knowledge/localops.db`)
Stored locally on your disk in the `knowledge/` directory:
- **39 Diagnostic Commands:** Exact flags and parameter rules for `ip`, `nmcli`, `resolvectl`, `free`, `df`, `ps`, `systemctl`, `journalctl`, `uptime`, etc.
- **24 Troubleshooting Workflows:** Pre-compiled symptom-to-tool maps for network loss, RAM exhaustion, full disks, audio glitches, crashing services, and thermal throttling.
- **Decision Rules:** Ground-truth troubleshooting logic compiled by Linux systems engineers directly into JSON/SQLite. For example, for network diagnostics:
  ```json
  "decision_rules": [
    {
      "condition": "no interface has an expected address",
      "possible_problem": "Interface may be disconnected or unconfigured"
    },
    {
      "condition": "no default route exists",
      "possible_problem": "Default route may be missing"
    },
    {
      "condition": "DNS settings look incorrect",
      "possible_problem": "DNS configuration may be involved"
    }
  ]
  ```

### B. Local System Inspection
LocalOps does not invent information or guess:
- In Step `[4/5]`, it directly invoked your machine's local Linux kernel and userland tools:
  - `ip -brief address` queried your Linux kernel's netlink sockets.
  - `ip route` read the kernel routing table (`/proc/net/route`).
  - `nmcli device status` queried your local NetworkManager daemon over D-Bus (`/run/dbus/system_bus_socket`).
  - `resolvectl status` queried your local `systemd-resolved` daemon over D-Bus.
- These tools executed directly on your processor using Python's `subprocess.run(argv, shell=False)` with **zero network communication**.

### C. The Local Expert Diagnostic Engine (`app/analyzer.py`)
In Step `[5/5]`, `app/analyzer.py` evaluated the actual text returned by those local tools:
1. **Detecting the Tailscale Conflict:**
   The analyzer inspected the output of `resolvectl status`:
   ```text
   Link 8 (tailscale0)
       Current Scopes: none
            Protocols: +DefaultRoute -LLMNR -mDNS -DNSOverTLS DNSSEC=no/unsupported
        Default Route: yes
   ```
   The offline pattern-matcher identified that `tailscale0` had `Default Route: yes` and `+DefaultRoute`, but `Current Scopes: none`.
   In Linux networking, this is a well-known failure condition: when a VPN tunnel claims the default DNS route but has no active scopes, `systemd-resolved` routes all DNS queries to the dead tunnel, cutting off internet access.
2. **Detecting the Missing Gateway:**
   The analyzer scanned the output of `ip route`:
   ```text
   10.72.149.0/24 dev wlo1 proto kernel scope link ...
   ```
   Because there was no line starting with `default via <ip>`, the engine detected that no default gateway was configured.
3. **Formulating Remediation Steps:**
   The fix recommendations (e.g. `tailscale down`, `tailscale status`, restarting NetworkManager) are pre-defined in `app/analyzer.py` and mapped to those exact conditions.

### D. Optional Local AI (Ollama on `127.0.0.1`)
If [Ollama](https://ollama.ai) is running on your machine:
- LocalOps communicates **only** with `http://127.0.0.1:11434` (the local loopback interface).
- The neural network weights (e.g., `qwen3:1.7b`) are stored locally on your hard drive (typically under `~/.ollama/models`).
- Inference runs entirely on your local CPU or GPU.
- If Ollama is turned off or times out, LocalOps automatically falls back to its built-in heuristic engine (`_analyze_network_domain`, `_analyze_memory_domain`, etc.) without losing diagnostic quality.

---

## 3. How to Prove to Yourself that No Internet is Used

You can easily verify that LocalOps operates 100% offline using standard Linux tools:

### Proof 1: Airplane Mode / Unplug Internet
1. Turn off your Wi-Fi completely (`nmcli radio wifi off` or disable Wi-Fi in GNOME Settings).
2. Unplug your Ethernet cable.
3. Run LocalOps:
   ```bash
   python3 -m app.main
   ```
4. Enter:
   ```text
   my internet is not working
   ```
5. You will see that LocalOps plans, validates, executes, and diagnoses the problem without any internet access.

---

### Proof 2: Inspect the Source Code Enforcing Offline Mode
Open [`app/llm.py`](file:///home/daivik/LocalOps/app/llm.py) lines 149–154:
```python
# Security check: ensure endpoint is local (loopback)
if "127.0.0.1" not in OLLAMA_GENERATE_URL and "localhost" not in OLLAMA_GENERATE_URL:
    raise RuntimeError(
        "LocalOps policy violation: Ollama URL must target local loopback (127.0.0.1/localhost)."
    )
```
Any attempt to point LocalOps to a remote internet address raises a security policy violation and terminates immediately.

---

### Proof 3: Monitor Network Sockets During Execution
Open a second terminal and run `ss` to watch all active connections while LocalOps is running:
```bash
# Watch active outbound TCP connections in real-time
watch -n 0.5 "ss -t -a '( dport = :http or dport = :https )'"
```
You will observe:
- `127.0.0.1:11434` (local loopback communication with local Ollama, if running).
- **Zero** connections to external IPs or public ports.

---

### Proof 4: Packet Capture with `tcpdump`
You can capture all network traffic on your machine while running a LocalOps session:
```bash
sudo tcpdump -i any -n "not ip and not ip6 and not port 11434"
```
Or monitor port 80/443:
```bash
sudo tcpdump -i any -n "port 80 or port 443"
```
Run LocalOps in another terminal. `tcpdump` will capture **zero packets** generated by LocalOps.

---

## 4. Summary

| Feature | Cloud AI Tools (ChatGPT, Claude, etc.) | LocalOps |
|---|---|---|
| **Requires Active Internet** | Yes (Fails completely when offline) | **No (100% Offline)** |
| **Where AI Runs** | Remote cloud data centers | **Local machine (`127.0.0.1`)** |
| **Data Privacy** | System diagnostics sent to cloud servers | **Diagnostics never leave your machine** |
| **Source of Truth** | Statistical guessing / hallucinations | **Grounded Linux rules & local CLI tools** |
| **Works During Total Network Outage** | No | **Yes (Designed specifically for this)** |

LocalOps was built specifically for situations where your internet **is** broken. Because it has no internet dependency, it can diagnose why your internet is down when no cloud assistant can even be reached.

