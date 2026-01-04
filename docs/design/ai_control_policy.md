# AI Control Strategy & Policy

This policy governs how Artificial Intelligence (LLMs) interacts with the production environment.

## 1. LLM Roles

| Role | Allowed? | Description |
| :--- | :--- | :--- |
| **Summarizer** | ✅ YES | Summarizing long logs or error traces. |
| **Classifier** | ✅ YES | Categorizing incidents (e.g., "Database", "Network", "App Application"). |
| **Recommender** | ✅ YES | Suggesting a course of action from a whitelist. |
| **Executor** | ❌ NO | DIRECTLY executing code or commands. |
| **Decision Finalizer** | ❌ NO | Having the final say on high-risk actions without checks. |

**Golden Rule**: LLMs suggest; Systems (and Humans) decide.

## 2. Prompt Engineering Rules

All prompts sent to the Intelligence Service must adhere to these rules:

1. **System Context**: Always include the current environment (Dev/Stage/Prod) and constraints.
2. **Structured Output**: Always request JSON or a specific schema. Never parse natural language for control logic.
3. **Confidence Score**: explicit `confidence` field (0.0 - 1.0) is required in the response.
4. **Rationale**: The LLM must generate a `reasoning` field explaining *why* it chose a recommendation.

### Example Constraint in Prompt
>
> "You must NOT generate shell commands or code. You may only select an action_id from the provided list of available tools. If no tool fits, return action_id: 'manual_intervention'."

## 3. Environment Progression

Autonomy is granted in stages:

1. **Level 0 (Local/Dev)**: Observation only.
2. **Level 1 (Staging)**: Observation + Recommendation.
3. **Level 2 (Prod - Initial)**: Recommendation + Human Approval (Click-to-fix).
4. **Level 3 (Prod - Mature)**: Auto-fix for Low-Risk items (e.g., clear temp space, restart stateless pod). High risk always requires approval.
5. **Level 4 (Prod - Advanced)**: Policy-controlled Auto-fix.

**Current Target**: Level 2 (Prod - Initial).
