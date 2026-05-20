# Kampung AI Skill Intelligence Checklist

This checklist is the source of truth for the Hermes-inspired skill intelligence upgrade. Implementation should update this file as work progresses, and the upgrade is not complete until the strict reviewer gives a 100 percent pass.

## 1) Skill Usage Learning

- [x] Add `skill_outcome_events` storage.
- [x] Record skill id.
- [x] Record user request.
- [x] Record channel.
- [x] Record selected lane.
- [x] Record reason selected.
- [x] Record outcome: success, failure, partial, user corrected, blocked, cancelled.
- [x] Record missing step if any.
- [x] Record user correction text if any.
- [x] Record artifact id or workflow id if relevant.
- [x] Record timestamp.
- [x] Repeated failure creates skill improvement proposal.
- [x] Repeated success strengthens trigger examples.
- [x] User correction can become skill memory only after confirmation.
- [x] No skill rewrites itself directly.
- [x] Skill upgrade requires approval before activation.
- [x] Existing `skill_usage_events` remains selection history.
- [x] New outcome table is used for learning quality.

## 2) Skill Memory Per Skill

- [x] Add `skill_memory_items` storage.
- [x] Store skill id.
- [x] Store kind.
- [x] Store content.
- [x] Store source.
- [x] Store confidence.
- [x] Store status: active, stale, rejected, disabled.
- [x] Store created time.
- [x] Store updated time.
- [x] Support memory kind: what worked.
- [x] Support memory kind: what failed.
- [x] Support memory kind: user preference.
- [x] Support memory kind: example.
- [x] Support memory kind: test case.
- [x] Support memory kind: safe data note.
- [x] Support memory kind: blocked data note.
- [x] Retrieve skill memory only when the skill is selected or inspected.
- [x] Do not leak skill memory into unrelated global preference answers.
- [x] Block passport number storage.
- [x] Block card detail storage.
- [x] Block bank data storage.
- [x] Block login credential storage.
- [x] Block OTP storage.
- [x] Block private identifier storage.

## 3) Private Maya Skill Library

- [x] Create `maya_skills/active`.
- [x] Create `maya_skills/proposed`.
- [x] Create `maya_skills/disabled`.
- [x] Create `maya_skills/research_notes`.
- [x] Create `maya_skills/tests`.
- [x] New scaffold starts in `maya_skills/proposed`.
- [x] Activation mirrors or moves reviewed skill into `maya_skills/active`.
- [x] Disable mirrors or moves skill into `maya_skills/disabled`.
- [x] Research notes go into `maya_skills/research_notes`.
- [x] Test specs go into `maya_skills/tests`.
- [x] Existing flat skill scaffold paths remain readable.
- [x] Database remains source of truth for status.
- [x] Folders are human readable library view only.
- [x] Proposed skills do not enter active prompt context.
- [x] Approved but untested skills do not enter active prompt context.
- [x] Disabled skills do not enter active prompt context.
- [x] Draft skills do not enter active prompt context.

## 4) Weekly Skill Review Routine

- [x] Add `weekly_skill_review.py`.
- [x] Dry run works without provider keys.
- [x] Inspect most used skills.
- [x] Inspect skills with failures.
- [x] Inspect skills with user corrections.
- [x] Inspect skills with missing steps.
- [x] Inspect stale or unused skills.
- [x] Inspect proposed skills waiting too long.
- [x] Inspect disabled skills that may stay disabled.
- [x] Inspect unsupported action logs for possible new skills.
- [x] Output skill review summary.
- [x] Output proposed improvements.
- [x] Output skills to test.
- [x] Output skills to disable.
- [x] Output new skill candidates.
- [x] Maya can show latest skill review naturally.
- [x] Maya asks before creating, editing, activating, or disabling any skill.
- [x] Provider review is optional later.
- [x] No key dry run is required now.

## 5) Messaging Gateway Cleanup

- [x] Add channel adapter contract.
- [x] Contract includes channel id.
- [x] Contract includes inbound text or event.
- [x] Contract includes optional attachments.
- [x] Contract includes visible channel name.
- [x] Contract includes can send text.
- [x] Contract includes can send files.
- [x] Contract includes can speak.
- [x] Contract includes can show local app or screen.
- [x] Contract includes privacy level.
- [x] Contract includes delivery limits.
- [x] Add Telegram adapter.
- [x] Add iMac voice adapter.
- [x] Add Omi transcript adapter.
- [x] Add Mudra event adapter.
- [x] Add placeholder future WhatsApp or email adapter.
- [x] Adapters only translate input and output.
- [x] Maya core owns routing.
- [x] Maya core owns memory.
- [x] Maya core owns skills.
- [x] Maya core owns safety.
- [x] Maya core owns workflow state.
- [x] No adapter contains personality rules.
- [x] No adapter directly activates skills.

## 6) Honest Self Improvement Language

- [x] "I learned a preference" only after write and read back succeeded.
- [x] "I updated a skill proposal" only after scaffold or metadata changed.
- [x] "I improved an active skill" only after approval, tests, and activation.
- [x] "I cannot improve this yet because I need approval" when blocked by safety.
- [x] "I noticed this skill failed twice" only when outcome log supports it.
- [x] Block vague "I'll remember that" without write verification.
- [x] Block vague "I improved myself" without inspectable change.
- [x] Block "Skill updated" when only a suggestion was made.

## 7) Skill Evaluation Before Activation

- [x] Extend `skill_activation_tests` with `test_type`.
- [x] Required test: trigger.
- [x] Required test: non_trigger.
- [x] Required test: safety.
- [x] Required test: happy_path.
- [x] Required test: failure_path.
- [x] Required test: regression.
- [x] Required record: approval.
- [x] `approve skill X` changes status to approved.
- [x] `test skill X` records named test results.
- [x] `activate skill X` succeeds only if required tests passed.
- [x] Failed tests block activation.
- [x] Missing tests block activation.
- [x] Disabled skills stay excluded from prompt context.
- [x] Existing simple passed tests count only as legacy smoke.

## 8) User Model With Boundaries

- [x] Add safe user model layer separate from raw memory.
- [x] Allowed category: preferences.
- [x] Allowed category: tone.
- [x] Allowed category: work style.
- [x] Allowed category: recurring worries.
- [x] Allowed category: decision patterns.
- [x] Allowed category: communication style.
- [x] Allowed category: skill specific preferences.
- [x] Hard block passwords.
- [x] Hard block OTP.
- [x] Hard block bank data.
- [x] Hard block card data.
- [x] Hard block private keys.
- [x] Hard block API keys.
- [x] Hard block passport or identity numbers.
- [x] Hard block anything marked private by Zainal.
- [x] Hard block creepy or overly intimate inference without clear consent.
- [x] Explicit cues can save after validation.
- [x] Implicit observations ask before saving.
- [x] Skill specific preferences are stored under that skill.
- [x] Global preferences stay in existing preference layer.
- [x] User model entries show source and confidence.

## 9) Natural Commands

- [x] `show skill memory for flight search`
- [x] `what did this skill learn`
- [x] `show skill review`
- [x] `why did you pick this skill`
- [x] `test skill X`
- [x] `improve skill X`
- [x] `disable skill X`
- [x] `show user model`
- [x] `forget this skill preference`
- [x] Existing `show skill proposals` still works.
- [x] Existing `show active skills` still works.
- [x] Existing `approve skill X` still works.
- [x] Existing `activate skill X` still works.
- [x] Existing `edit skill X` still works.

## 10) Documentation

- [x] Update `KAMPUNG_AI.md`.
- [x] Update `KAMPUNG_AI_CHECKLIST.md`.
- [x] Document skill learning as runtime knowledge, not model fine tuning.
- [x] Document private skill memory cannot override safety gates.
- [x] Document database is source of truth for skill status.
- [x] Document strict reviewer gate.

## 11) Tests

- [x] Add skill outcome smoke.
- [x] Add skill memory smoke.
- [x] Add private skill library smoke.
- [x] Add weekly skill review smoke.
- [x] Add channel adapter smoke.
- [x] Add honest self improvement smoke.
- [x] Add user model boundary smoke.
- [x] Update skill learning loop smoke.
- [x] Update skill usage smoke.
- [x] Run `code_health.py`.
- [x] Run `may1_rehearsal.py`.
- [x] Confirm all Python files stay under 300 lines.

## 12) Strict Reviewer Gate

- [x] Spawn strict senior AI engineer reviewer after implementation.
- [x] Reviewer reads this checklist.
- [x] Reviewer reads implementation diff.
- [x] Reviewer inspects affected code paths.
- [x] Reviewer checks tests and coverage.
- [x] Reviewer checks unsafe memory handling.
- [x] Reviewer checks proposed or disabled skills do not leak into prompt context.
- [x] Reviewer checks no fake activation.
- [x] Reviewer checks channel adapter boundaries.
- [x] Reviewer checks docs.
- [x] Reviewer gives pass only at 100 percent.
- [x] If reviewer fails anything, record finding here.
- [x] Fix implementation.
- [x] Rerun tests.
- [x] Repeat review until 100 percent pass.

## Acceptance Criteria

1) Checklist file exists in repo root.
2) Every item above is represented as a checkbox.
3) Implementation updates this file as work progresses.
4) No implementation is called complete until strict reviewer gives 100 percent pass.

## Review Result

Strict senior AI engineer reviewer result: PASS.
