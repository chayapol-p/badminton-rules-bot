"""
The stub answer for POST /chat while data/ is not in the repo.

Returns one fixed, correctly shaped answer for any question: answer text with
inline [n] markers plus the numbered source list they point to. Slice 1's swap
point is the single call to this function in app/chat.py.
"""

from app.chat import ChatReply, SourceEntry


# The canned answer: every [n] marker resolves into sources, and cite_no runs 1..len(sources)
def stub_answer(question: str) -> ChatReply:
    return ChatReply(
        answer=(
            "A serve is legal only while the whole shuttle is below 1.15 m from the surface of the court [1]. "
            "The posts stand 1.55 m high [2]."
        ),
        sources=[
            SourceEntry(
                cite_no=1,
                chunk_id="laws-9.1.4",
                quote="the whole shuttle shall be below 1.15 m from the surface of the court",
                source_name="Laws of Badminton 5.0 (2), Clause 9.1.4",
            ),
            SourceEntry(
                cite_no=2,
                chunk_id="laws-1.4",
                quote="The posts shall be 1.55 m in height from the surface of the court",
                source_name="Laws of Badminton 5.0 (2), Clause 1.4",
            ),
        ],
    )
