# LocalOps Linux

Local-first AI troubleshooting and system operations agent for Linux.

LocalOps runs an offline SLM through Ollama and provides a controlled
interface for diagnosing and managing a Linux system.

## Goals

- Offline AI operation
- Linux troubleshooting
- Command planning
- Command explanations
- Individual command approval
- Safe command execution
- Before/after system state comparison
- Local command knowledge base
- Human-in-the-loop execution

## Architecture

User
  ↓
LocalOps CLI
  ↓
Local SLM (Qwen)
  ↓
Command Planner
  ↓
Command Knowledge Base
  ↓
Safety Validator
  ↓
User Approval
  ↓
Command Executor
  ↓
Result + Before/After Report

## Status

Early development.

## Model

Qwen3 1.7B via Ollama.
