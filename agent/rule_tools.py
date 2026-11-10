"""
The two tools the agent can call: search_rules and read_clause.

search_rules(query, top_k)  vector search on the clauses, the same search as setup A, but with the
                            model's own words and its own top_k (1 to 100). No rule links: following
                            links is the model's job.
read_clause(chunk_id)       one clause, its direct sub-clauses, the ids of the clauses it links to, and
                            the ids of its alternatives and para exceptions. Ids only, so the model
                            decides which links are worth a read.

Both return source blocks in the same format as the answer prompt (answer/build_answer_prompt.py), so
the model cites tool results exactly as it cites the starting sources, and the citation check works
on them unchanged.

Prompt version 2 (Stage 3, 10 Nov) changes one line: search_rules's query description said "in your own
words", against the tool description's "use the rule books' own words" (build_tool_definitions).

A bad call (a top_k outside 1 to 100, an unknown chunk id, a wrong argument) returns an error message
as the tool result instead of raising. The model reads it and can try again; the run counts it.

Use:
    rule_tools = RuleTools(chunks, search, rule_map)
    tool_definitions = build_tool_definitions(prompt_version=2)
    tool_result = rule_tools.run_tool_call("search_rules", '{"query": "let", "top_k": 5}')
"""

import copy
import difflib
import json
from collections.abc import Callable
from dataclasses import dataclass, field

from answer.build_answer_prompt import format_source
from retrieval.expand_with_rule_links import direct_sub_clauses


# Constants
## The range of top_k the model may ask for; outside it, the call returns an error
SMALLEST_TOP_K = 1
LARGEST_TOP_K = 100

## How many near ids an unknown chunk id error suggests
SUGGESTED_ID_COUNT = 5

## Links that point back to a clause and that read_clause also lists, as it names them. The rule books
## write these one way only: an Alternative Laws clause names the Law it replaces, but the Law never
## names its alternatives, so without them read_clause("laws-8.1.3") would show no way to the
## best-of-five rule. The map follows the same two (retrieval/expand_with_rule_links.py)
POINTING_BACK_NAMES = {
    "overrides": "alternative",
    "para_exception_of": "para exception",
}

## Each link relation in data/rule_links.json, as the read_clause result names it
RELATION_NAMES = {
    "cites": "cites",
    "instructions_for": "official's instructions",
    "overrides": "alternative to",
    "para_exception_of": "para exception to",
    "shows_diagram": "diagram",
}

## The tool definitions sent to the model on every call (Mistral's function-calling format)
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_rules",
            "description": (
                "Searches the badminton rule books (Laws of Badminton, Instructions to Technical Officials, "
                "Alternative Laws) by meaning, and returns the closest clauses as source blocks. Use the rule "
                "books' own words when you can (for example 'let', 'unsighted', 'suspended')."
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
                "Reads one clause by its chunk id (the id in square brackets on a source block, such as "
                "laws-16.7). Returns the clause, the clauses directly under it, and the ids of the clauses "
                "it links to. Use it when a source names another rule ('Law 16.2') or ends with a colon."
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

## Prompt version 2's search_rules query description, which agrees with the tool description
SEARCH_QUERY_DESCRIPTION_VERSION_2 = "What to search for, in the documents' own terms where you know them."


# ===== The tool definitions of each prompt version =====

def build_tool_definitions(prompt_version: int) -> list[dict]:
    """Returns the tool definitions a prompt version sends: version 1 as above, version 2 with its query description."""
    if prompt_version == 1:
        return TOOL_DEFINITIONS

    # A copy, so version 1's definitions stay exactly as every earlier run sent them
    tool_definitions = copy.deepcopy(TOOL_DEFINITIONS)
    for tool_definition in tool_definitions:
        function_definition = tool_definition["function"]
        if function_definition["name"] == "search_rules":
            function_definition["parameters"]["properties"]["query"]["description"] = SEARCH_QUERY_DESCRIPTION_VERSION_2
    return tool_definitions


# ===== One tool result =====

@dataclass
class ToolResult:
    """What one tool call returns: the text the model reads, the chunks it showed, and the error, if any."""

    text: str
    shown_chunks: list[dict] = field(default_factory=list)
    error: str | None = None


# ===== The tools =====

class RuleTools:
    """Runs the agent's tool calls over the clauses, a search function and the rule map."""

    def __init__(self, chunks: list[dict], search: Callable[[str, int], list[dict]], rule_map: dict):
        self.chunk_by_id = {chunk["id"]: chunk for chunk in chunks}
        self.search = search
        self.rule_map = rule_map

    def search_rules(self, query: str, top_k: int) -> ToolResult:
        """Returns the top_k closest clauses to the query, or an error when top_k is out of range."""

        # Reject an out-of-range top_k instead of clamping it, so the model learns the rule
        is_whole_number = isinstance(top_k, int) and not isinstance(top_k, bool)
        is_in_range = is_whole_number and SMALLEST_TOP_K <= top_k <= LARGEST_TOP_K
        if not is_in_range:
            error = f"top_k must be a whole number from {SMALLEST_TOP_K} to {LARGEST_TOP_K}; got {top_k!r}."
            return ToolResult(text=f"Error: {error}", error=error)

        # Search, and show each hit as a source block
        hits = self.search(query, top_k)
        source_blocks = [format_source(chunk) for chunk in hits]
        return ToolResult(text="\n\n".join(source_blocks), shown_chunks=hits)

    def read_clause(self, chunk_id: str) -> ToolResult:
        """Returns one clause, its direct sub-clauses and the ids it links to, or an error with near ids."""

        # An unknown id gets the closest real ids, so the model can correct a typo or a missing format
        if chunk_id not in self.chunk_by_id:
            near_ids = difflib.get_close_matches(chunk_id, self.chunk_by_id, n=SUGGESTED_ID_COUNT, cutoff=0.6)
            error = f"No clause has the id {chunk_id!r}. Close ids: {', '.join(near_ids) or 'none'}."
            return ToolResult(text=f"Error: {error}", error=error)

        # The clause, then the clauses one level below it, as source blocks
        chunk = self.chunk_by_id[chunk_id]
        shown_chunks = [chunk]
        for sub_clause_id in direct_sub_clauses(self.chunk_by_id, chunk):
            shown_chunks.append(self.chunk_by_id[sub_clause_id])
        source_blocks = [format_source(shown_chunk) for shown_chunk in shown_chunks]

        # The ids it links to, by relation, without their text
        link_lines = self.describe_links(chunk_id)
        text = "\n\n".join(source_blocks)
        if link_lines:
            text += "\n\nLinks from this clause (read any with read_clause):\n" + "\n".join(link_lines)
        return ToolResult(text=text, shown_chunks=shown_chunks)

    def describe_links(self, chunk_id: str) -> list[str]:
        """Returns one line per linked clause: those this chunk links to, then its alternatives and para exceptions."""

        # Links written in this clause
        link_lines = []
        for link in self.rule_map["outgoing"].get(chunk_id, []):
            is_in_corpus = link["to_id"] in self.chunk_by_id
            if is_in_corpus:
                link_lines.append(f"- {RELATION_NAMES[link['relation']]}: {link['to_id']}")

        # Links written the other way: clauses that replace or adapt this one
        for link in self.rule_map["incoming"].get(chunk_id, []):
            if link["relation"] in POINTING_BACK_NAMES:
                link_lines.append(f"- {POINTING_BACK_NAMES[link['relation']]}: {link['from_id']}")
        return link_lines

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
