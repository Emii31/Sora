"""In-memory traces for the benchmark's explicitly registered chat turns."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Event
from time import perf_counter


@dataclass
class TurnTrace:
    message_id: str = ""
    policy: str = ""
    queued_at: float = 0.0
    persisted_at: float = 0.0
    stages: dict[str, float] = field(default_factory=dict)
    model_attempts: list[dict] = field(default_factory=list)
    persistence_finished: Event = field(default_factory=Event)


_registered: dict[str, TurnTrace] = {}
_active: ContextVar[TurnTrace | None] = ContextVar("chat_timing_trace", default=None)


@contextmanager
def capture(user_id):
    """Register one in-flight turn for a disposable benchmark user."""
    trace = TurnTrace()
    _registered[user_id] = trace
    try:
        yield trace
    finally:
        _registered.pop(user_id, None)


def queued(user_id, message_id):
    trace = _registered.get(user_id)
    if trace is not None:
        trace.message_id = message_id
        trace.queued_at = perf_counter()


@contextmanager
def worker(user_id, message_id):
    trace = _registered.get(user_id)
    if trace is None or trace.message_id != message_id:
        yield
        return
    trace.stages["queue_wait"] = perf_counter() - trace.queued_at
    token = _active.set(trace)
    try:
        yield
    finally:
        _active.reset(token)


def selected_policy(mode):
    trace = _active.get()
    if trace is not None:
        trace.policy = mode


@contextmanager
def span(stage):
    trace = _active.get()
    if trace is None:
        yield
        return
    started = perf_counter()
    try:
        yield
    finally:
        finished = perf_counter()
        trace.stages[stage] = trace.stages.get(stage, 0.0) + finished - started
        if stage == "reply_persistence":
            trace.persisted_at = finished
            trace.persistence_finished.set()


@contextmanager
def model_attempt(kind, attempt):
    trace = _active.get()
    if trace is None:
        yield
        return
    started = perf_counter()
    succeeded = False
    try:
        yield
        succeeded = True
    finally:
        trace.model_attempts.append({
            "kind": kind,
            "attempt": attempt,
            "seconds": perf_counter() - started,
            "succeeded": succeeded,
        })
