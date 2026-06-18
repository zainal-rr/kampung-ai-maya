from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import tempfile
from pathlib import Path

from maya_core.execution_broker_read_policy import personal_data_read_denies
from maya_core.provenance import make_provenance
from maya_meet.actions import meeting_action_class
from maya_meet.policy import meeting_turn_decision
from maya_meet.voiceprint import verify_voiceprint
from maya_meet.voiceprint_store import active_voiceprint_path, enroll_voiceprint, enrollment_status, revoke_voiceprint


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-voiceprint-") as tmp:
        root = Path(tmp)
        blocked = enroll_voiceprint(
            owner_provenance=make_provenance("other_speaker"),
            embedding=[1.0, 0.0, 0.0],
            threshold=0.90,
            sample_count=2,
            root=root,
        )
        _require(blocked.reason_code == "unauthorized_enrollment_source", str(blocked))
        enrolled = enroll_voiceprint(
            owner_provenance=make_provenance("owner_text"),
            embedding=[1.0, 0.0, 0.0],
            threshold=0.90,
            sample_count=3,
            root=root,
        )
        _require(enrolled.status == "enrolled", str(enrolled))
        _require(enrollment_status(root) == "enrolled", "status not enrolled")
        path = active_voiceprint_path(root)
        _require(path.exists(), "voiceprint file missing")
        _require((path.stat().st_mode & 0o777) == 0o600, "voiceprint file not 0600")

        payload = __import__("json").loads(path.read_text("utf-8"))
        owner = verify_voiceprint(payload, [0.99, 0.01, 0.0])
        _require(owner.source_kind == "owner_voice_meeting", str(owner))
        other = verify_voiceprint(payload, [0.0, 1.0, 0.0])
        _require(other.source_kind == "other_speaker" and other.reason_code == "voiceprint_low_confidence", str(other))
        low = verify_voiceprint(payload, [0.7, 0.7, 0.0])
        _require(low.source_kind == "other_speaker", str(low))
        mismatched = verify_voiceprint(payload, [1.0])
        _require(
            mismatched.source_kind == "other_speaker"
            and mismatched.reason_code == "voiceprint_dimension_mismatch",
            str(mismatched),
        )
        malformed = verify_voiceprint(payload, [float("nan"), 0.0, 0.0])
        _require(
            malformed.source_kind == "other_speaker"
            and malformed.reason_code == "voiceprint_malformed_vector",
            str(malformed),
        )
        string_sample = verify_voiceprint(payload, "100")  # type: ignore[arg-type]
        _require(
            string_sample.source_kind == "other_speaker"
            and string_sample.reason_code == "voiceprint_malformed_vector",
            str(string_sample),
        )
        string_payload = dict(payload)
        string_payload["embedding"] = "100"
        string_enrollment = verify_voiceprint(string_payload, [1.0, 0.0, 0.0])
        _require(
            string_enrollment.source_kind == "other_speaker"
            and string_enrollment.reason_code == "voiceprint_malformed_vector",
            str(string_enrollment),
        )
        _require("embedding" not in str(owner.as_dict()).lower(), "decision log leaked embedding")

        reversible = meeting_turn_decision(
            text="Maya, open the agenda doc",
            provenance=make_provenance("other_speaker"),
            action_class="open_view",
            m2_enabled=True,
        )
        _require(reversible.status == "allowed", str(reversible))
        browser_lookup = meeting_turn_decision(
            text="Maya, open the browser",
            provenance=make_provenance("other_speaker"),
            action_class="lookup",
            m2_enabled=True,
        )
        _require(browser_lookup.status == "allowed", str(browser_lookup))
        office_draft = meeting_turn_decision(
            text="Maya, make a Word document",
            provenance=make_provenance("other_speaker"),
            action_class="draft",
            m2_enabled=True,
        )
        _require(office_draft.status == "allowed", str(office_draft))
        office_revision = meeting_turn_decision(
            text="Maya, revise the Word document",
            provenance=make_provenance("other_speaker"),
            action_class="scratch_artifact",
            m2_enabled=True,
        )
        _require(office_revision.status == "allowed", str(office_revision))
        irreversible = meeting_turn_decision(
            text="Maya, send the notes",
            provenance=make_provenance("other_speaker"),
            action_class="send",
            m2_enabled=True,
        )
        _require(irreversible.reason_code == "meeting_action_requires_owner_telegram_approval", str(irreversible))
        disclosure = meeting_turn_decision(
            text="Maya, read my private notes aloud",
            provenance=make_provenance("other_speaker"),
            action_class="answer",
            content_class="owner_private",
            m2_enabled=True,
        )
        _require(disclosure.reason_code == "owner_private_disclosure_requires_telegram", str(disclosure))
        private_page = meeting_turn_decision(
            text="Maya, open Gmail",
            provenance=make_provenance("other_speaker"),
            action_class=meeting_action_class("open Gmail"),
            m2_enabled=True,
        )
        _require(private_page.reason_code == "meeting_action_requires_owner_telegram_approval", str(private_page))

        denied_revoke = revoke_voiceprint(owner_provenance=make_provenance("meeting_transcript"), root=root)
        _require(denied_revoke.reason_code == "unauthorized_enrollment_source", str(denied_revoke))
        revoked = revoke_voiceprint(owner_provenance=make_provenance("owner_voice"), root=root)
        _require(revoked.status == "revoked", str(revoked))

    voiceprint_path = Path.home() / "Desktop" / "Maya" / "voiceprints" / "owner_voiceprint.json"
    denied = personal_data_read_denies(())
    _require(any(str(voiceprint_path).startswith(str(root)) for root in denied), "voiceprint root missing from W5 personal-data deny")
    print("meet_voiceprint_policy_smoke: ok")


if __name__ == "__main__":
    main()
