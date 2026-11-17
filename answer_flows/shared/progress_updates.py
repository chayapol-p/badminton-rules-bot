"""
The progress updates the product flow sends while it answers, so the app can show each step as it happens
(Job's pick, 17 Nov: plain-language steps, then the quoted sources early; the answer only once it is checked).

Each update names its step and carries one plain-language line. "found_rules" also carries the rules' names,
and "sources_picked" the quoted sentences the answer will rest on. Those keep their numbers in the final answer:
source n here is citations[n - 1] there, and the final list adds only the related sentences the answer cites.

Steps, in the order they come:
    finding_rules   before the retrieve step
    found_rules     after it, with the names of the rules it found
    checking_rules  before each gather call: the model checks which rules answer the question
    searching       each search the model asks for, with its words
    reading         each clause the model asks to read
    sources_picked  the sentences code kept, with their quotes (not sent when the question is refused)
    writing         before the write call

Use:
    report_progress(ProgressUpdate(step=FINDING_RULES, message="Searching the rule books"))
    run_tool_loop(..., report_progress=report_progress)   # the eval runs leave it at ignore_progress
"""

import json
from collections.abc import Callable

from pydantic import BaseModel, Field

from answer_flows.shared.answer_shape import Citation
from answer_flows.shared.cite_sentences import name_source


# Constants
## The step names, in the order they come
FINDING_RULES = "finding_rules"
FOUND_RULES = "found_rules"
CHECKING_RULES = "checking_rules"
SEARCHING = "searching"
READING = "reading"
SOURCES_PICKED = "sources_picked"
WRITING = "writing"


# ===== One update =====

class ProgressUpdate(BaseModel):
    """One step of an answer in progress: its name, the line the app shows, and any rules or quotes it found."""

    step: str
    message: str
    source_names: list[str] = Field(default_factory=list)
    sources: list[Citation] = Field(default_factory=list)


## What every flow function takes to send its updates
ReportProgress = Callable[[ProgressUpdate], None]


def ignore_progress(update: ProgressUpdate) -> None:
    """Takes an update and does nothing: the default for callers with no screen, such as eval runs."""


# ===== Updates the flow builds =====

def describe_found_rules(starting_chunks: list[dict]) -> ProgressUpdate:
    """Returns the update after the retrieve step: how many rules it found, and their names."""
    source_names = [name_source(chunk) for chunk in starting_chunks]
    return ProgressUpdate(step=FOUND_RULES, message=f"Found {len(source_names)} rules to check",
                          source_names=source_names)


def describe_checking(round_number: int) -> ProgressUpdate:
    """Returns the update before a gather call: the first one checks the rules found, later ones the new results."""
    if round_number == 0:
        return ProgressUpdate(step=CHECKING_RULES, message="Checking which rules answer your question")
    return ProgressUpdate(step=CHECKING_RULES, message="Checking what the search found")


def describe_tool_call(tool_name: str, arguments: str | dict, chunk_by_id: dict[str, dict]) -> ProgressUpdate:
    """Returns the update for one tool call: the search's words, or the clause's name; a plain line when they can't be read."""

    # The SDK hands arguments over as a JSON string or as a dict; a broken one still gets a plain line,
    # because the tool itself records the error for the run file
    argument_values = arguments
    if isinstance(arguments, str):
        try:
            argument_values = json.loads(arguments)
        except json.JSONDecodeError:
            argument_values = {}

    # A search shows its words; a read shows the clause's name
    if tool_name == "search_rules":
        query = argument_values.get("query")
        if query:
            return ProgressUpdate(step=SEARCHING, message=f"Searching the rules: \"{query}\"")
        return ProgressUpdate(step=SEARCHING, message="Searching the rules")
    chunk = chunk_by_id.get(argument_values.get("chunk_id"))
    if chunk is not None:
        source_name = name_source(chunk)
        return ProgressUpdate(step=READING, message=f"Reading {source_name}", source_names=[source_name])
    return ProgressUpdate(step=READING, message="Reading a clause")


def describe_sources_picked(sources: list[Citation]) -> ProgressUpdate:
    """Returns the update after code checks the picks: the sentences the answer will rest on, with their quotes."""
    # One sentence "answers", several "answer"
    counted_sentences = f"{len(sources)} sentences that answer it"
    if len(sources) == 1:
        counted_sentences = "1 sentence that answers it"
    return ProgressUpdate(step=SOURCES_PICKED, message=f"Found {counted_sentences}", sources=sources)


def describe_writing() -> ProgressUpdate:
    """Returns the update before the write call."""
    return ProgressUpdate(step=WRITING, message="Writing the answer")
