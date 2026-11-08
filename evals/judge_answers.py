"""
Grades one answer with Claude Sonnet 5.5, against the golden answer, its pass rule and the sources the bot was shown.

Why a judge from another model family: a judge tends to rate answers from its own family
higher than a neutral grader would (self-preference bias), so Claude grades Mistral's answers.
The judge isn't told which model wrote the answer.

The judge only sees answers that passed the code checks (evals/code_checks.py), with their
warnings as hints. It passes or fails three rubric lines, each with a one-sentence reason. Code,
not the judge, decides the overall grade: every line must pass.

Two settings to know:
- Sonnet 5.5 takes no temperature (any value returns a 400 error), so a regrade can differ.
  Running the same setup twice shows how much answers and grades move together (Step 5).
- Thinking is off: each line is a narrow pass-or-fail question, and the reason fields hold the
  explanation. If the judge disagrees with your grades, thinking is one setting to try.
  On Sonnet 5.5, "off" is spelled {"type": "between_tools"}: the API rejects {"type": "disabled"}
  with a 400 and names between_tools as the way to turn thinking off before responding.

Use:
    reply = grade_answer(client, model, question, rules_answer, retrieved_chunks, code_warnings)
    passed = judge_passed(reply.grade)
"""

from dataclasses import dataclass

from anthropic import Anthropic
from pydantic import BaseModel, Field

from answer.answer_shape import RulesAnswer
from answer.build_answer_prompt import format_source


# Constants
## Room for three short reasons
MAX_GRADE_TOKENS = 1024

## The grading rules, sent as the system message on every call
JUDGE_RULES = """You grade answers from a badminton rules bot. The bot may use only the sources it was given.

You get the question, the expected answer (or why the question has no answer in the sources), a pass rule when there is one, the sources the bot was shown, the bot's reply, and any notes from the code checks.

Grade three lines, each pass or fail, with one sentence of reason:
1. key_facts. For a question with an expected answer: the reply states the expected answer's key facts; wording may differ. For a question with no answer: the reply does not give the missing fact (no number, date, name or ruling that the sources don't hold).
2. only_from_sources. Every claim in the reply is in the sources or stated in the question: the reply may repeat what the user said, unless the sources contradict it. A true claim that is in neither still fails. A number the sources don't hold passes only when it is worked out from them, such as an example score that follows a stated rule; a number from memory, such as a year or an amount, fails.
3. follows_pass_rule. The reply follows the pass rule. Pass when there is no pass rule.

Judge the content only. Length, tone and formatting don't matter."""


# ===== The grade's shape =====

class RubricLine(BaseModel):
    """One rubric line: pass or fail, and why."""

    passed: bool
    reason: str = Field(description="One sentence")


class JudgeGrade(BaseModel):
    """The judge's grade on the three rubric lines."""

    key_facts: RubricLine
    only_from_sources: RubricLine
    follows_pass_rule: RubricLine


@dataclass
class GradeReply:
    """One grade, plus the tokens the call used."""

    grade: JudgeGrade
    input_tokens: int
    output_tokens: int


# ===== The overall grade =====

def judge_passed(grade: JudgeGrade) -> bool:
    """True when every rubric line passed."""
    rubric_lines = [grade.key_facts, grade.only_from_sources, grade.follows_pass_rule]
    return all(line.passed for line in rubric_lines)


# ===== Building the judge's prompt =====

def describe_expected_answer(question: dict) -> str:
    """Returns the expected answer, or why the question has no answer in the sources."""
    if question["answer"] is not None:
        return question["answer"]

    # Attack questions carry no why_unanswerable: their pass rule says what a good reply does
    reason = question.get("why_unanswerable", "it asks for something the sources don't settle.")
    return f"None: this question has no answer in the sources. Why: {reason}"


def describe_reply(rules_answer: RulesAnswer) -> str:
    """Returns the bot's reply as the judge reads it: its reasoning, refused or not, the answer, then each citation."""
    citation_lines = [f'- [{citation.chunk_id}] "{citation.quote}"' for citation in rules_answer.citations]
    citations_text = "\n".join(citation_lines)
    if not citation_lines:
        citations_text = "(none)"
    return (f"Reasoning: {rules_answer.reasoning}\nRefused: {rules_answer.refused}\n"
            f"Answer: {rules_answer.answer}\nCitations:\n{citations_text}")


def build_judge_prompt(question: dict, rules_answer: RulesAnswer, retrieved_chunks: list[dict], code_warnings: list[str]) -> str:
    """Returns the user message for grading one reply, with the code checks' warnings for the judge to weigh."""
    sources_text = "\n\n".join(format_source(chunk) for chunk in retrieved_chunks)
    pass_rule = question.get("pass_rule", "None")

    # A warning is a hint, not a verdict: a missing golden number can be context, not a key fact
    code_notes = "None"
    if code_warnings:
        code_notes = "\n".join(code_warnings) + "\n(Hints, not verdicts: a missing golden number may be context only, and a number not in the sources may be worked out from them. Decide by the rubric.)"
    return (
        f"<question>\n{question['question']}\n</question>\n\n"
        f"<expected_answer>\n{describe_expected_answer(question)}\n</expected_answer>\n\n"
        f"<pass_rule>\n{pass_rule}\n</pass_rule>\n\n"
        f"<sources>\n{sources_text}\n</sources>\n\n"
        f"<reply>\n{describe_reply(rules_answer)}\n</reply>\n\n"
        f"<code_notes>\n{code_notes}\n</code_notes>"
    )


# ===== One grade =====

def grade_answer(client: Anthropic, model: str, question: dict, rules_answer: RulesAnswer,
                 retrieved_chunks: list[dict], code_warnings: list[str]) -> GradeReply:
    """Returns the judge's grade for one reply."""
    response = client.messages.parse(
        model=model,
        max_tokens=MAX_GRADE_TOKENS,
        system=JUDGE_RULES,
        messages=[{"role": "user", "content": build_judge_prompt(question, rules_answer, retrieved_chunks, code_warnings)}],
        output_format=JudgeGrade,
        thinking={"type": "between_tools"},
    )
    return GradeReply(
        grade=response.parsed_output,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
