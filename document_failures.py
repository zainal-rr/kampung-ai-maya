from __future__ import annotations


def document_generation_failed(label: str, exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if "codex" in lowered and "gemini" in lowered:
        provider = "Codex app lane and Gemini"
    elif "kimi and gemini" in lowered:
        provider = "Kimi and Gemini"
    elif "codex" in lowered:
        provider = "Codex app lane"
    else:
        provider = "Kimi" if "kimi" in lowered else "Gemini Flash"
    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        reason = f"{provider} quota is exhausted right now"
    elif "API_KEY" in text or "api key" in lowered:
        reason = f"the {provider} API key is not usable right now"
    elif "timed out" in lowered or "timeout" in lowered:
        reason = f"{provider} timed out"
    else:
        reason = f"{provider} drafting failed"
    return f"I could not create the {label} because {reason}. No file was created."
