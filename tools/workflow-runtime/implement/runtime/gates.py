"""Human gates declared by the plan."""
from runtime.tdd import test_target_snapshot

from runtime.deps import execution_model
from runtime.types import RuntimeFailure, RuntimeResult, Attempt, ok, failure
from runtime.storage import read_json
from runtime.context import append_event, load_events, stop_attempt


def _human_gate_target_identities(
    attempt: Attempt,
    binding: dict,
    *,
    step_id: str,
    timing: str,
) -> RuntimeResult:
    identities: dict[str, str] = {}
    boundary = execution_model.HUMAN_GATE_TIMINGS[timing]
    for gate in binding["human_gates"]:
        if gate["step_id"] != step_id:
            continue
        if execution_model.HUMAN_GATE_TIMINGS[gate["timing"]] > boundary:
            continue
        target = gate["target"]
        if target["kind"] == "event":
            identities[gate["gate_id"]] = target["content_identity"]
            continue
        observed = test_target_snapshot(attempt.worktree, target["paths"])
        if not observed.ok:
            return observed
        identities[gate["gate_id"]] = execution_model.content_identity(observed.value)
    return ok(identities)

def check_human_gates(attempt: Attempt, *, step_id: str, timing: str) -> RuntimeResult:
    binding_result = read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    binding_validation = execution_model.validate_binding(binding_result.value)
    if not binding_validation.ok:
        return failure(binding_validation.error.code, binding_validation.error.message)
    if timing not in execution_model.HUMAN_GATE_TIMINGS:
        return failure("human_gate_timing_invalid", "human gate timing is invalid")
    events = load_events(attempt)
    if not events.ok:
        return events
    identities = _human_gate_target_identities(
        attempt,
        binding_result.value,
        step_id=step_id,
        timing=timing,
    )
    if not identities.ok:
        return identities
    result = execution_model.validate_human_gate_boundary(
        binding_result.value,
        events.value,
        step_id=step_id,
        timing=timing,
        target_identities=identities.value,
    )
    if not result.ok:
        return failure(result.error.code, result.error.message, result.error.field)
    return ok(identities.value)

def record_human_gate(
    attempt: Attempt,
    *,
    step_id: str,
    gate_id: str,
    result: str,
) -> RuntimeResult:
    binding_result = read_json(attempt.binding_path)
    if not binding_result.ok:
        return binding_result
    binding = binding_result.value
    validation = execution_model.validate_binding(binding)
    if not validation.ok:
        return failure(validation.error.code, validation.error.message)
    declaration = next(
        (
            gate
            for gate in binding["human_gates"]
            if gate["gate_id"] == gate_id and gate["step_id"] == step_id
        ),
        None,
    )
    if declaration is None:
        return failure("human_gate_undeclared", "human gate is not declared for this step")
    if result not in declaration["allowed_results"]:
        return failure("human_gate_event_invalid", "human gate result is invalid")
    identities = _human_gate_target_identities(
        attempt,
        binding,
        step_id=step_id,
        timing=declaration["timing"],
    )
    if not identities.ok:
        return identities
    recorded = append_event(
        attempt,
        "human_gate",
        {
            "gate_id": gate_id,
            "step_id": step_id,
            "target_identity": identities.value[gate_id],
            "result": result,
        },
    )
    if not recorded.ok:
        return recorded
    if result == "rejected":
        return stop_attempt(
            attempt,
            RuntimeFailure("human_gate_rejected", "human gate was rejected", gate_id),
            step_id,
        )
    return recorded
