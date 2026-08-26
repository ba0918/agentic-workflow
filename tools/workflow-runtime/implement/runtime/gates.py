"""Human gates declared by the plan."""
from runtime.tdd import test_target_snapshot

from runtime.storage import content_identity
from runtime.types import IDENTITY, matches
from runtime.types import RuntimeFailure, RuntimeResult, Attempt, ok, failure
from runtime.context import append_event, load_effective_binding, load_events, stop_attempt


HUMAN_GATE_TIMINGS = {
    "before_edit": 0,
    "before_commit": 1,
    "before_implementation_green": 2,
}


def validate_human_gate_event(binding: dict, event: object) -> RuntimeResult:
    if not isinstance(event, dict) or event.get("event_type") != "human_gate":
        return failure("human_gate_event_invalid", "event is not a human gate decision", None)
    declaration = next(
        (gate for gate in binding["human_gates"] if gate["gate_id"] == event.get("gate_id")),
        None,
    )
    if declaration is None:
        return failure("human_gate_undeclared", "human gate is not declared by the plan", "gate_id")
    if declaration["step_id"] != event.get("step_id"):
        return failure("human_gate_step_mismatch", "human gate step differs from its declaration", "step_id")
    if event.get("result") not in declaration["allowed_results"] or not matches(
        IDENTITY, event.get("target_identity")
    ):
        return failure("human_gate_event_invalid", "human gate result or target identity is invalid", None)
    return ok(event)


def validate_human_gate_boundary(
    binding: dict,
    events: list[dict],
    *,
    step_id: str,
    timing: str,
    target_identities: dict[str, str],
) -> RuntimeResult:
    if timing not in HUMAN_GATE_TIMINGS:
        return failure("human_gate_timing_invalid", "human gate boundary timing is invalid", "timing")
    for event in events:
        if event.get("event_type") == "human_gate":
            validation = validate_human_gate_event(binding, event)
            if not validation.ok:
                return validation

    required = [
        gate
        for gate in binding["human_gates"]
        if gate["step_id"] == step_id
        and HUMAN_GATE_TIMINGS[gate["timing"]] <= HUMAN_GATE_TIMINGS[timing]
    ]
    for gate in required:
        current_identity = target_identities.get(gate["gate_id"])
        if not matches(IDENTITY, current_identity):
            return failure("human_gate_target_unavailable", "human gate target identity is unavailable", "target_identity")
        decisions = [
            event
            for event in events
            if event.get("event_type") == "human_gate"
            and event.get("gate_id") == gate["gate_id"]
            and event.get("step_id") == step_id
        ]
        if not decisions:
            return failure("human_gate_missing", "required human gate has no decision", gate["gate_id"])
        decision = decisions[-1]
        if decision["target_identity"] != current_identity:
            return failure("human_gate_target_changed", "human gate approval is stale", gate["gate_id"])
        if decision["result"] == "rejected":
            return failure("human_gate_rejected", "human gate was rejected", gate["gate_id"])
    return ok(required)


def _human_gate_target_identities(
    attempt: Attempt,
    binding: dict,
    *,
    step_id: str,
    timing: str,
) -> RuntimeResult:
    identities: dict[str, str] = {}
    boundary = HUMAN_GATE_TIMINGS[timing]
    for gate in binding["human_gates"]:
        if gate["step_id"] != step_id:
            continue
        if HUMAN_GATE_TIMINGS[gate["timing"]] > boundary:
            continue
        target = gate["target"]
        if target["kind"] == "event":
            identities[gate["gate_id"]] = target["content_identity"]
            continue
        observed = test_target_snapshot(attempt.worktree, target["paths"])
        if not observed.ok:
            return observed
        identities[gate["gate_id"]] = content_identity(observed.value)
    return ok(identities)

def check_human_gates(attempt: Attempt, *, step_id: str, timing: str) -> RuntimeResult:
    binding_result = load_effective_binding(attempt)
    if not binding_result.ok:
        return binding_result
    if timing not in HUMAN_GATE_TIMINGS:
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
    result = validate_human_gate_boundary(
        binding_result.value,
        events.value,
        step_id=step_id,
        timing=timing,
        target_identities=identities.value,
    )
    if not result.ok:
        return failure(result.error.code, result.error.message, result.error.detail)
    return ok(identities.value)

def record_human_gate(
    attempt: Attempt,
    *,
    step_id: str,
    gate_id: str,
    result: str,
) -> RuntimeResult:
    binding_result = load_effective_binding(attempt)
    if not binding_result.ok:
        return binding_result
    binding = binding_result.value
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
