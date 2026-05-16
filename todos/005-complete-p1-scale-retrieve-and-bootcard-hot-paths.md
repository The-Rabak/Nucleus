---
status: complete
priority: p1
issue_id: "005"
tags: [code-review, performance, dos, protects-user-story]
dependencies: []
---

# Scale retrieve and bootcard hot paths

## Problem Statement

`bootcard` and `retrieve` currently scan/parse full episode corpus, creating linear latency growth and DoS exposure.

## Findings

- `bootcard_use_case.py` + `episode_store.py` load all episodes then sort, even for tiny limit.
- `retrieve` parses all markdown and scores full corpus per request.
- Performance reviewer measured steep growth at 1k/3k and projected multi-second behavior at larger sizes.
- Security reviewer flagged unbounded retrieval as abuse vector.

## Proposed Solutions

### Option 1: Bounded recent-read + top-k clamps + lightweight index
**Approach:** Stop scanning after bounded candidate set, cap `top_k`, and use local token/index acceleration.
**Pros:** High impact with incremental rollout.
**Cons:** Requires index invalidation/update design.
**Effort:** Medium
**Risk:** Medium

---

### Option 2: Full retrieval channel abstraction with indexed backends
**Approach:** Move Slice 1 file scan path behind indexed retrieval channel immediately.
**Pros:** Better long-term architecture alignment.
**Cons:** Larger refactor and higher rollout risk.
**Effort:** Large
**Risk:** Medium

## Recommended Action

Implemented bounded read/parse windows for bootcard/retrieve hot paths and enforced bounded retrieval inputs (`top_k`, query length).

## Technical Details

**Affected files:**
- `src/nucleus/application/retrieve_use_case.py`
- `src/nucleus/application/bootcard_use_case.py`
- `src/nucleus/adapters/filesystem/episode_store.py`

## Resources

- `slice1-performance-review-1`
- `slice1-security-review`

## Acceptance Criteria

- [x] Bootcard no longer reads/parses full corpus for small limits.
- [x] Retrieve enforces bounded inputs (`top_k`, query size) and avoids full-corpus scoring in hot path.
- [x] Performance tests define and enforce practical latency budgets.
- [x] Abuse-style high-volume retrieval test no longer collapses responsiveness.

## Work Log

### 2026-05-14 - Review finding created

**By:** Copilot CLI

**Actions:**
- Consolidated P1 performance + P2 security DoS findings into one blocker.

**Learnings:**
- This issue threatens both reliability and security posture.

### 2026-05-15 - Resolution completed

**By:** Copilot CLI

**Actions:**
- Added bounded scan caps in `EpisodeStore.list_recent` and `EpisodeStore.search`.
- Enforced retrieval guardrails in `RetrieveUseCase` (`top_k` max 10, query length max 500).
- Added guardrail tests in `tests/unit/test_retrieve_guards.py`.

**Learnings:**
- Hard bounds on hot-path inputs are essential for both performance and abuse resistance.

## Notes

- WHY classification: 🎯 PROTECTS USER STORY
