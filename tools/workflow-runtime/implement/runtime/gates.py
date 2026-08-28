"""Human gates and bounded automatic recovery."""
from runtime.types import JsonObject, RuntimeResult, failure, object_values, ok

ALLOWED_GATE_KINDS = {"irreversible", "human_permission", "dangerous_target"}

def validate_gate(gate: object) -> RuntimeResult[JsonObject]:
    if not isinstance(gate, dict) or gate.get("kind") not in ALLOWED_GATE_KINDS:
        return failure("human_gate_not_allowed", "human gates are limited to irreversible, permission, and dangerous-target boundaries")
    if not isinstance(gate.get("reason"), str) or not gate["reason"].strip():
        return failure("human_gate_reason_missing", "human gate needs a concrete reason")
    return ok(dict(gate))

def declared_gate(
    binding: JsonObject, step_id: str, gate_id: str, result: str,
) -> RuntimeResult[JsonObject]:
    steps = object_values(binding.get("steps")) or []
    step = next((item for item in steps if item.get("id") == step_id), None)
    gates = object_values(step.get("human_gates")) if step is not None else None
    gate = next(
        (item for item in gates or [] if item.get("gate_id") == gate_id), None,
    )
    allowed = gate.get("allowed_results") if gate is not None else None
    if gate is None:
        return failure("human_gate_unknown", "Human gate is not declared by the active plan")
    if not isinstance(allowed, list) or result not in allowed:
        return failure("human_gate_result_invalid", "Human gate result is not allowed")
    return ok(gate)

def recovery_action(*, diagnosed: bool, method_changed: bool, still_stuck: bool) -> str:
    if not still_stuck:
        return "continue"
    if not diagnosed:
        return "diagnose"
    if not method_changed:
        return "change_method"
    return "human_judgment"
