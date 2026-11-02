# What You Can Ask LocalOps — Diagnostic Questions & Troubleshooting Guide

> **Overview:** LocalOps is an offline, security-gated Linux troubleshooting agent. You can ask questions in natural language, describe symptoms, or ask about system health.
>
> LocalOps will automatically:
> 1. Match your inquiry to an allow-listed diagnostic workflow.
> 2. Create a structured, safe troubleshooting plan with zero harmful side-effects.
> 3. Display the exact commands and request your explicit permission `[y/N]`.
> 4. Execute only read-only diagnostic commands via `shell=False`.
> 5. Provide an insightful diagnosis explaining **What is Happening**, the **Likely Root Cause**, and **Step-by-Step Fix Instructions**.

---

## Quick Reference: 28 Diagnostic Categories

| # | Category | What You Can Ask (Sample Prompts) | Safe Diagnostic Commands Executed |
|---|---|---|---|
| 1 | **System Performance** | *"Why is my system slow?"*, *"Linux is lagging"*, *"Laptop is slow"* | `uptime`, `free -h`, `df -h`, `ps aux` |
| 2 | **RAM & Memory Pressure** | *"Why is my RAM full?"*, *"Out of memory"*, *"High memory usage"* | `free -h`, `ps aux`, `uptime` |
| 3 | **Disk Storage Full** | *"My disk is full"*, *"No space left on device"*, *"Hard drive low"* | `df -h`, `lsblk -f`, `findmnt` |
| 4 | **Inode Exhaustion** | *"Inode usage is high"*, *"Cannot create new files"*, *"Disk full but df has space"* | `df -i`, `df -h`, `findmnt` |
| 5 | **CPU Saturation** | *"Why is CPU usage high?"*, *"CPU is maxed out"*, *"Processor bottleneck"* | `mpstat -P ALL`, `lscpu`, `uptime`, `ps aux` |
| 6 | **Storage I/O Lag** | *"Disk I/O is slow"*, *"High iowait"*, *"Storage latency is lagging"* | `iostat`, `iostat -x`, `vmstat 1 2`, `df -h` |
| 7 | **Slow Startup & Boot** | *"Why is my boot so slow?"*, *"Laptop takes forever to start"*, *"Slow boot"* | `systemd-analyze time`, `systemd-analyze blame`, `systemctl --failed` |
| 8 | **Internet Connectivity** | *"Why is my internet not working?"*, *"DNS not resolving"*, *"No internet"* | `ip -brief address`, `ip route`, `nmcli device status`, `resolvectl status` |
| 9 | **Wi-Fi & Wireless** | *"My Wi-Fi keeps disconnecting"*, *"Wi-Fi not working"*, *"Cannot connect to Wi-Fi"* | `nmcli device status`, `rfkill list`, `ip link` |
| 10 | **LAN & Gateway ARP** | *"Cannot reach local router"*, *"Local network device not reachable"*, *"ARP issue"* | `ip neigh`, `ip -brief address`, `ip route` |
| 11 | **Open Ports & Sockets** | *"What ports are open?"*, *"Which ports are listening?"*, *"Port conflict"* | `ss -tuln`, `ss -s`, `systemctl --failed --no-pager` |
| 12 | **Bluetooth Connectivity**| *"My Bluetooth headphones keep disconnecting"*, *"Bluetooth not working"* | `bluetoothctl show`, `bluetoothctl devices`, `rfkill list` |
| 13 | **Audio & Sound Server** | *"No sound"*, *"Audio not working"*, *"Sound keeps cutting out"* | `pactl info`, `pactl list short sinks`, `pactl list short sources` |
| 14 | **Failed System Services**| *"Why is my system service failing?"*, *"Service won't start"*, *"Failed daemon"* | `systemctl --failed`, `systemctl --user --failed`, `journalctl -p err -b` |
| 15 | **Application Crashes** | *"An application keeps crashing"*, *"Program closed unexpectedly"* | `journalctl -p err -b -n 50`, `ps aux` |
| 16 | **Process Investigation** | *"Which process is taking all resources?"*, *"Unresponsive app"* | `ps aux`, `uptime` |
| 17 | **Laptop Overheating** | *"Why is my laptop overheating?"*, *"CPU temp is high"*, *"Fan spinning fast"* | `sensors`, `acpi -t`, `uptime`, `ps aux` |
| 18 | **Battery & Power** | *"Why is my battery draining fast?"*, *"Battery not charging"*, *"Battery health"* | `acpi -V`, `acpi -b`, `uptime`, `ps aux` |
| 19 | **Package Manager** | *"Package installation failed"*, *"Broken package dependencies"*, *"dpkg error"* | `dpkg --audit`, `apt-get check`, `apt list --upgradable` |
| 20 | **Kernel Drivers & Modules**| *"Check loaded kernel modules"*, *"Driver issue"*, *"Kernel module problem"* | `lsmod`, `lspci`, `lsusb`, `uname -a` |
| 21 | **Hardware Peripherals** | *"USB device not recognized"*, *"Hardware not detected"*, *"PCI card check"* | `lspci`, `lsusb`, `uname -a` |
| 22 | **System Specs Inventory**| *"Show my computer specs"*, *"Hardware overview"*, *"System specifications"* | `lscpu`, `free -h`, `df -h`, `uname -a`, `lsblk -f` |
| 23 | **OS & Linux Release** | *"What OS am I running?"*, *"Check my Linux version"*, *"What distro is this?"* | `lsb_release -a`, `uname -a`, `hostnamectl status` |
| 24 | **System Clock & Time** | *"Clock is wrong"*, *"Timezone is incorrect"*, *"NTP time sync issue"* | `timedatectl status`, `timedatectl timesync-status` |
| 25 | **Locale & Keyboard** | *"Wrong system language"*, *"Keyboard layout wrong"*, *"Character encoding error"* | `localectl status`, `timedatectl status` |
| 26 | **User Sessions & Logins**| *"Who is logged in?"*, *"User session problem"*, *"Login seat status"* | `loginctl list-sessions`, `systemctl --failed`, `journalctl -p err` |
| 27 | **Dev Environment** | *"Check my dev tools"*, *"Is Python and Node installed?"*, *"Compiler versions"* | `python3 --version`, `node --version`, `npm --version`, `git --version` |
| 28 | **Flatpak Applications** | *"Check installed flatpak apps"*, *"Flatpak list"*, *"Flatpak runtime issue"* | `flatpak list` |

---

## Detailed Category Guides & Example Outputs

### 1. System Performance & Responsiveness
- **Example Prompts:**
  - *"Why is my system slow?"*
  - *"Ubuntu is running very slowly"*
  - *"Laptop is lagging and freezing"*
  - *"Why is my computer running so slow?"*
- **What LocalOps Runs:**
  - `$ uptime` (Inspects 1, 5, and 15-minute load averages)
  - `$ free -h` (Checks available RAM vs. buffer/page cache)
  - `$ df -h` (Checks if storage partitions are $\ge 90\%$ full)
  - `$ ps aux` (Identifies top CPU- and memory-consuming processes)
- **What It Diagnoses:**
  Identifies whether the bottleneck is CPU load, memory exhaustion, swap thrashing, or disk capacity.
- **Example Recommended Fixes:**
  - Shows top process PIDs consuming CPU.
  - Suggests lowering process priority with `renice` or terminating runaway workloads.

---

### 2. RAM & Memory Pressure
- **Example Prompts:**
  - *"Why is my RAM full?"*
  - *"System is running out of memory"*
  - *"RAM usage is very high"*
  - *"Why is swap usage high?"*
- **What LocalOps Runs:**
  - `$ free -h` (Reads total, used, free, buff/cache, and available memory)
  - `$ ps aux` (Ranks processes by `%MEM` and RSS)
  - `$ uptime` (Cross-checks load)
- **What It Diagnoses:**
  - **Linux Page Cache Clarification:** Explains whether memory is actually exhausted or simply utilized by the Linux kernel's high-speed page cache (`buff/cache`), which is automatically freed when applications need it.
  - **Memory Leaks:** Flags applications consuming unusual percentages of physical RAM.
- **Example Recommended Fixes:**
  - Close or restart specific high-memory browser tabs or development servers.
  - Adjust container memory constraints.

---

### 3. Disk Space & Filesystem Capacity
- **Example Prompts:**
  - *"My disk is full"*
  - *"No space left on device"*
  - *"Why is my root partition full?"*
  - *"Storage space is running out"*
- **What LocalOps Runs:**
  - `$ df -h` (Filesystem usage per mount point)
  - `$ lsblk -f` (Block devices, partitions, filesystem types, and UUIDs)
  - `$ findmnt` (Mount hierarchy and options)
- **What It Diagnoses:**
  Identifies the exact filesystem partition exceeding safety thresholds (e.g., `/dev/nvme0n1p9` mounted at `/` is at $95\%$ capacity).
- **Example Recommended Fixes:**
  - Clean old systemd journal logs: `journalctl --vacuum-size=200M`
  - Clear APT package cache: `sudo apt clean`
  - Prune Docker images and build caches: `docker system prune`
  - Find top 10 largest directories: `du -h -d 1 / 2>/dev/null | sort -hr | head -n 10`

---

### 4. Slow Startup & Boot Delays
- **Example Prompts:**
  - *"Why is my boot so slow?"*
  - *"Laptop takes forever to start"*
  - *"Computer takes too long to boot up"*
  - *"Slow startup"*
- **What LocalOps Runs:**
  - `$ systemd-analyze time` (Total duration in kernel, initrd, and userspace)
  - `$ systemd-analyze blame` (Lists every startup unit ordered by initialization duration)
  - `$ systemd-analyze critical-chain` (Identifies sequential dependency bottlenecks)
  - `$ systemctl --failed --no-pager` (Checks for services that crashed during boot)
- **What It Diagnoses:**
  Pins down the exact systemd units delaying boot completion (e.g. `NetworkManager-wait-online.service` blocking for 15 seconds, or a slow disk mount).
- **Example Recommended Fixes:**
  - Disable blocking network wait services: `sudo systemctl disable NetworkManager-wait-online.service`
  - Disable non-essential startup services: `sudo systemctl disable <service-name>`

---

### 5. Internet & DNS Issues
- **Example Prompts:**
  - *"Why is my internet not working?"*
  - *"DNS is not working"*
  - *"Websites are not loading"*
  - *"Internet keeps dropping"*
- **What LocalOps Runs:**
  - `$ ip -brief address` (Layer 3 IP address assignment on interfaces)
  - `$ ip route` (Default gateway configuration in kernel routing table)
  - `$ nmcli device status` (NetworkManager interface and connection status)
  - `$ resolvectl status` (systemd-resolved DNS servers, link scopes, and default routes)
- **What It Diagnoses:**
  - **VPN Conflicts:** Detects inactive or unconfigured VPN tunnels (e.g. `tailscale0`) that hijack default DNS routing.
  - **Missing Gateways:** Detects absence of a `default via <ip>` gateway.
  - **Captive Portals:** Detects Wi-Fi link UP with local IP, pointing to web authentication or router WAN failure.
- **Example Recommended Fixes:**
  - Disconnect conflicting VPN: `tailscale down`
  - Ping local router: `ping -c 3 <gateway-ip>`
  - Check captive portal: open `http://neverssl.com` in browser.

---

### 6. Laptop Overheating & Thermal Throttling
- **Example Prompts:**
  - *"Why is my laptop overheating?"*
  - *"CPU temperature is high"*
  - *"Fan is spinning very fast"*
  - *"Thermal throttling"*
- **What LocalOps Runs:**
  - `$ sensors` (Hardware thermal zone temperature readings and fan RPM)
  - `$ acpi -t` (ACPI thermal zone readings)
  - `$ uptime` (Load correlation)
  - `$ ps aux` (Processes generating thermal load)
- **What It Diagnoses:**
  Compares peak core temperatures against safe operating thresholds ($<70^\circ\text{C}$ = Normal, $70\text{--}84^\circ\text{C}$ = Elevated, $\ge 85^\circ\text{C}$ = High / Throttling Risk).
- **Example Recommended Fixes:**
  - Identifies top CPU processes to reduce workload.
  - Recommends cleaning air intake vents and elevating chassis.

---

### 7. Bluetooth Issues
- **Example Prompts:**
  - *"My Bluetooth headphones keep disconnecting"*
  - *"Bluetooth not working"*
  - *"Cannot connect Bluetooth device"*
  - *"Bluetooth is disabled"*
- **What LocalOps Runs:**
  - `$ bluetoothctl show` (Controller power, discoverable, and pairable states)
  - `$ bluetoothctl devices` (Known and paired devices)
  - `$ rfkill list` (Hardware and software wireless radio switches)
- **What It Diagnoses:**
  Distinguishes between a soft-blocked radio, hard-blocked physical switch, powered-down controller, or missing Bluetooth firmware.
- **Example Recommended Fixes:**
  - Unblock radio: `sudo rfkill unblock bluetooth`
  - Power on controller: `bluetoothctl power on`
  - Reconnect device: `bluetoothctl connect <MAC-address>`

---

### 8. Audio & Sound Issues
- **Example Prompts:**
  - *"No sound"*
  - *"Audio not working"*
  - *"Sound keeps cutting out"*
  - *"Microphone not working"*
- **What LocalOps Runs:**
  - `$ pactl info` (Sound server: PulseAudio vs. PipeWire status)
  - `$ pactl list short sinks` (Output playback devices)
  - `$ pactl list short sources` (Input recording/microphone devices)
- **What It Diagnoses:**
  Detects "Dummy Output" (null sink fallback when audio hardware drivers fail to claim hardware), muted sinks, or inactive sound servers.
- **Example Recommended Fixes:**
  - Restart user sound server: `systemctl --user restart pipewire pipewire-pulse wireplumber`
  - Verify user audio group membership: `id`

---

### 9. Operating System & Linux Distribution Details
- **Example Prompts:**
  - *"What OS am I running?"*
  - *"Check my Linux version"*
  - *"What Ubuntu version do I have?"*
  - *"Show my operating system details"*
- **What LocalOps Runs:**
  - `$ lsb_release -a` (Distributor, description, release version, codename)
  - `$ uname -a` (Kernel release and hardware architecture)
  - `$ hostnamectl status` (OS release, chassis, machine ID, architecture)
- **What It Diagnoses:**
  Provides an authoritative summary of your Linux distribution, kernel release version, and architecture without querying external servers.

---

## All 45 Allow-Listed Diagnostic Commands

Every command listed below is verified **100% read-only**, requires **no sudo**, and will **never modify system files or install/remove software**:

| Command | Permitted Safe Options / Variations | Purpose |
|---|---|---|
| `uptime` | `uptime`, `-p` (pretty), `-s` (since) | System uptime and load averages |
| `free` | `-h`, `-m`, `-g`, `-k`, `-b`, `-w` (wide), `-t` (total) | RAM and swap utilization |
| `df` | `-h`, `-i` (inodes), `-T` (type), `-k`, `-m`, `--total` | Filesystem partition capacity |
| `ps` | `aux`, `-ef`, `auxf` (tree), `ax`, `-e` | Running process inspection |
| `top` | `-b -n 1` (non-interactive batch snapshot) | CPU and memory process ranking |
| `uname` | `-a`, `-r` (kernel), `-m` (arch), `-s`, `-v`, `-n` | Kernel and system architecture |
| `lscpu` | `lscpu`, `-e` (extended), `-p` (parseable) | CPU cores, cache, and topology |
| `lsblk` | `-f` (filesystem UUIDs), `-a`, `-m`, `-d`, `-t` | Block storage device hierarchy |
| `findmnt` | `findmnt`, `-l` (list), `-D` (df-style), `-a` | Mount point tree and options |
| `ip` | `-brief address`, `address`, `route`, `link`, `neigh` | Network interfaces, routes, ARP |
| `ss` | `-s` (summary), `-tuln`, `-tulpn`, `-tlpn`, `-ta`, `-ua` | Sockets and listening ports |
| `nmcli` | `device status`, `connection show`, `radio all`, `device wifi list` | NetworkManager device and Wi-Fi state |
| `rfkill` | `list`, `list wifi`, `list bluetooth` | Wireless radio killswitch status |
| `resolvectl`| `status`, `dns`, `domain`, `statistics` | systemd-resolved DNS link scopes |
| `systemd-analyze` | `time`, `blame`, `critical-chain` | Boot performance and slow services |
| `systemctl` | `--failed`, `--user --failed`, `is-system-running`, `list-units` | Systemd service status |
| `journalctl`| `-p err -b -n 50 --no-pager`, `-k` (kernel ring buffer), `-xe` | Recent system and kernel error logs |
| `sensors` | `sensors`, `-u` (raw units) | Hardware temperatures and fan RPM |
| `acpi` | `-b` (battery), `-t` (thermal), `-V` (all), `-a` (AC power) | Battery charge and power adapter |
| `bluetoothctl` | `show`, `devices`, `list`, `paired-devices` | Bluetooth controller and paired devices |
| `pactl` | `info`, `list short sinks`, `list short sources`, `sink-inputs` | Sound server sinks and streams |
| `lsb_release` | `-a`, `-d`, `-r`, `-c` | Distribution and release version |
| `hostnamectl` | `status` | System identity and OS release |
| `networkctl` | `status`, `list` | systemd-networkd link states |
| `localectl` | `status` | System locale and keyboard keymap |
| `timedatectl` | `status`, `timesync-status`, `show` | System clock and NTP synchronization |
| `lspci` | `lspci`, `-k` (drivers), `-nn`, `-v` | PCI bus hardware and kernel drivers |
| `lsusb` | `lsusb`, `-t` (tree), `-v` | USB bus peripherals and devices |
| `lsmod` | `lsmod` | Loaded Linux kernel modules |
| `vmstat` | `vmstat`, `-s`, `1 2`, `1 5`, `-m`, `-d` | Memory, swap paging, and disk I/O |
| `iostat` | `iostat`, `-x` (extended), `-h`, `-xz 1 2`, `-c`, `-d` | Disk I/O throughput and wait times |
| `mpstat` | `mpstat`, `-P ALL`, `-P ALL 1 2`, `-u` | Per-core CPU utilization breakdown |
| `dpkg` | `--audit`, `-C`, `--print-architecture` | Audit unconfigured or broken packages |
| `apt` | `list --upgradable`, `list --installed` | Query package update availability |
| `apt-get` | `check`, `-s check` (simulate check) | Verify package dependency consistency |
| `flatpak` | `list`, `list --app`, `list --runtime` | Inspect Flatpak applications |
| `loginctl` | `list-sessions`, `list-sessions --no-legend`, `list-users` | Active user sessions and seats |
| `id` | `id`, `-u`, `-g`, `-un`, `-gn` | Effective user and group identity |
| `whoami` | `whoami` | Current user account name |
| `python3` | `--version` | Python interpreter version |
| `node` | `--version` | Node.js runtime version |
| `npm` | `--version` | Node Package Manager version |
| `git` | `--version` | Git version control tool version |
| `gcc` | `--version` | GNU C Compiler toolchain version |
| `ls` | `ls`, `-l`, `-a`, `-lh`, `-la` | Directory file listing |

---

## Safety Guarantees

LocalOps enforces defense-in-depth at every layer:

1. **Deny by Default:** Commands not in the table above are unconditionally rejected by the security validator.
2. **Zero Shell Execution:** Commands run via `argv` vectors with `shell=False`. Shell pipelines (`|`), command chaining (`&&`, `;`), and redirections (`>`, `<`) are strictly blocked.
3. **No Sudo:** Privilege escalation is disabled during automated diagnostics.
4. **Explicit Human Confirmation:** LocalOps presents the exact normalized commands and requires your explicit `[y/N]` confirmation before executing anything.
5. **100% Offline:** LocalOps functions with complete independence from cloud APIs.

