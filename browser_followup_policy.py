from __future__ import annotations


def looks_like_general_question(lowered: str) -> bool:
    return lowered.startswith((
        "how does ", "how do ", "what is ", "what are ", "what was ",
        "why ", "should ", "explain ", "relate ",
    ))


def looks_like_writing_or_advice_request(lowered: str) -> bool:
    return lowered.startswith((
        "write ", "draft ", "give me ", "help me ", "make a ", "make an ",
        "create an outline", "summarize ", "translate ",
    ))
