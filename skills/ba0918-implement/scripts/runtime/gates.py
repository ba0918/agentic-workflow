"""Human gates and bounded automatic recovery."""
from runtime.types import RuntimeResult, failure, ok

ALLOWED_GATE_KINDS = {"irreversible", "human_permission", "dangerous_target"}

def validate_gate(gate: object) -> RuntimeResult:
    if not isinstance(gate, dict) or gate.get("kind") not in ALLOWED_GATE_KINDS:
        return failure("human_gate_not_allowed", "human gates are limited to irreversible, permission, and dangerous-target boundaries")
    if not isinstance(gate.get("reason"), str) or not gate["reason"].strip():
        return failure("human_gate_reason_missing", "human gate needs a concrete reason")
    return ok(dict(gate))

def recovery_action(*, diagnosed: bool, method_changed: bool, still_stuck: bool) -> str:
    if not still_stuck:
        return "continue"
    if not diagnosed:
        return "diagnose"
    if not method_changed:
        return "change_method"
    return "human_judgment"
