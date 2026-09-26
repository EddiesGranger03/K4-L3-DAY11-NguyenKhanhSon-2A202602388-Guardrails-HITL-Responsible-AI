"""
Lab 11 — Optional enrichment: Human-in-the-Loop Design
  (Không chấm — tham khảo. Tóm tắt nộp do scripts/grade.py tự sinh,
   không viết report/*.md tay.)
  - Confidence Router
  - 3 HITL decision points
"""
from dataclasses import dataclass
import math


# ============================================================
# Optional enrichment: ConfidenceRouter (không chấm)
#
# Route agent responses based on confidence scores:
#   - HIGH (>= 0.9): Auto-send to user
#   - MEDIUM (0.7 - 0.9): Queue for human review
#   - LOW (< 0.7): Escalate to human immediately
#
# Special case: if the action is HIGH_RISK (e.g., money transfer,
# account deletion), ALWAYS escalate regardless of confidence.
#
# Implement the route() method.
# ============================================================

HIGH_RISK_ACTIONS = [
    "transfer_money",
    "close_account",
    "change_password",
    "delete_data",
    "update_personal_info",
]


@dataclass
class RoutingDecision:
    """Result of the confidence router."""
    action: str          # "auto_send", "queue_review", "escalate"
    confidence: float
    reason: str
    priority: str        # "low", "normal", "high"
    requires_human: bool


class ConfidenceRouter:
    """Route agent responses based on confidence and risk level.

    Thresholds:
        HIGH:   confidence >= 0.9 -> auto-send
        MEDIUM: 0.7 <= confidence < 0.9 -> queue for review
        LOW:    confidence < 0.7 -> escalate to human

    High-risk actions always escalate regardless of confidence.
    """

    HIGH_THRESHOLD = 0.9
    MEDIUM_THRESHOLD = 0.7

    def route(self, response: str, confidence: float,
              action_type: str = "general") -> RoutingDecision:
        """Route a response based on confidence score and action type.

        Args:
            response: The agent's response text
            confidence: Confidence score between 0.0 and 1.0
            action_type: Type of action (e.g., "general", "transfer_money")

        Returns:
            RoutingDecision with routing action and metadata
        """
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise TypeError("confidence must be a number between 0 and 1")
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")

        normalized_action = (action_type or "general").strip().lower()
        if normalized_action in HIGH_RISK_ACTIONS:
            return RoutingDecision(
                action="escalate", confidence=float(confidence),
                reason=f"High-risk action requires human approval: {normalized_action}",
                priority="high", requires_human=True,
            )
        if confidence >= self.HIGH_THRESHOLD:
            return RoutingDecision(
                action="auto_send", confidence=float(confidence),
                reason="High confidence; no high-risk action detected",
                priority="low", requires_human=False,
            )
        if confidence >= self.MEDIUM_THRESHOLD:
            return RoutingDecision(
                action="queue_review", confidence=float(confidence),
                reason="Medium confidence; reviewer should verify before sending",
                priority="normal", requires_human=True,
            )
        return RoutingDecision(
            action="escalate", confidence=float(confidence),
            reason="Low confidence; escalate for human review",
            priority="high", requires_human=True,
        )


# ============================================================
# Optional enrichment: 3 HITL decision points (không chấm)
# Không bắt buộc điền. Tóm tắt bài nộp: chạy scripts/grade.py
# (tự sinh lab_report.md) — không viết report tay.
#
# For each decision point, define:
# - trigger: What condition activates this HITL check?
# - hitl_model: Which model? (human-in-the-loop, human-on-the-loop,
#   human-as-tiebreaker)
# - context_needed: What info does the human reviewer need?
# - example: A concrete scenario
# - approval_path: What approve/reject/timeout decision is recorded?
# - audit_fields: Which correlation ID, intent and proposed action/diff are logged?
#
# Think about real banking scenarios where human judgment is critical.
# ============================================================

hitl_decision_points = [
    {
        "id": 1,
        "name": "High-risk transfer approval",
        "trigger": "Any transfer above the bank's configured risk threshold or to a new payee.",
        "hitl_model": "human-in-the-loop",
        "context_needed": "Authenticated customer, verified payee, amount, currency, balance, risk signals, and an immutable action preview.",
        "example": "A customer asks the assistant to transfer 50,000,000 VND to a newly added account.",
        "approval_path": "Bind reviewer approval to the exact transfer details; reject on denial or timeout. A changed amount or payee requires a fresh approval.",
        "audit_fields": "correlation_id, customer_id, action, payee_hash, amount, currency, risk_reason, request_hash, reviewer_id, decision, timestamp, timeout",
    },
    {
        "id": 2,
        "name": "Account recovery and identity mismatch",
        "trigger": "Identity verification signals disagree, or recovery would change a trusted contact method.",
        "hitl_model": "human-on-the-loop",
        "context_needed": "Verification provenance, recent account changes, fraud indicators, and masked contact details; never expose raw credentials.",
        "example": "A caller passes one verification step but requests a password reset to a new phone number.",
        "approval_path": "Pause recovery and queue a trained fraud reviewer. Approve only after independent verification; denial or timeout leaves the account protected.",
        "audit_fields": "correlation_id, account_id, verification_methods, mismatch_codes, risk_score, proposed_change, reviewer_id, decision, timestamp",
    },
    {
        "id": 3,
        "name": "Disputed or ambiguous customer instruction",
        "trigger": "Conversation instructions conflict, or the proposed tool action does not match confirmed customer intent.",
        "hitl_model": "human-as-tiebreaker",
        "context_needed": "Relevant conversation turns, explicit user confirmation, proposed action, and a plain-language explanation of the ambiguity.",
        "example": "The user asks to cancel a card, then asks to keep it active while disputing a charge.",
        "approval_path": "Ask the customer to clarify where possible. If ambiguity remains, hold for human review; silence or timeout cancels the action.",
        "audit_fields": "correlation_id, conversation_turn_ids, intent_candidates, proposed_action, ambiguity_reason, reviewer_id, decision, timestamp",
    },
]


# ============================================================
# Quick tests
# ============================================================

def test_confidence_router():
    """Test ConfidenceRouter with sample scenarios."""
    router = ConfidenceRouter()

    test_cases = [
        ("Balance inquiry", 0.95, "general"),
        ("Interest rate question", 0.82, "general"),
        ("Ambiguous request", 0.55, "general"),
        ("Transfer $50,000", 0.98, "transfer_money"),
        ("Close my account", 0.91, "close_account"),
    ]

    print("Testing ConfidenceRouter:")
    print("=" * 80)
    print(f"{'Scenario':<25} {'Conf':<6} {'Action Type':<18} {'Decision':<15} {'Priority':<10} {'Human?'}")
    print("-" * 80)

    for scenario, conf, action_type in test_cases:
        decision = router.route(scenario, conf, action_type)
        print(
            f"{scenario:<25} {conf:<6.2f} {action_type:<18} "
            f"{decision.action:<15} {decision.priority:<10} "
            f"{'Yes' if decision.requires_human else 'No'}"
        )

    print("=" * 80)


def test_hitl_points():
    """Display HITL decision points."""
    print("\nHITL Decision Points:")
    print("=" * 60)
    for point in hitl_decision_points:
        print(f"\n  Decision Point #{point['id']}: {point['name']}")
        print(f"    Trigger:  {point['trigger']}")
        print(f"    Model:    {point['hitl_model']}")
        print(f"    Context:  {point['context_needed']}")
        print(f"    Example:  {point['example']}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_confidence_router()
    test_hitl_points()
