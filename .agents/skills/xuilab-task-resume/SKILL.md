---
name: xuilab-task-resume
description: Resume an authorized XUILab task or interrupted Unity build/test from persistent records without duplicating an uncertain dispatch. Also route frozen-candidate handoff and acceptance for XUILab.
---

Read the current request and [project cursor](../../../Docs/PM/PROJECT_STATUS.md), then its linked Task Status and Brief. Old chat summaries do not establish candidate identity or completion.

For an interrupted Unity build/test, follow [operation journal](../../../Docs/Agents/UNITY_OPERATION_JOURNAL.md), run its read-only inspect command on the recorded operation ID, and use the returned recovery action. Actual editor work follows [Unity preflight](../../../Docs/Agents/UNITY_MCP_PLAYBOOK.md).

For handoff/acceptance, use [PM contract](../../../Docs/Agents/PM_CONTRACT.md) and [acceptance mapping](../../../Docs/MVP/ACCEPTANCE_MAP.md); compare the frozen candidate and required criteria with actual linked evidence. Run the [offline entry](../../../Tools/check_offline.py) and report its coverage limits.

The request controls authorization. These routes do not authorize a queued milestone, new attempt, commit, or release. Keep procedure and status in the linked Docs/Tools; do not copy them into this skill.
