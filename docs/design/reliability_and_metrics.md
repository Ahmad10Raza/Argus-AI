# Reliability, Failure Strategy & Success Metrics

## 1. Success Metrics

We define success by these core KPIs:

- **MTTD (Mean Time To Detect)**: Time from issue start to alert generation.
- **MTTR (Mean Time To Recovery)**: Time from alert to issue resolution.
- **Auto-fix Success Rate**: `(Successful Auto-fixes / Total Recommended Fixes) * 100`
- **False Positive Rate**: Percentage of alerts that were incorrect.
- **Human Override Rate**: How often humans have to reject or revert an AI action.

## 2. Failure Strategy

Hardware and software fail; our AI system must fail safely.

### Scenario: AI Unavailable (LLM Down)

- **Action**: Fallback to rule-based detection only.
- **Impact**: No complex RCAs, only standard alerts. System remains functional but "dumber".

### Scenario: LLM Timeout

- **Action**: Retry once with exponential backoff. If it fails again, log error and skip analysis for that event.
- **Impact**: Delayed insights, but no crash.

### Scenario: Vector DB Down

- **Action**: Skip historical context retrieval.
- **Impact**: AI suggestions may be less context-aware but still valid based on current logs.

### Scenario: Action Execution Failure

- **Action**:
    1. Stop further execution immediately.
    2. Trigger PagerDuty/Alert for human intervention.
    3. Rollback if a rollback script is defined.
- **Impact**: Incident escalated to human; no further automated damage.

**Principle**: No single AI failure should break production or the observability pipeline itself.
