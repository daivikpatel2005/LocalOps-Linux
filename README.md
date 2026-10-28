# LocalOps — Offline Linux Troubleshooting Agent

Local-first, offline Linux troubleshooting and system diagnostic agent.

LocalOps combines an offline Small Language Model (SLM) running via Ollama with a deterministic, security-gated knowledge base and SQLite database. It provides a controlled, explainable interface for diagnosing Linux system issues without running destructive commands or sending sensitive system diagnostics to external clouds.

---

## 1. Project Purpose

When troubleshooting Linux issues (such as resource exhaustion, slow performance, network loss, or service crashes), administrators often need quick triage. Traditional scripts lack flexibility, while cloud-based AI tools risk leaking private system information and can hallucinate dangerous shell commands.

LocalOps solves this by:
- Operating **100% locally and offline** by default.
- Separating planning, deterministic validation, user confirmation, and execution.
- Treating the LLM as an unprivileged advisor whose plans must pass strict allow-lists.
- Enforcing human-in-the-loop explicit confirmation (`[y/N]`) before running any command.
- Keeping all diagnostic checks strictly **read-only** with no `sudo` privilege escalation.

> **Detailed Offline Guide:** For an in-depth technical explanation of how LocalOps diagnoses system issues with zero internet connectivity and zero cloud APIs, see [HOW_LOCALOPS_WORKS_OFFLINE.md](HOW_LOCALOPS_WORKS_OFFLINE.md).

---

## 2. Architecture

```text
User Request ("Why is my RAM full?")
       │
       ▼
[1] Planner (Local SLM + Knowledge Base)
       │
       ▼ Structured JSON Plan (problem, assessment, workflow_id, plan)
[2] Validator (Knowledge Base Allow-List Gate)
       │  - Rejects unknown commands, unapproved options, shell pipelines, metacharacters
       │  - Binds trusted safety metadata (read_only=True, requires_sudo=False)
       │  - Constructs normalized argv array
       ▼
[3] User Confirmation Gate
       │  - Displays exact command strings, purpose, and risk
       │  - Explicit approval prompt: [y/N] (default deny)
       ▼ (if approved)
[4] Command Executor
       │  - Executes via argv with shell=False
       │  - Enforces per-command timeout (default: 30s)
       │  - Truncates oversized outputs (max 64 KB)
       │  - Collects structured stdout, stderr, return codes
       ▼
[5] Analyzer & Diagnostic Report
       │  - Analyzes evidence with local SLM (or deterministic fallback)
       │  - Distinguishes observed facts from hypotheses
       │  - Filters any recommended follow-up actions
       ▼
Final Diagnosis & Observations
```

---

## 3. Supported Troubleshooting Categories

LocalOps includes 24 pre-defined, tested diagnostic workflows covering 39 allow-listed, read-only commands:

| Workflow ID | Category & Scope | Candidate Diagnostic Commands |
|---|---|---|
| `system_slow` | Overall system slowdown and load pressure | `uptime`, `free -h`, `df -h`, `ps aux` |
| `memory_problem` | RAM exhaustion, swap pressure, high memory consumers | `free -h`, `ps aux`, `uptime` |
| `disk_space` | Filesystem utilization and mount point exhaustion | `df -h`, `findmnt`, `lsblk -f` |
| `process_problem` | CPU-heavy processes and load inspection | `uptime`, `ps aux` |
| `service_problem` | Failed systemd units and daemon errors | `systemctl --failed`, `systemctl --user --failed` |
| `network_problem` | IP connectivity, routing, and DNS resolution | `ip link`, `ip addr`, `ip route`, `resolvectl status` |
| `wifi_problem` | Wi-Fi device state and radio blocks | `nmcli device wifi`, `rfkill list wifi`, `ip link` |
| `bluetooth_problem`| Bluetooth controllers, devices, and radio blocks | `bluetoothctl show`, `rfkill list bluetooth` |
| `audio_problem` | PulseAudio/PipeWire server status | `pactl info` |
| `package_problem` | Package manager database and dependency consistency | `dpkg -C`, `apt-get check` |
| `application_crash`| System core dumps and recent crash logs | `journalctl -p 3 -xb -n 50` |
| `boot_login_problem`| User sessions and login states | `loginctl list-sessions`, `whoami`, `id` |
| `time_problem` | Clock synchronization and time zone state | `timedatectl status` |
| `development_environment` | Basic compiler and runtime versions | `python3 --version`, `node --version`, `git --version`, `gcc --version` |
| `hardware_problem` | Basic PCI and USB hardware inventory | `lspci`, `lsusb`, `uname -a` |
| `flatpak_problem` | Installed Flatpak applications and runtimes | `flatpak list` |
| `overheating_thermal` | Hardware temperature sensors, fan RPM, thermal zones | `sensors`, `acpi -t`, `uptime`, `ps aux` |
| `battery_power` | Laptop battery charge, discharge rate, health state | `acpi -V`, `acpi -b`, `uptime`, `ps aux` |
| `cpu_bottleneck` | Multi-core CPU utilization, thread saturation | `mpstat -P ALL`, `lscpu`, `uptime`, `ps aux` |
| `io_disk_bottleneck` | Storage I/O wait, partition throughput, paging | `iostat`, `iostat -x`, `vmstat 1 2`, `df -h` |
| `ports_listening_services` | Open listening network ports and socket bindings | `ss -tuln`, `ss -s`, `systemctl --failed --no-pager` |
| `kernel_module_driver` | Loaded Linux kernel modules, PCI/USB driver bindings | `lsmod`, `lspci`, `lsusb`, `uname -a` |
| `system_specs_inventory` | Full system overview: CPU, memory, OS, disks | `lscpu`, `free -h`, `df -h`, `uname -a`, `lsblk -f` |
| `inode_exhaustion` | Filesystem inode capacity and exhausted inode tables | `df -i`, `df -h`, `findmnt` |

---

## 4. Prerequisites

- **Operating System:** Linux (Ubuntu 22.04+, 24.04+, Debian, Fedora, Arch, etc.)
- **Python:** Python 3.10+ (Standard library only; zero mandatory third-party pip dependencies required)
- **Local SLM:** [Ollama](https://ollama.ai) (optional for deterministic mode; required for SLM planning and analysis)
- **Recommended Model:** `qwen3:1.7b` (or `qwen2.5:1.5b`, `llama3.2:1b`, `phi3:mini`)

---

## 5. Local Ollama Setup & Configuration

### 5.1 Starting Ollama and Pulling the Model

```bash
# Start Ollama service (if not already running)
ollama serve

# In another terminal, download the default lightweight model
ollama pull qwen3:1.7b
```

### 5.2 Environment Configuration

LocalOps can be configured via environment variables:

```bash
# Custom model name (default: qwen3:1.7b)
export LOCALOPS_MODEL="qwen3:1.7b"

# Local Ollama endpoint (default: http://127.0.0.1:11434)
export LOCALOPS_OLLAMA_HOST="http://127.0.0.1:11434"

# Timeout for LLM queries in seconds (default: 60)
export LOCALOPS_LLM_TIMEOUT=45

# Timeout for individual Linux diagnostic commands in seconds (default: 30)
export LOCALOPS_COMMAND_TIMEOUT=30
```

*Note: For security, LocalOps rejects any `LOCALOPS_OLLAMA_HOST` that does not target the local loopback (`127.0.0.1` or `localhost`).*

---

## 6. Installation & Launch Commands

### Clone and Run

```bash
cd ~/LocalOps

# Verify Python syntax and environment
python3 -m py_compile app/*.py

# Run LocalOps CLI
python3 -m app.main
```

### Alternative Runner Scripts

```bash
# Manual planner test with natural language argument
python3 -m app.test_planner "why is my RAM full?"

# Manual executor test on safe read-only commands
python3 -m app.test_executor

# Manual knowledge base inspector
python3 -m app.test_knowledge
```

---

## 7. Knowledge Base & Database Structure

The knowledge base is stored in two synchronized layers:
1. **`knowledge/commands.json` (Seed File):** Human-audited JSON defining all allowed commands, permitted options, combinations, and workflows.
2. **`knowledge/localops.db` (SQLite Database):** Relational store enforcing schema consistency, foreign-key relationships (`PRAGMA foreign_keys = ON;`), and transactional updates.

### SQLite Schema

- **`schema_info`**: Tracks schema version and synchronization metadata.
- **`commands`**: Command definitions, categories, output types, read-only status, sudo restrictions.
- **`command_options`**: Allowed command-line flags and their parameter requirements.
- **`command_examples`**: Explicitly approved command and option combinations.
- **`workflows`**: Diagnostic problem domains.
- **`workflow_triggers`**: Natural-language trigger phrases for workflow matching.
- **`workflow_candidates`**: Ordered sequence of diagnostic commands for each workflow.
- **`workflow_decision_rules`**: Heuristic rules linking command findings to possible issues.

### Transactional Synchronization

When `app/knowledge.py` or `app/database.py` initializes, it synchronizes `commands.json` into SQLite inside a single atomic transaction. If any foreign-key violation or corrupt record is detected, the transaction rolls back cleanly, preserving the existing database state.

---

## 8. Safety & Security Model

LocalOps enforces defense-in-depth at every layer:

1. **Deny by Default:** Commands not listed in `knowledge/commands.json` / SQLite are unconditionally rejected.
2. **No Shell Execution:** Subprocesses are executed via `subprocess.run(argv, shell=False)`. Shell pipelines (`|`), redirects (`>`), chaining (`&&`, `;`), and command substitutions (`$(...)`, backticks) are strictly rejected.
3. **Strict Read-Only Enforcement:** Only commands with `read_only=True` in the trusted knowledge base can run. Modifying commands (`rm`, `dd`, `kill`, `sed -i`, `mkfs`) are rejected.
4. **No Privilege Escalation:** Commands requiring `sudo` are prohibited during automated diagnostics.
5. **Untrusted Model Boundary:** The validator ignores model-provided risk or permission flags and uses only trusted database records.
6. **Explicit User Approval:** Every batch of commands requires explicit `[y/N]` confirmation showing the normalized command line and purpose.
7. **Resource Protection:** Commands time out after 30 seconds; command outputs are capped at 64 KB to protect system memory.

---

## 9. Running Tests

The test suite requires no external packages, live internet access, or active LLM server:

```bash
# Run all automated unit and integration tests
python3 -m unittest discover -s tests -v
```

### Test Coverage Highlights

- **LLM Handling:** Connection failures, timeout recovery, valid/invalid JSON extraction, markdown fence handling.
- **Planner Structure:** Missing fields, `plan` as string/object, empty plans, bounded retries.
- **Security Boundaries:** Unknown commands, invalid options, shell injection, pipelines, chaining, metadata tampering.
- **Database Integrity:** SQLite initialization, schema enforcement, foreign-key constraints, transaction rollback.
- **Executor Safety:** Refusal on `confirm=False`, non-read-only denial, subprocess timeouts, non-zero return codes, output truncation.
- **Workflow Matching:** Natural language variations for memory, disk, network, wifi, bluetooth, service, and crash queries.
- **End-to-End Simulation:** Full cycle (plan → validate → confirm → execute → analyze) using mocked LLM and subprocesses.

---

## 10. Current Limitations

- **Read-Only Diagnostics:** LocalOps intentionally does not perform automatic repair, file editing, package installations, or service restarts.
- **Unsupported Problem Domains:** Hardware-level thermal management (e.g., fan speed, overheating) and kernel-level firmware flashing are unsupported.
- **Local Linux Focus:** Designed for single-node Linux systems (Ubuntu, Debian, Fedora, Arch); not designed for distributed clusters or cloud VMs with custom orchestrators.

---

## 11. Example Troubleshooting Session

```text
$ python3 -m app.main
LocalOps Linux Troubleshooting Agent
============================================================

What problem are you experiencing?
> why is my RAM full?

[1/5] Creating troubleshooting plan...
Plan created.

[2/5] Validating troubleshooting plan...
Plan validated: 3 command(s).

TROUBLESHOOTING PLAN
============================================================
1. $free -h
   Purpose: Display RAM and swap memory usage
   Risk:    safe (read-only: True, sudo: False)
2. $ps aux
   Purpose: Display information about running processes
   Risk:    safe (read-only: True, sudo: False)
3. $uptime
   Purpose: Display system uptime and load average
   Risk:    safe (read-only: True, sudo: False)

[3/5] Requesting permission...

============================================================
LocalOps wants to run the following commands:
============================================================

[1] $free -h
    Purpose : Display RAM and swap memory usage
    Risk    : safe

[2] $ps aux
    Purpose : Display information about running processes
    Risk    : safe

[3] $uptime
    Purpose : Display system uptime and load average
    Risk    : safe

============================================================
Allow these commands to run? [y/N]: y

Permission granted.

[4/5] Executing commands...

COMMAND RESULTS
============================================================

[1] $free -h
Exit code: 0
Success:   True

Output:
               total        used        free      shared  buff/cache   available
Mem:           6.6Gi       4.6Gi       251Mi        98Mi       2.0Gi       2.0Gi
Swap:          7.8Gi       1.6Gi       6.2Gi

[2] $ps aux
Exit code: 0
Success:   True

Output:
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
...

[3] $uptime
Exit code: 0
Success:   True

Output:
15:40:54 up 29 min,  0 users,  load average: 1.43, 1.37, 1.24

[5/5] Analyzing results...

LOCALOPS DIAGNOSIS
============================================================

Problem:    Elevated memory utilization
Severity:   medium
Confidence: high
Evidence:   Available memory is 2.0Gi out of 6.6Gi with active swap usage (1.6Gi).

Summary:
Initial diagnostics indicate moderate RAM pressure with 2.0Gi available headroom and active swap utilization. No immediate OOM condition observed.

Enough evidence: true
```
