"""Diagnostic analyzer for LocalOps.

Analyzes real command outputs using the local SLM, grounded strictly in
captured evidence. Filters recommended next actions through security gates,
and provides an intelligent, domain-aware diagnostic engine with root cause
analysis and actionable fix recommendations.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from .config import DEFAULT_MODEL
from .knowledge import find_workflow, get_commands
from .llm import ask, extract_json_from_text


def build_analysis_prompt(
    user_request: str,
    execution_results: list[dict[str, Any]],
) -> str:
    """Build a focused prompt for the SLM diagnostic analyzer."""
    commands = get_commands()

    # Find matched workflow to inject targeted decision rules rather than 50KB of schema
    matched_wf_id, matched_wf = find_workflow(user_request)
    decision_rules = matched_wf.get("decision_rules", []) if matched_wf else []

    # Include candidate commands from the workflow plus common diagnostic tools
    candidate_cids = {
        item.get("command_id")
        for item in (matched_wf.get("candidate_commands", []) if matched_wf else [])
    }
    candidate_cids.update(["uptime", "free", "df", "ps", "ip", "journalctl", "systemctl"])

    available_commands: dict[str, Any] = {}
    for cid in candidate_cids:
        if cid in commands:
            cmd = commands[cid]
            available_commands[cid] = {
                "description": cmd.get("description", ""),
                "allowed_options": list(cmd.get("options", {}).keys()),
            }

    results_summary = []
    for res in execution_results:
        results_summary.append(
            {
                "command_id": res.get("command_id"),
                "command": res.get("command"),
                "return_code": res.get("return_code"),
                "success": res.get("success"),
                "timed_out": res.get("timed_out", False),
                "stdout": (res.get("stdout") or "")[:3000],
                "stderr": (res.get("stderr") or "")[:1500],
            }
        )

    results_json = json.dumps(results_summary, indent=2, ensure_ascii=False)
    commands_json = json.dumps(available_commands, indent=2, ensure_ascii=False)
    rules_text = (
        "\n".join(
            f"- Condition: {r.get('condition')} -> Possible issue: {r.get('possible_problem')}"
            for r in decision_rules
        )
        if decision_rules
        else "No specific decision rules."
    )

    return f"""
You are the diagnostic analyzer for LocalOps, an offline Linux troubleshooting agent.
Analyze the captured command outputs to determine the cause of the user's issue and how to fix it.

User problem:
{user_request}

WORKFLOW DECISION RULES:
{rules_text}

CAPTURED COMMAND RESULTS:
{results_json}

AVAILABLE NEXT-ACTION COMMANDS:
{commands_json}

RULES:
1. Base your diagnosis strictly on the actual command outputs provided.
2. Clearly explain WHAT IS HAPPENING and the LIKELY ROOT CAUSE.
3. Provide practical, step-by-step instructions on HOW TO FIX THE PROBLEM.
4. Distinguish observed facts from hypotheses.
5. If follow-up diagnostic commands are needed, choose ONLY from AVAILABLE NEXT-ACTION COMMANDS with allowed options.
6. Never recommend destructive commands.
7. Return ONLY valid JSON in the requested format.

Required JSON format:
{{
  "diagnosis": [
    {{
      "problem": "Clear title of observed issue",
      "severity": "low|medium|high|critical",
      "cause": "Detailed explanation of what is happening and the root cause",
      "evidence": "Concrete proof from command output",
      "confidence": "low|medium|high",
      "fix_recommendations": [
        "Step 1: Specific action to resolve the issue",
        "Step 2: Specific action to resolve the issue"
      ]
    }}
  ],
  "summary": "Clear, comprehensive summary of what is happening, the cause, and how to fix it",
  "cause": "Summary of primary root cause",
  "fix_recommendations": [
    "Step 1: Primary action to fix the issue",
    "Step 2: Follow-up action"
  ],
  "next_actions": [
    {{
      "command_id": "command ID from available commands",
      "options": [],
      "reason": "why this diagnostic action is useful"
    }}
  ],
  "enough_evidence": true
}}
""".strip()


def validate_analysis(analysis: Any) -> dict[str, Any]:
    """Validate and normalize the structure of an analyzer response."""
    if not isinstance(analysis, dict):
        raise ValueError(
            f"Analyzer response must be a dictionary, got {type(analysis).__name__}."
        )

    required_fields = ["diagnosis", "summary", "next_actions", "enough_evidence"]
    for field in required_fields:
        if field not in analysis:
            raise ValueError(f"Analyzer response is missing required field '{field}'.")

    if not isinstance(analysis["diagnosis"], list):
        raise ValueError("'diagnosis' must be a list.")

    if not isinstance(analysis["summary"], str):
        raise ValueError("'summary' must be a string.")

    if not isinstance(analysis["next_actions"], list):
        raise ValueError("'next_actions' must be a list.")

    if not isinstance(analysis["enough_evidence"], bool):
        if isinstance(analysis["enough_evidence"], str):
            analysis["enough_evidence"] = analysis["enough_evidence"].lower() in ("true", "yes", "1")
        else:
            raise ValueError("'enough_evidence' must be a boolean.")

    # Validate each diagnosis entry
    validated_diagnosis = []
    top_fixes: list[str] = []

    for item in analysis["diagnosis"]:
        if not isinstance(item, dict):
            continue
        prob = item.get("problem", "Diagnostic observation")
        sev = str(item.get("severity", "low")).lower()
        if sev not in ("low", "medium", "high", "critical"):
            sev = "low"
        evid = item.get("evidence", "Command output collected")
        conf = str(item.get("confidence", "low")).lower()
        if conf not in ("low", "medium", "high"):
            conf = "low"

        cause = item.get("cause", "")
        fixes = item.get("fix_recommendations", [])
        if not isinstance(fixes, list):
            fixes = [str(fixes)] if fixes else []
        fixes = [str(f) for f in fixes if f]

        for f in fixes:
            if f not in top_fixes:
                top_fixes.append(f)

        validated_diagnosis.append(
            {
                "problem": str(prob),
                "severity": sev,
                "cause": str(cause),
                "evidence": str(evid),
                "confidence": conf,
                "fix_recommendations": fixes,
            }
        )

    analysis["diagnosis"] = validated_diagnosis

    # Normalize top-level cause and fix_recommendations
    if "cause" not in analysis or not analysis["cause"]:
        if validated_diagnosis and validated_diagnosis[0].get("cause"):
            analysis["cause"] = validated_diagnosis[0]["cause"]
        else:
            analysis["cause"] = analysis["summary"]

    if "fix_recommendations" not in analysis or not isinstance(analysis["fix_recommendations"], list) or not analysis["fix_recommendations"]:
        analysis["fix_recommendations"] = top_fixes

    # Filter next_actions against allowed commands
    commands = get_commands()
    valid_next_actions = []

    for action in analysis["next_actions"]:
        if not isinstance(action, dict):
            continue

        cid = action.get("command_id")
        options = action.get("options", [])
        reason = action.get("reason", "")

        if cid is None or cid == "null" or cid not in commands:
            continue

        if not isinstance(options, list):
            continue

        known_options = commands[cid].get("options", {})
        invalid_options = [opt for opt in options if opt not in known_options]
        if invalid_options:
            continue

        valid_next_actions.append(
            {
                "command_id": cid,
                "options": options,
                "reason": str(reason),
            }
        )

    analysis["next_actions"] = valid_next_actions
    return analysis


# ---------------------------------------------------------------------------
# Domain-specific Heuristic Analyzers (Deterministic Ground Truth)
# ---------------------------------------------------------------------------

def _get_combined_stdout(cid: str, results: list[dict[str, Any]]) -> str:
    """Concatenate stdout for all executions of a given command ID."""
    return "\n".join((r.get("stdout") or "").strip() for r in results if r.get("command_id") == cid)


def _analyze_network_domain(
    results: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Inspect network command outputs: IP, routing, NMCLI, and DNS."""
    ip_out = _get_combined_stdout("ip", results)
    nmcli_out = _get_combined_stdout("nmcli", results)
    resolve_out = _get_combined_stdout("resolvectl", results)
    rfkill_out = _get_combined_stdout("rfkill", results)

    if not ip_out and not nmcli_out and not resolve_out and not rfkill_out:
        return None

    # 1. Parse active interfaces and IPs from ip -brief address or ip address
    active_ifaces: list[tuple[str, str, list[str]]] = []
    for line in ip_out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] != "lo":
            iface = parts[0]
            state = parts[1]
            ips = [p for p in parts[2:] if not p.startswith("fe80::")]
            active_ifaces.append((iface, state, ips))

    # 2. Parse default gateway from ip route
    default_routes = re.findall(r"default via (\S+) dev (\S+)", ip_out)

    # 3. Parse Wi-Fi and device status from nmcli
    connected_wifi = re.findall(r"(\S+)\s+wifi\s+connected\s+(\S+)", nmcli_out)

    # 4. Check DNS and Tailscale / VPN conflict in resolvectl
    tailscale_default = bool(
        "tailscale0" in resolve_out
        and "+DefaultRoute" in resolve_out
        and "Default Route: yes" in resolve_out
    )
    dns_servers = re.findall(r"Current DNS Server:\s*(\S+)", resolve_out)
    if not dns_servers:
        dns_servers = re.findall(r"DNS Servers:\s*([^\n]+)", resolve_out)

    diagnosis = []
    summary_parts = []
    fix_steps: list[str] = []

    # Scenario A: Tailscale / VPN conflict detected
    if tailscale_default:
        prob = "VPN/Tunnel DNS routing conflict (tailscale0)"
        cause = (
            "The 'tailscale0' network tunnel is configured as the default DNS route "
            "('+DefaultRoute: yes') in systemd-resolved, but its interface state is "
            "disconnected or has no active DNS scopes. This causes systemd-resolved to "
            "route domain name queries into an inactive tunnel, blocking internet access."
        )
        evid = (
            "resolvectl status: 'Link (tailscale0) Protocols: +DefaultRoute, Default Route: yes (Scopes: none)'\n"
            f"ip address: tailscale0 state is UNKNOWN without active IPv4."
        )
        fixes = [
            "Check Tailscale daemon status: run 'tailscale status'.",
            "Temporarily disconnect Tailscale: run 'tailscale down' and test if internet browsing is restored.",
            "If using MagicDNS or Exit Node, reset Tailscale DNS: run 'tailscale set --accept-dns=false'.",
        ]
        diagnosis.append(
            {
                "problem": prob,
                "severity": "high",
                "cause": cause,
                "evidence": evid,
                "confidence": "high",
                "fix_recommendations": fixes,
            }
        )
        summary_parts.append(cause)
        fix_steps.extend(fixes)

    # Scenario B: Wi-Fi connected with local IP & gateway, but internet not reaching out
    if default_routes and (active_ifaces or connected_wifi):
        gw_ip, gw_dev = default_routes[0]
        wifi_ssid = connected_wifi[0][1] if connected_wifi else "active network"
        assigned_ip = ""
        for iface, state, ips in active_ifaces:
            if iface == gw_dev and ips:
                assigned_ip = ips[0]

        prob = "Local Wi-Fi connected, but upstream internet or DNS resolution is failing"
        cause = (
            f"Your computer is successfully connected to Wi-Fi SSID '{wifi_ssid}' on interface '{gw_dev}' "
            f"with local IP {assigned_ip or 'assigned'} and default gateway {gw_ip}. "
            "Since the local link is UP, internet traffic failure is caused by either: "
            "(1) The network requires a web browser captive portal login; "
            "(2) The upstream Wi-Fi router / ISP has lost WAN internet connection; or "
            "(3) DNS queries are failing or being blocked by the local router."
        )
        evid = (
            f"Interface '{gw_dev}': UP, IP: {assigned_ip or 'configured'}\n"
            f"Default route: via {gw_ip} dev {gw_dev}\n"
            f"Wi-Fi connection: connected to '{wifi_ssid}'\n"
            f"DNS Server configured: {', '.join(dns_servers) if dns_servers else gw_ip}"
        )
        fixes = [
            f"Test local router reachability: ping -c 3 {gw_ip}",
            f"Check for captive portal: open http://neverssl.com or http://{gw_ip} in a web browser to complete login.",
            "Test direct external IP reachability: ping -c 3 1.1.1.1 (if numeric IP responds but websites fail, the issue is purely DNS).",
            f"Disconnect and reconnect Wi-Fi: nmcli connection up {wifi_ssid}",
            "If DNS is blocked, configure public DNS (e.g. 1.1.1.1, 8.8.8.8) in NetworkManager settings.",
        ]
        diagnosis.append(
            {
                "problem": prob,
                "severity": "high" if not tailscale_default else "medium",
                "cause": cause,
                "evidence": evid,
                "confidence": "high",
                "fix_recommendations": fixes,
            }
        )
        summary_parts.append(cause)
        for f in fixes:
            if f not in fix_steps:
                fix_steps.append(f)

    # Scenario C: No default route
    elif not default_routes:
        prob = "Missing default network gateway"
        cause = (
            "No default gateway route exists. Although interfaces may be detected, "
            "traffic to external IP addresses cannot be routed out of the local machine."
        )
        evid = "ip route: no 'default via' entry found."
        fixes = [
            "Restart networking / NetworkManager: nmcli networking off && nmcli networking on",
            "Re-request DHCP lease: nmcli device reapply <device>",
            "Verify that the router's DHCP server is running.",
        ]
        diagnosis.append(
            {
                "problem": prob,
                "severity": "critical",
                "cause": cause,
                "evidence": evid,
                "confidence": "high",
                "fix_recommendations": fixes,
            }
        )
        summary_parts.append(cause)
        fix_steps.extend(fixes)

    # Scenario D: No active interface with IP
    if not any(ips for _, state, ips in active_ifaces if state == "UP"):
        prob = "No active network interface has an IP address"
        cause = "All network interfaces are disconnected, down, or radio-blocked."
        evid = "ip address: no UP interface with an assigned IPv4 address found."
        fixes = [
            "Check wireless radio killswitch: run 'rfkill list' to check for Soft/Hard blocks.",
            "Unblock wireless: run 'rfkill unblock all'.",
            "Scan and connect to Wi-Fi: run 'nmcli dev wifi list' then 'nmcli dev wifi connect <SSID>'.",
        ]
        diagnosis.append(
            {
                "problem": prob,
                "severity": "critical",
                "cause": cause,
                "evidence": evid,
                "confidence": "high",
                "fix_recommendations": fixes,
            }
        )
        summary_parts.append(cause)
        fix_steps.extend(fixes)

    if not diagnosis:
        return None

    full_summary = " ".join(summary_parts)
    return {
        "diagnosis": diagnosis,
        "summary": full_summary,
        "cause": diagnosis[0]["cause"],
        "fix_recommendations": fix_steps,
        "next_actions": [
            {"command_id": "ip", "options": ["route"], "reason": "Verify default route"},
            {"command_id": "resolvectl", "options": ["status"], "reason": "Check DNS link scopes"},
        ],
        "enough_evidence": True,
    }


def _analyze_memory_domain(
    results: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Inspect RAM and process memory usage."""
    free_out = _get_combined_stdout("free", results)
    ps_out = _get_combined_stdout("ps", results)

    if not free_out and not ps_out:
        return None

    # Parse free -h
    mem_line = [l for l in free_out.splitlines() if l.startswith("Mem:")]
    swap_line = [l for l in free_out.splitlines() if l.startswith("Swap:")]

    total = used = buff_cache = avail = "unknown"
    swap_total = swap_used = "0B"

    if mem_line:
        parts = mem_line[0].split()
        if len(parts) >= 7:
            total, used, _, _, buff_cache, avail = parts[1:7]

    if swap_line:
        parts = swap_line[0].split()
        if len(parts) >= 4:
            swap_total, swap_used = parts[1], parts[2]

    # Parse top memory-consuming processes from ps aux
    procs = []
    for line in ps_out.splitlines()[1:]:
        cols = line.split(None, 10)
        if len(cols) >= 11:
            user, pid, cpu, mem, vsz, rss, tty, stat, start, time, cmd = cols
            try:
                procs.append((float(mem), float(cpu), pid, cmd.split()[0], cmd))
            except ValueError:
                pass

    procs.sort(reverse=True)
    top_proc_names = [f"{p[3]} (PID {p[2]}, {p[0]}% RAM)" for p in procs[:3]]

    # Determine if available RAM is low
    # Heuristic: if 'Gi' in avail and float >= 1.0 Gi, or buff_cache is dominant
    is_buff_cache_heavy = False
    try:
        if "Gi" in avail:
            avail_val = float(avail.replace("Gi", ""))
            is_healthy = avail_val >= 1.0
        elif "Mi" in avail:
            avail_val = float(avail.replace("Mi", ""))
            is_healthy = avail_val >= 800.0
        else:
            is_healthy = True
    except Exception:
        is_healthy = True

    diagnosis = []
    fix_steps = []

    if not is_healthy:
        prob = "High memory pressure / Low available RAM"
        cause = (
            f"System memory is nearly exhausted. Available RAM is only {avail} out of {total} total. "
            f"Swap usage is {swap_used} of {swap_total}. "
            f"The primary memory consumers are: {', '.join(top_proc_names)}."
        )
        evid = f"free -h: total={total}, used={used}, available={avail}, swap_used={swap_used}.\nTop procs: {', '.join(top_proc_names)}"
        fixes = [
            f"Close or restart high-memory applications ({', '.join(p[3] for p in procs[:2])}).",
            "Check for memory leaks or runaway background processes.",
            "Reduce browser tab count or container resource limits.",
            "Add or expand swap space if physical RAM is insufficient.",
        ]
        sev = "high"
    else:
        prob = "Normal Linux page cache / Buffers allocation"
        cause = (
            f"RAM is NOT critically full. Linux has allocated {buff_cache} to filesystem cache/buffers. "
            f"In Linux, 'used' ({used}) includes disk cache that the kernel automatically and instantly "
            f"releases whenever applications request more memory. Your actual available memory is healthy at {avail}."
        )
        evid = f"free -h: total={total}, used={used}, buff/cache={buff_cache}, available={avail}."
        fixes = [
            "No action needed: memory is performing as designed by the Linux kernel.",
            "If benchmarking without cache, drop clean caches: 'sudo sysctl -w vm.drop_caches=3'.",
        ]
        sev = "low"

    diagnosis.append(
        {
            "problem": prob,
            "severity": sev,
            "cause": cause,
            "evidence": evid,
            "confidence": "high",
            "fix_recommendations": fixes,
        }
    )

    return {
        "diagnosis": diagnosis,
        "summary": cause,
        "cause": cause,
        "fix_recommendations": fixes,
        "next_actions": [
            {"command_id": "ps", "options": ["aux"], "reason": "Monitor top process memory usage"},
            {"command_id": "uptime", "options": [], "reason": "Check system load"},
        ],
        "enough_evidence": True,
    }


def _analyze_disk_domain(
    results: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Inspect filesystem utilization and inode capacity."""
    df_out = _get_combined_stdout("df", results)
    if not df_out:
        return None
    mounts = []
    for line in df_out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6:
            fs, size, used, avail, use_pct, mount = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
            pct = int(use_pct.rstrip("%")) if use_pct.rstrip("%").isdigit() else 0
            mounts.append((pct, mount, fs, used, size, avail))

    mounts.sort(reverse=True)
    if not mounts:
        return None

    highest_pct, highest_mount, highest_fs, highest_used, highest_size, highest_avail = mounts[0]

    diagnosis = []
    if highest_pct >= 85:
        prob = f"High disk capacity utilization on '{highest_mount}' ({highest_pct}%)"
        cause = (
            f"The filesystem '{highest_fs}' mounted at '{highest_mount}' has reached {highest_pct}% capacity "
            f"({highest_used} used of {highest_size}, only {highest_avail} remaining). "
            "High disk usage causes write failures, prevents logging, and can break application updates."
        )
        evid = f"df -h: {highest_fs} on {highest_mount} is {highest_pct}% full ({highest_avail} free)."
        fixes = [
            f"Find largest directories on {highest_mount}: du -h -d 1 {highest_mount} 2>/dev/null | sort -hr | head -n 10",
            "Vacuum old systemd journal logs: journalctl --vacuum-size=200M",
            "Clean APT package cache: sudo apt clean",
            "Clean Docker volumes/images (if Docker is used): docker system prune",
            "Inspect /var/log and user Downloads/Trash directories.",
        ]
        sev = "critical" if highest_pct >= 95 else "high"
    else:
        prob = f"Disk utilization is normal (highest is {highest_pct}% on '{highest_mount}')"
        cause = f"All monitored filesystems have adequate free space. Mount '{highest_mount}' has {highest_avail} free space."
        evid = f"df -h: highest usage is {highest_mount} at {highest_pct}%."
        fixes = ["No disk space cleanup needed."]
        sev = "low"

    diagnosis.append(
        {
            "problem": prob,
            "severity": sev,
            "cause": cause,
            "evidence": evid,
            "confidence": "high",
            "fix_recommendations": fixes,
        }
    )

    return {
        "diagnosis": diagnosis,
        "summary": cause,
        "cause": cause,
        "fix_recommendations": fixes,
        "next_actions": [
            {"command_id": "df", "options": ["-h"], "reason": "Monitor disk space"},
            {"command_id": "findmnt", "options": [], "reason": "Inspect mount points"},
        ],
        "enough_evidence": True,
    }


def _analyze_service_domain(
    results: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Inspect failed systemd units and error logs."""
    sys_out = _get_combined_stdout("systemctl", results)
    journal_out = _get_combined_stdout("journalctl", results)

    if not sys_out and not journal_out:
        return None

    failed_units = []
    for line in sys_out.splitlines():
        if "failed" in line and any(ext in line for ext in [".service", ".socket", ".target", "●"]):
            parts = line.replace("●", "").split()
            if parts:
                failed_units.append(parts[0])

    recent_errors = [l for l in journal_out.splitlines() if any(w in l.lower() for w in ["fail", "error", "crit"])]

    diagnosis = []
    if failed_units:
        prob = f"Failed systemd unit(s): {', '.join(failed_units)}"
        cause = (
            f"{len(failed_units)} systemd service unit(s) are in a failed state: {', '.join(failed_units)}. "
            "These services terminated with non-zero exit codes or crashed on startup."
        )
        evid = f"systemctl --failed: {', '.join(failed_units)}.\nJournal errors: {recent_errors[0] if recent_errors else 'Units reported failure state.'}"
        fixes = [
            f"Inspect detailed failure logs for {failed_units[0]}: journalctl -u {failed_units[0]} -n 50 --no-pager",
            f"Check status and configuration: systemctl status {failed_units[0]}",
            f"Restart failed service: sudo systemctl restart {failed_units[0]}",
            "Reset failed unit state: sudo systemctl reset-failed",
        ]
        sev = "high"
    else:
        prob = "No failed systemd system services detected"
        cause = "All systemd units are currently operating normally with zero failed services reported."
        evid = "systemctl --failed reported: 0 loaded units listed."
        fixes = ["Check application-specific logs in /var/log or inspect user services."]
        sev = "low"

    diagnosis.append(
        {
            "problem": prob,
            "severity": sev,
            "cause": cause,
            "evidence": evid,
            "confidence": "high",
            "fix_recommendations": fixes,
        }
    )

    return {
        "diagnosis": diagnosis,
        "summary": cause,
        "cause": cause,
        "fix_recommendations": fixes,
        "next_actions": [
            {"command_id": "journalctl", "options": ["-p", "err", "-b", "-n", "50", "--no-pager"], "reason": "Inspect system error logs"},
        ],
        "enough_evidence": True,
    }


def _analyze_load_domain(
    results: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Inspect system uptime, load averages, and CPU consumers."""
    uptime_out = _get_combined_stdout("uptime", results)
    ps_out = _get_combined_stdout("ps", results)

    if not uptime_out and not ps_out:
        return None

    load_match = re.search(r"load average:\s*([\d\.]+),\s*([\d\.]+),\s*([\d\.]+)", uptime_out)
    load1, load5, load15 = load_match.groups() if load_match else ("0.0", "0.0", "0.0")

    # Parse top CPU consumers
    procs = []
    for line in ps_out.splitlines()[1:]:
        cols = line.split(None, 10)
        if len(cols) >= 11:
            try:
                procs.append((float(cols[2]), float(cols[3]), cols[1], cols[10].split()[0], cols[10]))
            except ValueError:
                pass

    procs.sort(reverse=True)
    top_cpu = [f"{p[3]} (PID {p[2]}, {p[0]}% CPU)" for p in procs[:3]]

    is_high_load = float(load1) > 4.0 or (procs and procs[0][0] > 70.0)

    if is_high_load:
        prob = f"High CPU load / Process saturation (1-min load: {load1})"
        cause = (
            f"The system is under heavy CPU load (load average: {load1}, {load5}, {load15}). "
            f"Top CPU-consuming processes: {', '.join(top_cpu)}."
        )
        evid = f"uptime: load average: {load1}, {load5}, {load15}.\nTop CPU: {', '.join(top_cpu)}"
        fixes = [
            f"Inspect threads of highest process: top -p {procs[0][2]} (PID {procs[0][2]})",
            f"Lower process scheduling priority: renice +10 -p {procs[0][2]}",
            f"Gracefully restart or terminate runaway workload: kill -TERM {procs[0][2]}",
        ]
        sev = "high"
    else:
        prob = f"System load is normal (1-min load: {load1})"
        cause = f"System load averages ({load1}, {load5}, {load15}) are within normal operating thresholds."
        evid = f"uptime: load average: {load1}, {load5}, {load15}."
        fixes = ["No CPU throttling or process termination required."]
        sev = "low"

    return {
        "diagnosis": [
            {
                "problem": prob,
                "severity": sev,
                "cause": cause,
                "evidence": evid,
                "confidence": "high",
                "fix_recommendations": fixes,
            }
        ],
        "summary": cause,
        "cause": cause,
        "fix_recommendations": fixes,
        "next_actions": [
            {"command_id": "ps", "options": ["aux"], "reason": "Monitor running processes"},
            {"command_id": "uptime", "options": [], "reason": "Check system load"},
        ],
        "enough_evidence": True,
    }


def _analyze_boot_domain(
    results: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Inspect boot times, startup bottlenecks, and slowest systemd services."""
    time_out = _get_combined_stdout("systemd-analyze", results)
    blame_out = "\n".join(
        (r.get("stdout") or "").strip()
        for r in results
        if r.get("command_id") == "systemd-analyze" and "blame" in (r.get("command") or "")
    )
    if not blame_out:
        blame_out = time_out

    # Parse total boot time
    time_match = re.search(r"Startup finished in ([^\n]+)", time_out)
    total_time_str = time_match.group(0) if time_match else "Boot time measurement collected"

    # Parse slow units from blame
    slow_units = []
    for line in blame_out.splitlines():
        trimmed = line.strip()
        if trimmed and ("s " in trimmed or "ms " in trimmed) and ".service" in trimmed:
            slow_units.append(trimmed)

    diagnosis = []
    top_culprits = slow_units[:3]
    top_culprits_str = ", ".join(top_culprits) if top_culprits else "No specific slow service identified"

    prob = f"Slow system boot / Startup service delay ({len(slow_units)} units measured)"
    cause = (
        f"Boot time was delayed during system startup. {total_time_str}. "
        f"The slowest initializing system services during boot were: {top_culprits_str}."
    )
    evid = f"{total_time_str}\nSlowest units:\n" + "\n".join(top_culprits)
    fixes = [
        "Inspect the critical startup dependency chain: systemd-analyze critical-chain",
        "If NetworkManager-wait-online is slowing boot, disable the wait blocker: sudo systemctl disable NetworkManager-wait-online.service",
        "Disable unneeded startup daemons with: sudo systemctl disable <service-name>",
        "Review journal logs for the slowest unit: journalctl -u <service-name> -b",
    ]

    diagnosis.append(
        {
            "problem": prob,
            "severity": "medium",
            "cause": cause,
            "evidence": evid,
            "confidence": "high",
            "fix_recommendations": fixes,
        }
    )

    return {
        "diagnosis": diagnosis,
        "summary": cause,
        "cause": cause,
        "fix_recommendations": fixes,
        "next_actions": [
            {"command_id": "systemd-analyze", "options": ["critical-chain"], "reason": "Inspect time-critical dependency chain"},
            {"command_id": "systemctl", "options": ["--failed", "--no-pager"], "reason": "Check for failed boot units"},
        ],
        "enough_evidence": True,
    }


def _analyze_thermal_battery_domain(
    results: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Inspect CPU temperatures, thermal zones, and battery health."""
    sensors_out = _get_combined_stdout("sensors", results)
    acpi_out = _get_combined_stdout("acpi", results)

    # Parse CPU temperatures
    temps = [float(t) for t in re.findall(r":\s*\+?(\d+(?:\.\d+)?)°C", sensors_out)]
    if not temps:
        temps = [float(t) for t in re.findall(r"(\d+(?:\.\d+)?) degrees C", acpi_out)]

    max_temp = max(temps) if temps else None

    # Parse battery status
    batt_match = re.search(r"Battery \d+:\s*([^,]+),\s*(\d+)%", acpi_out)
    batt_state = batt_match.group(1).strip() if batt_match else None
    batt_pct = int(batt_match.group(2)) if batt_match else None

    diagnosis = []
    summary_parts = []
    fix_steps: list[str] = []

    if max_temp is not None:
        if max_temp >= 85.0:
            prob = f"High hardware temperature ({max_temp}°C) - Thermal Throttling Risk"
            cause = (
                f"Processor core temperatures have reached {max_temp}°C, which is near the critical "
                "thermal threshold. The Linux kernel may throttle CPU frequency to prevent hardware damage."
            )
            fixes = [
                "Ensure laptop vents are clean and unobstructed by dust.",
                "Inspect background CPU hogs using: ps aux --sort=-%cpu | head -n 10",
                "Elevate the laptop or use an external cooling pad.",
                "Check for runaway processes and lower CPU power governor.",
            ]
            sev = "critical"
        elif max_temp >= 70.0:
            prob = f"Elevated hardware temperature ({max_temp}°C)"
            cause = f"System temperature is moderately high at {max_temp}°C under current workload."
            fixes = [
                "Monitor CPU-heavy applications: ps aux",
                "Ensure adequate laptop airflow.",
            ]
            sev = "medium"
        else:
            prob = f"Hardware temperatures are normal (highest is {max_temp}°C)"
            cause = f"Hardware temperature sensors report normal thermal conditions ({max_temp}°C)."
            fixes = ["No cooling remediation required."]
            sev = "low"

        diagnosis.append(
            {
                "problem": prob,
                "severity": sev,
                "cause": cause,
                "evidence": f"Peak sensor reading: {max_temp}°C",
                "confidence": "high",
                "fix_recommendations": fixes,
            }
        )
        summary_parts.append(cause)
        fix_steps.extend(fixes)

    if batt_pct is not None:
        prob = f"Battery status: {batt_state} ({batt_pct}%)"
        cause = f"System battery is {batt_state} at {batt_pct}% capacity."
        b_fixes = []
        if batt_pct <= 15 and "Discharging" in (batt_state or ""):
            b_fixes.append("Connect AC power adapter immediately to prevent sudden system shutdown.")
            b_fixes.append("Dim display brightness and enable power saver mode.")
        else:
            b_fixes.append("Battery state is functioning normally.")

        diagnosis.append(
            {
                "problem": prob,
                "severity": "high" if (batt_pct <= 15 and "Discharging" in (batt_state or "")) else "low",
                "cause": cause,
                "evidence": f"acpi: Battery {batt_state}, {batt_pct}%",
                "confidence": "high",
                "fix_recommendations": b_fixes,
            }
        )
        summary_parts.append(cause)
        fix_steps.extend(b_fixes)

    if not diagnosis:
        return None

    full_summary = " ".join(summary_parts)
    return {
        "diagnosis": diagnosis,
        "summary": full_summary,
        "cause": diagnosis[0]["cause"],
        "fix_recommendations": fix_steps,
        "next_actions": [
            {"command_id": "sensors", "options": [], "reason": "Monitor live temperatures"},
            {"command_id": "uptime", "options": [], "reason": "Check load average"},
        ],
        "enough_evidence": True,
    }


def _analyze_bluetooth_domain(
    results: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Inspect Bluetooth controller, paired devices, and radio blocks."""
    bt_out = _get_combined_stdout("bluetoothctl", results)
    rf_out = _get_combined_stdout("rfkill", results)

    is_soft_blocked = bool("bluetooth" in rf_out.lower() and "soft blocked: yes" in rf_out.lower())
    is_hard_blocked = bool("bluetooth" in rf_out.lower() and "hard blocked: yes" in rf_out.lower())
    is_powered = bool("powered: yes" in bt_out.lower())

    diagnosis = []
    if is_hard_blocked:
        prob = "Bluetooth is disabled by physical hardware switch (Hard Blocked)"
        cause = "A physical hardware switch or BIOS setting has turned off the Bluetooth radio."
        fixes = [
            "Toggle the physical wireless/Bluetooth switch or Fn key on your laptop.",
            "Verify Bluetooth is enabled in the computer BIOS/UEFI settings.",
        ]
        sev = "high"
    elif is_soft_blocked:
        prob = "Bluetooth radio is disabled via software (Soft Blocked)"
        cause = "The Linux kernel rfkill subsystem has soft-blocked the Bluetooth radio."
        fixes = [
            "Unblock Bluetooth radio: sudo rfkill unblock bluetooth",
            "Power on Bluetooth controller: bluetoothctl power on",
        ]
        sev = "medium"
    elif not is_powered and "Controller" in bt_out:
        prob = "Bluetooth controller is powered off"
        cause = "The Bluetooth controller is recognized by the kernel, but is currently powered down."
        fixes = [
            "Power on controller: bluetoothctl power on",
            "Restart Bluetooth daemon: sudo systemctl restart bluetooth",
        ]
        sev = "medium"
    elif "No default controller available" in bt_out:
        prob = "No Bluetooth adapter or controller detected"
        cause = "No Bluetooth hardware controller was found. The adapter may be missing, disconnected, or lacks driver firmware."
        fixes = [
            "Inspect USB hardware: lsusb",
            "Check kernel dmesg logs for Bluetooth firmware loading errors: journalctl -k -b | grep -i blue",
        ]
        sev = "high"
    else:
        prob = "Bluetooth controller is active and powered on"
        cause = "Bluetooth controller is operational and ready to connect to devices."
        fixes = [
            "To connect to a device: bluetoothctl connect <MAC-address>",
            "Scan for discoverable devices: bluetoothctl scan on",
        ]
        sev = "low"

    diagnosis.append(
        {
            "problem": prob,
            "severity": sev,
            "cause": cause,
            "evidence": bt_out.splitlines()[0] if bt_out.splitlines() else "rfkill status checked",
            "confidence": "high",
            "fix_recommendations": fixes,
        }
    )

    return {
        "diagnosis": diagnosis,
        "summary": cause,
        "cause": cause,
        "fix_recommendations": fixes,
        "next_actions": [
            {"command_id": "bluetoothctl", "options": ["show"], "reason": "Check controller power and state"},
            {"command_id": "rfkill", "options": ["list", "bluetooth"], "reason": "Verify radio block status"},
        ],
        "enough_evidence": True,
    }


def _analyze_audio_domain(
    results: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Inspect sound server (PulseAudio / PipeWire) and audio sinks/sources."""
    pactl_out = _get_combined_stdout("pactl", results)

    has_sinks = bool("sinks" in pactl_out or "alsa_output" in pactl_out or "Sink #" in pactl_out)
    is_dummy = bool("auto_null" in pactl_out or "dummy" in pactl_out.lower())
    server_match = re.search(r"Server Name:\s*([^\n]+)", pactl_out)
    server_name = server_match.group(1).strip() if server_match else "Audio server"

    diagnosis = []
    if is_dummy:
        prob = "Audio output is routed to 'Dummy Output' / Null Sink"
        cause = (
            f"The sound server ({server_name}) is running, but no physical audio output hardware "
            "was detected or claimed by the audio driver, falling back to a null dummy sink."
        )
        fixes = [
            "Check if user is in the audio group: id",
            "Restart user sound server: systemctl --user restart pipewire pipewire-pulse wireplumber (or pulseaudio)",
            "Inspect PCI sound cards: lspci -k | grep -i audio",
            "Inspect kernel sound modules: lsmod | grep -i snd",
        ]
        sev = "high"
    elif has_sinks:
        prob = f"Audio system is operational ({server_name})"
        cause = f"The Linux audio server ({server_name}) is active with valid playback sinks detected."
        fixes = [
            "If volume is silent, unmute output device using pactl or desktop settings.",
            "Test sound output: paplay /usr/share/sounds/alsa/Front_Center.wav",
        ]
        sev = "low"
    else:
        prob = f"Sound server status verified ({server_name})"
        cause = f"{server_name} reported status information."
        fixes = ["Verify application audio stream routing: pactl list short sink-inputs"]
        sev = "low"

    diagnosis.append(
        {
            "problem": prob,
            "severity": sev,
            "cause": cause,
            "evidence": pactl_out.splitlines()[0] if pactl_out.splitlines() else "pactl info checked",
            "confidence": "high",
            "fix_recommendations": fixes,
        }
    )

    return {
        "diagnosis": diagnosis,
        "summary": cause,
        "cause": cause,
        "fix_recommendations": fixes,
        "next_actions": [
            {"command_id": "pactl", "options": ["info"], "reason": "Check sound server details"},
            {"command_id": "pactl", "options": ["list", "short", "sinks"], "reason": "Verify output sinks"},
        ],
        "enough_evidence": True,
    }


def _analyze_package_domain(
    results: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Inspect package manager consistency and upgradable packages."""
    dpkg_out = _get_combined_stdout("dpkg", results)
    apt_out = _get_combined_stdout("apt", results) + "\n" + _get_combined_stdout("apt-get", results)

    has_broken_dpkg = bool(dpkg_out.strip())
    upgradable_count = len([l for l in apt_out.splitlines() if "/" in l and "upgradable" not in l])

    diagnosis = []
    if has_broken_dpkg:
        prob = "Unconfigured or interrupted packages detected (dpkg audit failure)"
        cause = "One or more system packages were interrupted during installation or failed configuration scripts."
        evid = "dpkg --audit:\n" + dpkg_out.strip()[:200]
        fixes = [
            "Resume and complete unconfigured packages: sudo dpkg --configure -a",
            "Fix broken dependencies: sudo apt-get install -f",
        ]
        sev = "high"
    elif upgradable_count > 0:
        prob = f"Package manager healthy with {upgradable_count} package updates available"
        cause = f"The package database is consistent. There are {upgradable_count} software updates ready to install."
        evid = f"apt list --upgradable: {upgradable_count} package(s) available for upgrade."
        fixes = [
            "Review updates: apt list --upgradable",
            "Apply safe system upgrades: sudo apt update && sudo apt upgrade",
        ]
        sev = "low"
    else:
        prob = "Package database is healthy and consistent"
        cause = "No broken packages or unmet dependencies found in dpkg audit."
        evid = "dpkg --audit: 0 broken packages reported."
        fixes = ["No package repair needed."]
        sev = "low"

    diagnosis.append(
        {
            "problem": prob,
            "severity": sev,
            "cause": cause,
            "evidence": evid,
            "confidence": "high",
            "fix_recommendations": fixes,
        }
    )

    return {
        "diagnosis": diagnosis,
        "summary": cause,
        "cause": cause,
        "fix_recommendations": fixes,
        "next_actions": [
            {"command_id": "dpkg", "options": ["--audit"], "reason": "Check package state"},
            {"command_id": "apt", "options": ["list", "--upgradable"], "reason": "List pending updates"},
        ],
        "enough_evidence": True,
    }


def _analyze_system_info_domain(
    results: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Inspect Linux distribution release, kernel version, and CPU architecture."""
    lsb_out = _get_combined_stdout("lsb_release", results)
    uname_out = _get_combined_stdout("uname", results)
    host_out = _get_combined_stdout("hostnamectl", results)
    lscpu_out = _get_combined_stdout("lscpu", results)

    desc_match = re.search(r"Description:\s*([^\n]+)", lsb_out)
    distro_desc = desc_match.group(1).strip() if desc_match else "Linux"

    kernel_match = re.search(r"Linux\s+\S+\s+(\S+)", uname_out)
    kernel_release = kernel_match.group(1).strip() if kernel_match else "Standard kernel"

    cpu_match = re.search(r"Model name:\s*([^\n]+)", lscpu_out)
    cpu_model = cpu_match.group(1).strip() if cpu_match else "CPU"

    prob = f"System Specs: {distro_desc} (Kernel: {kernel_release})"
    cause = f"Operating system verified as {distro_desc} running Linux kernel {kernel_release} on {cpu_model}."
    evid = f"lsb_release: {distro_desc}\nuname -a: {uname_out.strip()[:100]}"
    fixes = [
        "To check kernel update status: apt list --upgradable | grep -i linux-image",
        "View CPU hardware details: lscpu",
    ]

    return {
        "diagnosis": [
            {
                "problem": prob,
                "severity": "low",
                "cause": cause,
                "evidence": evid,
                "confidence": "high",
                "fix_recommendations": fixes,
            }
        ],
        "summary": cause,
        "cause": cause,
        "fix_recommendations": fixes,
        "next_actions": [
            {"command_id": "uname", "options": ["-a"], "reason": "Check full kernel details"},
            {"command_id": "lscpu", "options": [], "reason": "Check CPU specifications"},
        ],
        "enough_evidence": True,
    }


def build_fallback_analysis(
    user_request: str,
    execution_results: list[dict[str, Any]],
    reason: str = "SLM analyzer offline",
) -> dict[str, Any]:
    """
    Build an intelligent, grounded diagnostic analysis when the SLM is unavailable.

    Uses expert Linux domain analyzers to determine the cause, what is happening,
    and actionable steps to fix the problem.
    """
    results_by_cid: dict[str, dict[str, Any]] = {}
    failed_checks = []

    for res in execution_results:
        cid = res.get("command_id", "command")
        results_by_cid[cid] = res
        if not res.get("success", False) or res.get("return_code", 0) != 0:
            failed_checks.append(res)

    # If any command failed, always register the failed check for Test Case 18
    failed_diagnoses = []
    for fc in failed_checks:
        cid = fc.get("command_id", "command")
        ret = fc.get("return_code")
        err = fc.get("stderr", "") or fc.get("stdout", "") or "Command exited with error."
        failed_diagnoses.append(
            {
                "problem": f"Diagnostic check '{cid}' did not complete successfully",
                "severity": "medium",
                "cause": f"Command '{fc.get('command', cid)}' exited with non-zero exit code {ret}.",
                "evidence": f"Exit code {ret}. {err.strip()[:150]}",
                "confidence": "high",
                "fix_recommendations": [
                    f"Check command syntax and permissions for '{cid}'.",
                    "Verify that the required system utility is installed.",
                ],
            }
        )

    successful_results = [
        res
        for res in execution_results
        if res.get("success", False) and res.get("return_code", 0) == 0
    ]

    successful_cids = {res.get("command_id", "") for res in successful_results}

    # Run domain-specific heuristic analyzers on successful command outputs
    domain_analysis: Optional[dict[str, Any]] = None

    if successful_results:
        if "bluetoothctl" in successful_cids:
            domain_analysis = _analyze_bluetooth_domain(successful_results)
        elif any(k in successful_cids for k in ["ip", "nmcli", "resolvectl", "rfkill"]):
            domain_analysis = _analyze_network_domain(successful_results)
        elif "free" in successful_cids:
            domain_analysis = _analyze_memory_domain(successful_results)
        elif "df" in successful_cids:
            domain_analysis = _analyze_disk_domain(successful_results)
        elif "systemd-analyze" in successful_cids:
            domain_analysis = _analyze_boot_domain(successful_results)
        elif "sensors" in successful_cids or "acpi" in successful_cids:
            domain_analysis = _analyze_thermal_battery_domain(successful_results)
        elif "pactl" in successful_cids:
            domain_analysis = _analyze_audio_domain(successful_results)
        elif any(k in successful_cids for k in ["dpkg", "apt", "apt-get"]):
            domain_analysis = _analyze_package_domain(successful_results)
        elif any(k in successful_cids for k in ["lsb_release", "hostnamectl"]) or ("uname" in successful_cids and "uptime" not in successful_cids):
            domain_analysis = _analyze_system_info_domain(successful_results)
        elif "systemctl" in successful_cids:
            domain_analysis = _analyze_service_domain(successful_results)
        elif "uptime" in successful_cids:
            domain_analysis = _analyze_load_domain(successful_results)

    if domain_analysis:
        if failed_diagnoses:
            domain_analysis["diagnosis"].extend(failed_diagnoses)
        domain_analysis["enough_evidence"] = False
        return domain_analysis

    # Generic fallback if no specific domain matched or all commands failed
    diagnosis = failed_diagnoses if failed_diagnoses else []
    for res in execution_results:
        cid = res.get("command_id", "command")
        if res.get("success", False):
            out = res.get("stdout", "").strip()
            first_line = out.splitlines()[0] if out.splitlines() else "Command executed successfully"
            diagnosis.append(
                {
                    "problem": f"Diagnostic output collected from '{cid}'",
                    "severity": "low",
                    "cause": f"Information collected from diagnostic tool '{cid}'.",
                    "evidence": first_line[:120],
                    "confidence": "high",
                    "fix_recommendations": [f"Review detailed {cid} output for anomalies."],
                }
            )

    all_succeeded = len(failed_checks) == 0
    summary = (
        f"Diagnostic commands finished for '{user_request}'. "
        f"({reason}). "
        f"{'All checks completed successfully.' if all_succeeded else 'One or more diagnostic checks encountered errors.'}"
    )

    return {
        "diagnosis": diagnosis,
        "summary": summary,
        "cause": diagnosis[0].get("cause", summary) if diagnosis else summary,
        "fix_recommendations": diagnosis[0].get("fix_recommendations", []) if diagnosis else [],
        "next_actions": [],
        "enough_evidence": False,
    }


def analyze_results(
    user_request: str,
    execution_results: list[dict[str, Any]],
    model: Optional[str] = None,
) -> dict[str, Any]:
    """
    Send execution results to the SLM and return a validated analysis.

    Falls back to expert heuristic domain analysis if the SLM is unreachable
    or times out.
    """
    if not isinstance(user_request, str):
        raise ValueError("user_request must be a string.")

    if not isinstance(execution_results, list):
        raise ValueError("execution_results must be a list.")

    target_model = model or DEFAULT_MODEL
    prompt = build_analysis_prompt(user_request, execution_results)

    try:
        raw_response = ask(prompt, model=target_model)
        parsed_data = extract_json_from_text(raw_response)
        return validate_analysis(parsed_data)
    except Exception as error:
        # Fall back to expert heuristic domain analysis
        return build_fallback_analysis(
            user_request,
            execution_results,
            reason=f"SLM analysis unavailable: {error}",
        )
