from __future__ import annotations

from document_actions_context import apply_artifact_edit_delta, topic_from_state


def _office_session_edit_topic(session, artifact_type: str, instruction: str) -> str:
    state = apply_artifact_edit_delta(session.state, instruction)
    return topic_from_state(artifact_type, state, fallback=session.topic)
