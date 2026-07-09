"""Approval policy + risk analyzer.

Risk analyzer scores each (tool, args) tuple. High-risk calls require human approval.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class RiskAssessment:
    score: int            # 0-100
    level: str            # "low" | "medium" | "high" | "critical"
    reasons: list[str]


class RiskAnalyzer:
    """Score tool calls for risk. Used by ApprovalPolicy."""

    CRITICAL_PATTERNS = [
        (r"rm\s+-rf\s+/(?!tmp)", "recursive root delete"),
        (r"rm\s+-rf\s+~", "recursive home delete"),
        (r"mkfs", "filesystem format"),
        (r"dd\s+.*of=/dev/[sh]d", "raw disk write"),
        (r"shutdown|reboot", "system shutdown/reboot"),
        (r":\(\)\s*\{\s*:\|:&\s*\};", "fork bomb"),
    ]
    HIGH_PATTERNS = [
        (r"curl.*\|\s*(sh|bash)", "pipe to shell"),
        (r"wget.*\|\s*(sh|bash)", "pipe to shell"),
        (r"git\s+push\s+--force", "force push"),
        (r"npm\s+publish", "npm publish"),
        (r"pip\s+install\s+--user", "user-level pip install"),
    ]
    MEDIUM_PATTERNS = [
        (r"rm\s+-rf", "recursive delete"),
        (r"git\s+reset\s+--hard", "hard git reset"),
        (r"chmod\s+\+x", "make executable"),
        (r"sudo\s", "sudo"),
    ]

    def assess(self, tool_name: str, args: dict[str, Any]) -> RiskAssessment:
        score = 0
        reasons: list[str] = []

        # Read-only tools are always low risk
        READ_ONLY = {"file_read", "file_list", "file_search", "web_fetch", "web_search",
                     "skill_list", "skill_read", "memory_read",
                     "phone_battery", "phone_sensor", "phone_location",
                     "phone_clipboard_get", "phone_app_list", "phone_app_current",
                     "phone_ui_screenshot", "phone_ui_dump", "phone_screen_state",
                     "phone_sms_read"}
        if tool_name in READ_ONLY:
            return RiskAssessment(score=0, level="low", reasons=["read-only tool"])

        # Check the full arg dump against patterns
        arg_blob = " ".join(str(v) for v in args.values())

        for pat, label in self.CRITICAL_PATTERNS:
            if re.search(pat, arg_blob):
                score = 100
                reasons.append(f"critical: {label}")
                break

        if score < 100:
            for pat, label in self.HIGH_PATTERNS:
                if re.search(pat, arg_blob):
                    score = max(score, 75)
                    reasons.append(f"high: {label}")

        if score < 75:
            for pat, label in self.MEDIUM_PATTERNS:
                if re.search(pat, arg_blob):
                    score = max(score, 50)
                    reasons.append(f"medium: {label}")

        # Phone-specific risk
        if tool_name in ("phone_sms_send", "phone_call"):
            score = max(score, 80)
            reasons.append("phone communication (costs money / disturbs contacts)")
        if tool_name in ("phone_notification",):
            score = max(score, 30)
            reasons.append("posts visible notification")
        if tool_name in ("phone_app_stop",):
            score = max(score, 40)
            reasons.append("force-stops an app")

        # Writes to filesystem
        if tool_name in ("file_write", "file_edit"):
            score = max(score, 30)
            reasons.append("modifies filesystem")

        if not reasons:
            reasons.append("no specific risk pattern matched")

        level = "low"
        if score >= 100: level = "critical"
        elif score >= 75: level = "high"
        elif score >= 40: level = "medium"

        return RiskAssessment(score=score, level=level, reasons=reasons)


class ApprovalPolicy:
    """Decides whether a tool call needs human approval."""

    def __init__(self, config):
        self.config = config
        self.analyzer = RiskAnalyzer()

    def needs_approval(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, RiskAssessment]:
        assessment = self.analyzer.assess(tool_name, args)
        # Auto-approve read-only if config allows
        if assessment.level == "low" and self.config.auto_approve_reads:
            return False, assessment
        # Auto-approve medium+ only if auto_approve_writes is True
        if assessment.level in ("medium",) and self.config.auto_approve_writes:
            return False, assessment
        # High and critical always require approval
        return assessment.level in ("high", "critical"), assessment
