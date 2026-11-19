"""
The two tools the agent can call: search_rules and read_clause. Both answer with a bundle
(retrieval/build_bundle.py), the same builder the plain RAG sources come from, so every source block has
one format, and the model cites tool results exactly as it cites the starting sources.

search_rules(query, top_k)  vector search on the clauses, the same search as plain RAG, but with the
                            model's own words and its own top_k (1 to 100). Each hit comes in full,
                            with its list items; every clause the rule map brings for it comes as a
                            one-line preview.
read_clause(chunk_id)       one clause in full, with its list items at every level, and a preview of
                            every clause it links to (cited clauses, alternatives, para exceptions,
                            official's instructions, diagrams). Previews leave the model to decide
                            which links are worth a read.

Within one question, a clause already shown in full comes back as one "shown above" line instead of
its text again (start_question resets this for each question). read_clause always shows the clause it
was asked for.

A bad call (a top_k outside 1 to 100, an unknown chunk id, a wrong argument) returns an error message
as the tool result instead of raising. The model reads it and can try again; the run counts it.

Use:
    rule_tools = RuleTools(chunks, search, rule_map)
    rule_tools.start_question(starting_ids)
    tool_result = rule_tools.run_tool_call("search_rules", '{"query": "let", "top_k": 5}')
"""

import difflib
import json
from collections.abc import Callable
from dataclasses import dataclass, field

from retrieval.build_bundle import build_bundle, format_bundle, full_chunks, label_by_full_id


# Constants
## The range of top_k the model may ask for; outside it, the call returns an error
SMALLEST_TOP_K = 1
LARGEST_TOP_K = 100

## How many near ids an unknown chunk id error suggests
SUGGESTED_ID_COUNT = 5

## The tool definitions sent to the model on every call (Mistral's function-calling format)
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_rules",
            "description": (
                "Searches the badminton rule books (Laws of Badminton, Instructions to Technical Officials, "
                "Alternative Laws) by meaning, and returns the closest clauses as source blocks, each with a "
                "one-line preview of the clauses it links to. Use the rule books' own words when you can (for "
                "example 'let', 'unsighted', 'suspended')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for, in your own words."},
                    "top_k": {
                        "type": "integer",
                        "description": (
                            "How many clauses to return, from 1 to 100. Start small (5 to 10); ask for more "
                            "only when the results miss what you need."
                        ),
                    },
                },
                "required": ["query", "top_k"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_clause",
            "description": (
                "Reads one clause by its chunk id (the id in square brackets on a source block or a preview, "
                "such as laws-16.7). Returns the clause with every clause under it, and a one-line preview of "
                "each clause it links to. Use it when a source names another rule ('Law 16.2'), or when a "
                "preview looks like it answers part of the question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chunk_id": {"type": "string", "description": "The chunk id, such as laws-16.7 or itto-5.12.2."},
                },
                "required": ["chunk_id"],
            },
        },
    },
]

# ===== One tool result =====

@dataclass
class ToolResult:
    """What one tool call returns: the text the model reads, the chunks it showed with their labels, and the error, if any."""

    text: str
    shown_chunks: list[dict] = field(default_factory=list)
    shown_label_by_id: dict[str, str] = field(default_factory=dict)
    error: str | None = None


# ===== The tools =====

class RuleTools:
    """Runs the agent's tool calls over the clauses, a search function and the rule map."""

    def __init__(self, chunks: list[dict], search: Callable[[str, int], list[dict]], rule_map: dict):
        self.chunk_by_id = {chunk["id"]: chunk for chunk in chunks}
        self.search = search
        self.rule_map = rule_map
        self.shown_ids: set[str] = set()

    def start_question(self, shown_ids: set[str]) -> None:
        """Starts a new question: the clauses its starting sources showed in full are the only ones shown so far."""
        self.shown_ids = set(shown_ids)

    def answer_with_bundle(self, hit_ids: list[str], shown_ids: set[str]) -> ToolResult:
        """Returns the bundle for these hits as a tool result, and counts its full clauses as shown."""
        items = build_bundle(hit_ids, self.chunk_by_id, self.rule_map, related_in_full=False, shown_ids=shown_ids)
        shown_chunks = full_chunks(items)
        self.shown_ids.update(chunk["id"] for chunk in shown_chunks)

        # The labels go with the clauses, so the write call sees each sentence under its label
        return ToolResult(text=format_bundle(items), shown_chunks=shown_chunks, shown_label_by_id=label_by_full_id(items))

    def search_rules(self, query: str, top_k: int) -> ToolResult:
        """Returns the top_k closest clauses to the query with previews of their links, or an error when top_k is out of range."""

        # Reject an out-of-range top_k instead of clamping it, so the model learns the rule
        is_whole_number = isinstance(top_k, int) and not isinstance(top_k, bool)
        is_in_range = is_whole_number and SMALLEST_TOP_K <= top_k <= LARGEST_TOP_K
        if not is_in_range:
            error = f"top_k must be a whole number from {SMALLEST_TOP_K} to {LARGEST_TOP_K}; got {top_k!r}."
            return ToolResult(text=f"Error: {error}", error=error)

        # Search, and answer with the hits' bundle
        hit_ids = [chunk["id"] for chunk in self.search(query, top_k)]
        return self.answer_with_bundle(hit_ids, self.shown_ids)

    def read_clause(self, chunk_id: str) -> ToolResult:
        """Returns one clause with its list items and previews of its links, or an error with near ids."""

        # An unknown id gets the closest real ids, so the model can correct a typo or a missing format
        if chunk_id not in self.chunk_by_id:
            near_ids = difflib.get_close_matches(chunk_id, self.chunk_by_id, n=SUGGESTED_ID_COUNT, cutoff=0.6)
            error = f"No clause has the id {chunk_id!r}. Close ids: {', '.join(near_ids) or 'none'}."
            return ToolResult(text=f"Error: {error}", error=error)

        # The clause asked for is always shown in full, even when shown before
        shown_ids_but_this_one = self.shown_ids.difference({chunk_id})
        return self.answer_with_bundle([chunk_id], shown_ids_but_this_one)

    def run_tool_call(self, tool_name: str, arguments: str | dict) -> ToolResult:
        """Runs one tool call by name, or returns an error for an unknown tool or bad arguments."""

        # The SDK hands arguments over as a JSON string or as a dict, depending on the reply
        argument_values = arguments
        if isinstance(arguments, str):
            try:
                argument_values = json.loads(arguments)
            except json.JSONDecodeError:
                error = f"The arguments are not valid JSON: {arguments!r}."
                return ToolResult(text=f"Error: {error}", error=error)

        # Call the named tool with its arguments; a missing argument is an error the model can fix
        try:
            if tool_name == "search_rules":
                return self.search_rules(argument_values["query"], argument_values["top_k"])
            if tool_name == "read_clause":
                return self.read_clause(argument_values["chunk_id"])
        except KeyError as missing_argument:
            error = f"{tool_name} needs the argument {missing_argument}."
            return ToolResult(text=f"Error: {error}", error=error)
        error = f"There is no tool named {tool_name!r}. The tools are search_rules and read_clause."
        return ToolResult(text=f"Error: {error}", error=error)
