"""Automatic reviewer task creation for implementation PR handoffs."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from .hermes_imports import kanban_db

GITHUB_PR_RE = re.compile(r"https://github\.com/(?P<owner>[^\s/]+)/(?P<repo>[^\s/]+)/pull/(?P<number>\d+)")
TRAILING_PR_PUNCTUATION = ".,;:!?)>]}'\""
PR_METADATA_KEYS = ("pr_url", "github_pr_url", "pull_request_url")
PR_LIST_METADATA_KEYS = ("pr_urls", "github_pr_urls", "pull_request_urls")
REVIEW_STATUSES = "passed|changes_needed|unable_to_review"


@dataclass(frozen=True)
class PullRequest:
    url: str
    owner: str
    repo: str
    number: str

    @property
    def label(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"


def normalize_pr_url(value: str) -> Optional[str]:
    text = str(value or "").strip().rstrip(TRAILING_PR_PUNCTUATION)
    match = GITHUB_PR_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(TRAILING_PR_PUNCTUATION)


def parse_pr_url(value: str) -> Optional[PullRequest]:
    url = normalize_pr_url(value)
    if not url:
        return None
    match = GITHUB_PR_RE.match(url)
    if not match:
        return None
    return PullRequest(url=url, owner=match.group("owner"), repo=match.group("repo"), number=match.group("number"))


def _append_pr_urls(found: list[str], text: Any) -> None:
    if text is None:
        return
    for match in GITHUB_PR_RE.finditer(str(text)):
        normalized = normalize_pr_url(match.group(0))
        if normalized and normalized not in found:
            found.append(normalized)


def _metadata_pr_urls(metadata: Any) -> list[str]:
    found: list[str] = []
    if not isinstance(metadata, dict):
        return found
    for key in PR_METADATA_KEYS:
        _append_pr_urls(found, metadata.get(key))
    for key in PR_LIST_METADATA_KEYS:
        values = metadata.get(key)
        if isinstance(values, (list, tuple, set)):
            for value in values:
                _append_pr_urls(found, value)
        else:
            _append_pr_urls(found, values)
    return found


def _run_metadata(run: Any) -> Any:
    metadata = getattr(run, "metadata", None)
    if isinstance(metadata, str):
        try:
            return json.loads(metadata)
        except json.JSONDecodeError:
            return None
    return metadata


def extract_pr_urls(
    task: Any,
    runs: Iterable[Any] = (),
    comments: Iterable[Any] = (),
    *,
    extra_summary: Any = None,
    extra_result: Any = None,
    extra_metadata: Any = None,
) -> list[str]:
    """Extract full GitHub PR URLs from handoff payload, task, runs, and comments."""
    found: list[str] = []
    for url in _metadata_pr_urls(extra_metadata):
        if url not in found:
            found.append(url)
    _append_pr_urls(found, extra_summary)
    _append_pr_urls(found, extra_result)
    _append_pr_urls(found, getattr(task, "body", None))
    _append_pr_urls(found, getattr(task, "result", None))
    for run in runs:
        for url in _metadata_pr_urls(_run_metadata(run)):
            if url not in found:
                found.append(url)
        _append_pr_urls(found, getattr(run, "summary", None))
        _append_pr_urls(found, getattr(run, "result", None))
        _append_pr_urls(found, getattr(run, "error", None))
    for comment in comments:
        _append_pr_urls(found, getattr(comment, "body", None))
    return found


def is_implementation_completion(task: Any) -> bool:
    """Return true for source implementation tasks that should spawn review work."""
    assignee = str(getattr(task, "assignee", "") or "").strip().lower()
    title = str(getattr(task, "title", "") or "").strip().lower()
    step_key = str(getattr(task, "current_step_key", "") or "").strip().lower()
    if assignee == "reviewer" or step_key == "review":
        return False
    if title.startswith(("review ", "review:", "reviewer ", "reviewer:")):
        return False
    return True


def _review_task_body(source_task_id: str, pr: PullRequest) -> str:
    return f"""Automatic PR review task for source task {source_task_id}.

PR URL: {pr.url}
Repository/PR: {pr.label}

Hard requirements for the reviewer:
0. Before local review work, verify GitHub auth and PR access from this spawned reviewer profile/runtime, not from the maintainer/default shell:
   - Run `gh auth status` and `gh pr view {pr.url} --json url,number,headRefName,baseRefName` (or the repo-owned `./scripts/hermes-kanban github-auth-preflight` helper) before reading the diff/tests.
   - If preflight fails, do not spend time on local review. Immediately block, or complete with metadata.review_status = `unable_to_review`, and include the exact remediation: configure GitHub auth in this reviewer profile with `gh auth login` then `gh auth setup-git`, or provide `GH_TOKEN`/`GITHUB_TOKEN` in the reviewer profile/runtime environment before dispatching reviewer tasks. Use the gh CLI/profile credential path only.
   - The blocker message should include `GitHub PR review posting is blocked` so the maintainer can distinguish reviewer-profile auth mismatch from a code review finding.
1. Read the PR body, changed diff, and relevant CI/check results before deciding.
2. Run or verify local tests where relevant; record exact commands in Kanban metadata.tests_run.
3. Post the review result on GitHub, not only in Kanban. Use a GitHub PR review when possible.
4. Clean result must include `LGTM`. Approve the PR if GitHub permits it.
5. If GitHub disallows self-approval or API approval, treat that as non-fatal: post a clear LGTM GitHub comment explaining the self-approval restriction and include that comment URL in Kanban.
6. If findings exist, include concrete file/line/reason/suggested fix where possible.
7. Complete this Kanban task with machine-readable metadata using this schema:
   - review_status: {REVIEW_STATUSES}
   - pr_url: {pr.url}
   - github_review_url or github_comment_url: URL proving the GitHub-visible result was posted
   - findings: array of objects like {{file, line, severity, reason, suggested_fix}}
   - tests_run: array of exact commands/checks performed

Kanban completion examples:
- Passed: summary includes `LGTM`, metadata.review_status = `passed`, metadata.github_review_url or metadata.github_comment_url is set.
- Changes needed: metadata.review_status = `changes_needed` and findings lists blockers.
- Unable to review: metadata.review_status = `unable_to_review` and summary explains the credential/environment blocker.
"""


def _task_id_for_idempotency(conn, key: str) -> Optional[str]:
    row = conn.execute(
        "SELECT id FROM tasks WHERE idempotency_key = ? AND status != 'archived' ORDER BY created_at DESC LIMIT 1",
        (key,),
    ).fetchone()
    return str(row["id"]) if row else None


def ensure_pr_review_task(conn, source_task_id: str, pr_url: str, *, board: Optional[str] = None) -> dict[str, Any]:
    """Create or reuse the idempotent reviewer child task for a source PR."""
    source = kanban_db.get_task(conn, source_task_id)
    if source is None:
        raise ValueError(f"source task {source_task_id} not found")
    pr = parse_pr_url(pr_url)
    if pr is None:
        raise ValueError(f"not a supported GitHub PR URL: {pr_url!r}")
    idem = f"auto-pr-review:{source_task_id}:{pr.url}"
    existing_id = _task_id_for_idempotency(conn, idem)
    if existing_id:
        return {"task_id": existing_id, "pr_url": pr.url, "created": False, "board": board}

    workspace_kind = "scratch"
    workspace_path = None
    if getattr(source, "workspace_kind", None) == "dir" and getattr(source, "workspace_path", None):
        workspace_kind = "dir"
        workspace_path = source.workspace_path

    task_id = kanban_db.create_task(
        conn,
        title=f"Review PR for {source_task_id}: {pr.label}",
        body=_review_task_body(source_task_id, pr),
        assignee="reviewer",
        created_by="kanban-webui:auto-pr-review",
        workspace_kind=workspace_kind,
        workspace_path=workspace_path,
        tenant=getattr(source, "tenant", None),
        priority=getattr(source, "priority", 0) or 0,
        parents=[source_task_id],
        idempotency_key=idem,
        skills=["github-code-review", "systematic-debugging"],
    )
    return {"task_id": task_id, "pr_url": pr.url, "created": True, "board": board}


def validate_review_completion_payload(task: Any, *, summary: Any = None, result: Any = None, metadata: Any = None) -> None:
    """Validate auto-created review task completion evidence before marking done."""
    idempotency_key = str(getattr(task, "idempotency_key", "") or "")
    if not idempotency_key.startswith("auto-pr-review:"):
        return
    if not isinstance(metadata, dict):
        raise ValueError("auto PR review completion requires metadata with review_status, pr_url, and GitHub evidence")
    review_status = str(metadata.get("review_status") or "").strip()
    allowed = {"passed", "changes_needed", "unable_to_review"}
    if review_status not in allowed:
        raise ValueError("auto PR review metadata.review_status must be one of passed, changes_needed, unable_to_review")
    if not normalize_pr_url(str(metadata.get("pr_url") or "")):
        raise ValueError("auto PR review metadata.pr_url must contain the reviewed GitHub PR URL")
    if review_status in {"passed", "changes_needed"}:
        if not (metadata.get("github_review_url") or metadata.get("github_comment_url")):
            raise ValueError("auto PR review metadata must include github_review_url or github_comment_url")
    if review_status == "passed" and "LGTM" not in f"{summary or ''}\n{result or ''}":
        raise ValueError("passed auto PR review completion summary or result must include LGTM")
    if review_status == "changes_needed" and not isinstance(metadata.get("findings"), list):
        raise ValueError("changes_needed auto PR review completion requires metadata.findings as a list")


def reconcile_pr_review_tasks(
    conn,
    task_ids: Optional[Iterable[str]] = None,
    *,
    board: Optional[str] = None,
    extra_summary: Any = None,
    extra_result: Any = None,
    extra_metadata: Any = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Ensure reviewer tasks exist for completed implementation tasks with PR URLs."""
    if task_ids is None:
        tasks = kanban_db.list_tasks(conn, status="done", limit=limit)
    else:
        tasks = [task for task_id in task_ids if (task := kanban_db.get_task(conn, task_id)) is not None]
    results: list[dict[str, Any]] = []
    for task in tasks:
        if task.status != "done" or not is_implementation_completion(task):
            continue
        runs = kanban_db.list_runs(conn, task.id)
        comments = kanban_db.list_comments(conn, task.id)
        urls = extract_pr_urls(
            task,
            runs,
            comments,
            extra_summary=extra_summary,
            extra_result=extra_result,
            extra_metadata=extra_metadata,
        )
        for url in urls:
            results.append(ensure_pr_review_task(conn, task.id, url, board=board))
    return results
