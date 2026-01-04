# System Boundaries & Responsibilities

This document defines the hard boundaries between services in the AIOps platform. These rules are **non-negotiable** to ensure security and stability.

## 1. Ingestion Service

**Role**: The gateway for all raw data. It normalizes logs and metrics into structured events.

### ✅ Allowed

- **Receive logs**: Accept raw logs via HTTP/gRPC.
- **Receive metrics**: Accept telemetry data.
- **Normalize data**: Convert diverse formats into the standard `IncidentEvent` schema.
- **Publish events**: Push normalized events to the message queue (e.g., Kafka).

### ❌ Forbidden

- **No AI logic**: Do not perform analysis or inference here.
- **No persistence decisions**: Do not decide what to store long-term; just pass it on.
- **No remediation logic**: Do not trigger any fixes.

---

## 2. Intelligence Service (The Brain)

**Role**: The analysis engine. It detects anomalies and recommends actions using AI/ML.

### ✅ Allowed

- **Analyze logs**: Process event streams to find patterns.
- **Call LLMs**: Use Large Language Models for reasoning and root cause analysis.
- **Recommend actions**: Produce structured `ActionRequest` events proposing a fix.

### ❌ Forbidden

- **No direct execution**: NEVER run a command or modify infrastructure directly.
- **No infra credentials**: Must not hold keys to production servers.
- **No shell access**: Cannot execute shell commands.

---

## 3. Action Service (The Hands)

**Role**: The execution engine. It safely runs approved remediation steps.

### ✅ Allowed

- **Execute approved actions**: Run predefined, sandboxed scripts or API calls.
- **Validate outcomes**: Check if the action fixed the issue.

### ❌ Forbidden

- **No LLM calls**: Do not make decisions or reason about "what to do".
- **No dynamic command generation**: Only execute from a whitelist of pre-approved scripts.
- **No unrestricted internet access**: Should operate within a secured network perimeter.

---

## 4. Audit Service (The Memory)

**Role**: The compliant record-keeper. It stores the history of what happened.

### ✅ Allowed

- **Store incidents**: Archive `IncidentEvent` data.
- **Store actions**: Archive `ActionRequest` and `ActionResult` data.
- **Provide historical context**: allow semantic search for past similar incidents.

### ❌ Forbidden

- **No decision making**: Do not trigger alerts or fixes.
- **No execution**: Purely a storage and retrieval system.
