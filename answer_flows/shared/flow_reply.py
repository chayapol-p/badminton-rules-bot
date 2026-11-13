"""
The reply every answer flow returns, so the run script reads every flow the same way: the checked answer
(or a format error), the reply's raw text and thinking, every clause the model saw in full, and what the
answer cost in tool rounds, model calls and tokens. A flow with no tools leaves the tool fields at zero.

Use:
    reply = FlowReply(answer=rules_answer, is_format_error=False, error_message=None, raw_reply=raw_reply,
                      thinking=thinking, shown_chunks=shown_chunks)
"""

from dataclasses import dataclass, field

from answer_flows.shared.answer_shape import RulesAnswer


# ===== One answer =====

@dataclass
class FlowReply:
    """One answer, or a format error, plus every chunk the model saw, the tool calls it made and the tokens they used.
    Slice 5 also records the gather call's bad picks and whether the write call ran."""

    answer: RulesAnswer | None
    is_format_error: bool
    error_message: str | None
    raw_reply: str
    thinking: str
    shown_chunks: list[dict]
    tool_rounds: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    tools_turned_off: bool = False
    bad_picks: list[dict] = field(default_factory=list)
    write_called: bool = False
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
