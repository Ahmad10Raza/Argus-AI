# Threat Model & Risk Assessment

Before implementation, we identify critical risks and their mitigations.

## 1. AI Hallucination

**Risk**: The LLM invents a fake root cause or suggests a dangerous, non-existent command.
**Impact**: Production outages, data loss, or confusion.

### Mitigations

- **Structured Output**: LLMs must output strict JSON. Free-form text is for logging only, not execution.
- **Tool-Based Execution**: The LLM cannot "write" code to run. It can only select from a predefined list of tools/scripts.
- **Confidence Thresholds**: Actions below a certain confidence score (e.g., 0.8) require human approval.

## 2. Infinite Remediation Loops

**Risk**: A fix causes a side effect that triggers another alert, leading to a fix loop.
**Impact**: Resource exhaustion, system instability.

### Mitigations

- **Rate Limiting**: Limit the number of actions per target (pod/server) per hour.
- **Cooldown Timers**: Enforced wait time between identical actions on the same target.
- **Incident Correlation ID**: Track chain of events; detect if "Action A" is repeatedly triggering "Alert B".
- **Max Retry Policy**: Stop after N failed attempts.

## 3. Privilege Escalation

**Risk**: The Action Service is compromised or tricked into doing more than it should.
**Impact**: Full system compromise.

### Mitigations

- **RBAC (Role-Based Access Control)**: Service account has minimum necessary permissions (principle of least privilege).
- **Namespace Isolation**: Run remediation jobs in isolated namespaces.
- **Read-Only by Default**: Filesystems should be read-only where possible.
- **No Cluster-Admin**: Never grant full cluster admin rights to the Action Service.

## 4. False Positives

**Risk**: The system detects an anomaly where there is none, triggering unnecessary fixes.
**Impact**: Service disruption, alert fatigue.

### Mitigations

- **Multi-signal Confirmation**: Require corroboration (e.g., Log Error + CPU Spike) before acting.
- **Human-in-the-Loop**: Start with "Recommendation Mode" only.
- **Confidence Scoring**: Explainable scores must accompany every recommendation.
