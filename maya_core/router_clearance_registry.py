from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from pathlib import Path


CLASSIFICATIONS = {"effect", "disclosure", "both", "inert"}
GATE_PLACEMENTS = {"gate_internal", "gate_at_callsite", "ungated_canary", "not_applicable"}
ACTIVE_CLASSIFICATIONS = {"effect", "disclosure", "both"}


@dataclass(frozen=True)
class RouteSurface:
    surface_id: str
    module_path: str
    qualname: str
    layer: str
    classification: str
    required_gate: str
    gate_placement: str
    conformance_test_id: str
    justification: str


@dataclass(frozen=True)
class ScopeInventory:
    scope_id: str
    module_path: str
    module_name: str
    class_name: str
    layer: str
    methods: tuple[str, ...]


@dataclass(frozen=True)
class FixRegisterEntry:
    fix_id: str
    title: str
    verification: str
    evidence: str


SCOPE_ROWS = """
assistant|maya_core/assistant.py|maya_core.assistant|KampungAssistant|gate0|_sync_router,handle_text
assistant_routes|maya_core/assistant_routes.py|maya_core.assistant_routes|AssistantRouter|gate0|route,_route_inner,_route_telegram,_answer_telegram_segment,_handle_telegram_bundle
assistant_commands|maya_core/assistant_commands.py|maya_core.assistant_commands|AssistantCommandRouter|gateA|handle,_handle_activation_command,_handle_reminder,_handle_summary_task,_handle_weekly_reflection,_handle_safety_actions,_handle_everyday_commands,_handle_send_to_telegram,_handle_local_actions,_handle_document_actions,_handle_local_creation_actions,_handle_project_actions,_handle_imac_workflows,_handle_web_actions,_handle_routine_commands,_handle_skill_creation,_handle_explicit_skill_scaffold_approval,_handle_unsupported_action,_handle_task_deletion,_handle_task_listing,_handle_context_window,_handle_artisan_status,_handle_voice_session_command,_handle_review_resolution,_handle_session_memory_command,_handle_preference_listing,_handle_skill_listing,_handle_skill_proposals,_handle_skill_lifecycle,_handle_self_heal_status,_handle_memory_lookup,_handle_memory_forget,_resolve_confirmation
learning|maya_core/learning_pipeline.py|maya_core.learning_pipeline|LearningPipeline|gateB|handle,_save_explicit,_ask_to_save,_resolve_pending,_inspect_lessons,_visible_preferences,_visible_lesson,_verified,_explicit_lesson,_implicit_lesson,_is_direct_test_fact,_normalize_rule,_decision,_is_lesson_inspection,_preference_key
harness|maya_harness/harness_router.py|maya_harness.harness_router|HarnessRouter|gateB|handle,_start,_continue,_confirmation,_artisan_confirmation,_stop,status,_artifact_summary,_last_file,_save_resume_choices,_selection,_remember_route
local|maya_core/local_actions.py|maya_core.local_actions|LocalActionRouter|gateB|handle,_frontmost_app,_running_apps,_where_last_app,_volume_set,_volume_delta,_mute,_switch_app,_press_shortcut,_type_text
web|maya_core/web_actions.py|maya_core.web_actions|WebActionRouter|gateB|handle,_parse
routine|maya_core/routine_commands.py|maya_core.routine_commands|RoutineCommandRouter|gateB|handle,_handle_listing,_handle_disable,_handle_create,_clock_phrase,_weekday,_kind_from_text,_describe
project|maya_core/project_actions.py|maya_core.project_actions|ProjectActionRouter|gateB|handle,open_project,_handle_project_command,_make_readme,_summarize_project
document|maya_documents/document_actions.py|maya_documents.document_actions|DocumentActionRouter|gateB|handle,_handle_document_request,_prepend_semantic_lane,_update_markdown,_path,_remember,_artifact_preflight,_draft_markdown,_draft_with_issues,_done,_markdown_target,_open_latest_draft
everyday|maya_core/everyday_commands.py|maya_core.everyday_commands|EverydayCommandRouter|gateB|handle,_mark,_maya_desk,_open_latest_file,_latest_document,_open_latest_document,_open_latest_draft,_document_summary
file|maya_core/file_actions.py|maya_core.file_actions|FileActionRouter|gateB|handle,_parse,_resolve_path
workspace|maya_core/workspace_actions.py|maya_core.workspace_actions|WorkspaceActionRouter|gateB|handle,_create_folder,_create_project
drawing|maya_core/drawing_actions.py|maya_core.drawing_actions|DrawingActionRouter|gateB|handle,_try_gemini,_deliver
imac_workflows|maya_core/imac_workflows.py|maya_core.imac_workflows|ImacWorkflowRouter|gateB|browser,handle,handle_confirmation,_flight_start,_flight_followup,_browser_inspect,_browser_click,_click_target,_browser_state_payload,_presentation,_network_doc,_open_search
visual_workflow|maya_core/visual_workflow.py|maya_core.visual_workflow|VisualWorkflowRenderer|gateB|handle,create,_render_mermaid
desktop_file_opener|maya_core/desktop_file_opener.py|maya_core.desktop_file_opener|DesktopFileOpener|gateB|handle,_resolve,_open_file
screen|maya_core/screen_responder.py|maya_core.screen_responder|ScreenResponder|gateB|handle,_app_state_reply,_hidden_apps,_norm,_is_visible_apps_question,_requires_active_screen,_is_open_apps_question,_is_named_app_open_question,_explicit_command,_is_query,_looks_like_screen_question,_mentions_known_app,_screen_followup,_same_app,_describe,_fallback_description,_record_snapshot,_should_escalate,_confidence,_remove_confidence
vision|maya_core/vision_responder.py|maya_core.vision_responder|VisionResponder|gateB|handle,_is_query,_allowed_for_channel,_describe,_maybe_escalate_to_premium,_record_snapshot,_safe_targets,_wants_pointing,_confidence,_remove_confidence_line,_remove_repeated_see,_premium_may_help,_barcode_or_serial_target,_orientation_context
policy|maya_core/response_policy.py|maya_core.response_policy|ResponsePolicy|gate0|reply,_normalize,is_topic_break,_topic_break_reply,_greeting_reply,_presence_reply,_malay_reply,_identity_reply,_powering_reply,_channel_role_reply,_capability_reply,_improvement_reply,_scope_reply,_goal_reply,_needs_reply
model_lanes|maya_core/assistant_model_lanes.py|maya_core.assistant_model_lanes|ModelLanes|gate0|build_imac_fast_responder,build_harness_planner,should_use_artisan_path,artisan_lane,should_use_pulse_path,should_use_source_research_path,should_use_complex_path,should_use_plan_path,should_use_steward_path,complex_response,complex_plan_response,artisan_response,_artisan_build_brief,steward_response,post_implementation_review,pulse_response,source_research_response,_prompt
telegram_commands|maya_telegram/telegram_commands.py|maya_telegram.telegram_commands|<module>|gate0|parse_command,bot_commands,command_to_text,_remember_text,_create_skill_text,_complex_text,_artisan_text,_screen_text,_screen_command_text,_imac_text,_memory_text,_weekly_text,_join_text,_leave_text,_meet_status_text
telegram_reliability|maya_telegram/telegram_reliability_commands.py|maya_telegram.telegram_reliability_commands|<module>|gate0|reliability_text,_record_reliability_note,_reliability_note_parts,_append_reliability_note,_reliability_soak_path
context_command|maya_core/assistant_context_helpers.py|maya_core.assistant_context_helpers|<module>|gate0|handle_context_command
document_html|maya_documents/document_actions_html.py|maya_documents.document_actions_html|DocumentHtmlMixin|gateB|_create_markdown,_create_html,_html_draft,_html_fallback,_markdown_content
document_word|maya_documents/document_actions_word.py|maya_documents.document_actions_word|DocumentWordMixin|gateB|_create_recent_questions_word,_create_word,_build_word_doc,_word_quality,_repair_word_doc,_edit_latest_document,_simple_word_edit
document_office|maya_documents/document_actions_office.py|maya_documents.document_actions_office|DocumentOfficeMixin|gateB|_edit_latest_powerpoint,_restore_failed_edit,_create_powerpoint,_done_powerpoint,_attach_powerpoint
document_excel|maya_documents/document_actions_excel_mixin.py|maya_documents.document_actions_excel_mixin|DocumentExcelMixin|gateB|_edit_latest_excel,_edit_latest_excel_simple,_finish_excel_edit,_create_excel,_create_saas_tracker,_create_testing_comparison,_create_task_tracker,_create_budget_workbook,_create_species_or_generic_workbook,_generic_excel_rebuilder,_finish_excel,_excel_quality
human_browser|maya_browser/browser_workflows.py|maya_browser.browser_workflows|HumanBrowserWorkflowRouter|gateB|browser,handle,handle_confirmation,_start,_status,_inspect,_filter_followup,_fill,_click,_stop,_click_target,_click_search_result_fallback,_task,_save,_add_step,_set_pending,_current_browser_state_payload,_injected_page_guard
"""


DEFAULT_ROWS = """
assistant|both|entrypoint dispatch and downstream gates|gate_at_callsite|RC-G0|true text entrypoint
assistant_routes|both|entrypoint dispatch and downstream gates|gate_at_callsite|RC-G0|secondary route orchestrator
assistant_commands|both|W7 kernel or confirmation or disclosure guard|gate_internal|RC-GA|command router surface
learning|both|owner-authored memory provenance gate|gate_internal|RC-GB-LEARN|learning and memory route
harness|both|harness confirmation and approval binding|gate_internal|RC-GB-HARNESS|persistent workflow route
local|effect|local iMac action policy|gate_internal|RC-GB-LOCAL|desktop control route
web|effect|web action policy|gate_internal|RC-GB-WEB|browser navigation route
routine|both|routine command policy|gate_internal|RC-GB-ROUTINE|routine route
project|both|project path and write policy|gate_internal|RC-GB-PROJECT|project route
document|both|document path QA and disclosure gates|gate_internal|RC-GB-DOCUMENT|artifact route
everyday|both|document delivery and local open gates|gate_internal|RC-GB-EVERYDAY|everyday shortcut route
file|effect|safe path and write policy|gate_internal|RC-GB-FILE|file write route
workspace|effect|workspace path policy|gate_internal|RC-GB-WORKSPACE|workspace creation route
drawing|effect|Maya workspace artifact path|gate_internal|RC-GB-DRAWING|drawing artifact route
imac_workflows|both|browser workflow confirmation and action policy|gate_internal|RC-GB-IMAC|iMac workflow route
visual_workflow|effect|Maya workspace artifact path|gate_internal|RC-GB-VISUAL|visual workflow artifact route
desktop_file_opener|both|desktop file delivery policy|gate_internal|RC-GB-FILEOPEN|desktop file open route
screen|both|screen sight permission and disclosure gate|gate_internal|RC-GB-SCREEN|screen responder route
vision|both|guided sight permission and disclosure gate|gate_internal|RC-GB-VISION|vision responder route
policy|disclosure|curated non-effect reply only|gate_internal|RC-G0-POLICY|policy responder route
model_lanes|disclosure|model lanes cannot authorize effects|gate_at_callsite|RC-G0-MODEL|model responder route
telegram_commands|both|direct command gates and destination policy|gate_internal|RC-G0-COMMAND|slash command conversion and direct command effects
telegram_reliability|both|reliability scorecard disclosure and soak note write policy|gate_internal|RC-G0-COMMAND|Telegram reliability scorecard and note command
context_command|disclosure|private disclosure policy|gate_internal|RC-G0-CONTEXT|direct context command path
document_html|effect|document path and QA gates|gate_internal|RC-GB-DOC-MIXIN|HTML and Markdown artifact mixin
document_word|effect|document path QA and edit gates|gate_internal|RC-GB-DOC-MIXIN|Word artifact mixin
document_office|effect|document path QA and edit gates|gate_internal|RC-GB-DOC-MIXIN|PowerPoint artifact mixin
document_excel|effect|document path QA and edit gates|gate_internal|RC-GB-DOC-MIXIN|Excel artifact mixin
human_browser|both|browser workflow confirmation and injected page guard|gate_internal|RC-GB-HUMAN-BROWSER|nested human browser workflow router
"""


OVERRIDE_ROWS = """
assistant._sync_router|inert|none|not_applicable|RC-G0|dependency wiring only
assistant_commands._handle_context_window|disclosure|private disclosure policy|gate_internal|RC-GA-CONTEXT|context status is disclosure unless proven mutating
assistant_commands._handle_task_listing|disclosure|private disclosure policy|gate_internal|RC-GA-LIST|task listing discloses stored state
assistant_commands._handle_preference_listing|disclosure|private disclosure policy|gate_internal|RC-GA-LIST|preference listing discloses stored state
assistant_commands._handle_skill_listing|disclosure|private disclosure policy|gate_internal|RC-GA-LIST|skill listing discloses stored capability state
assistant_commands._handle_self_heal_status|disclosure|private disclosure policy|gate_internal|RC-GA-LIST|self heal status discloses internal state
assistant_commands._handle_memory_lookup|disclosure|private disclosure policy|gate_internal|RC-GA-MEMORY|memory lookup discloses stored memory
assistant_commands._handle_memory_forget|effect|memory delete policy|gate_internal|RC-GA-MEMORY|memory forget deletes persisted memory
assistant_commands._handle_send_to_telegram|both|private disclosure plus confirmation|gate_internal|RC-GA-SEND|external Telegram send path
assistant_commands._handle_task_deletion|effect|task delete policy|gate_internal|RC-GA-TASK|task deletion mutates state
assistant_commands._handle_unsupported_action|effect|skill scaffold confirmation|gate_internal|RC-GA-SKILL|unsupported action can queue scaffold
assistant_commands._resolve_confirmation|effect|confirmation binding|gate_internal|RC-GA-CONFIRM|generic confirmation resolver
learning._visible_lesson|inert|none|not_applicable|RC-GB-LEARN|visibility predicate only
learning._verified|inert|none|not_applicable|RC-GB-LEARN|postcondition check only
learning._explicit_lesson|inert|none|not_applicable|RC-GB-LEARN|parse helper only
learning._implicit_lesson|inert|none|not_applicable|RC-GB-LEARN|parse helper only
learning._is_direct_test_fact|inert|none|not_applicable|RC-GB-LEARN|parse helper only
learning._normalize_rule|inert|none|not_applicable|RC-GB-LEARN|normalization helper only
learning._decision|inert|none|not_applicable|RC-GB-LEARN|confirmation text parser only
learning._is_lesson_inspection|inert|none|not_applicable|RC-GB-LEARN|parse helper only
learning._preference_key|inert|none|not_applicable|RC-GB-LEARN|key helper only
harness._remember_route|inert|none|not_applicable|RC-GB-HARNESS|route bookkeeping only
local._frontmost_app|disclosure|local state disclosure policy|gate_internal|RC-GB-LOCAL|frontmost app readout
local._running_apps|disclosure|local state disclosure policy|gate_internal|RC-GB-LOCAL|running apps readout
local._where_last_app|disclosure|local state disclosure policy|gate_internal|RC-GB-LOCAL|last app status readout
web._parse|inert|none|not_applicable|RC-GB-WEB|parse helper only
routine._clock_phrase|inert|none|not_applicable|RC-GB-ROUTINE|parse helper only
routine._weekday|inert|none|not_applicable|RC-GB-ROUTINE|parse helper only
routine._kind_from_text|inert|none|not_applicable|RC-GB-ROUTINE|parse helper only
routine._describe|inert|none|not_applicable|RC-GB-ROUTINE|format helper only
project._summarize_project|disclosure|project disclosure policy|gate_internal|RC-GB-PROJECT|project summary discloses files and notes
document._prepend_semantic_lane|inert|none|not_applicable|RC-GB-DOCUMENT|bookkeeping only
document._path|inert|none|not_applicable|RC-GB-DOCUMENT|safe path resolver helper
document._markdown_target|inert|none|not_applicable|RC-GB-DOCUMENT|target lookup helper
everyday._mark|inert|none|not_applicable|RC-GB-EVERYDAY|route bookkeeping only
everyday._latest_document|inert|none|not_applicable|RC-GB-EVERYDAY|path lookup helper
everyday._document_summary|disclosure|artifact disclosure policy|gate_internal|RC-GB-EVERYDAY|document summary readout
file._parse|inert|none|not_applicable|RC-GB-FILE|parse helper only
file._resolve_path|inert|none|not_applicable|RC-GB-FILE|path helper only
workspace._create_folder|effect|safe path policy|gate_internal|RC-GB-WORKSPACE|folder creation effect
workspace._create_project|effect|safe path policy|gate_internal|RC-GB-WORKSPACE|project creation effect
drawing._try_gemini|effect|artifact generation policy|gate_internal|RC-GB-DRAWING|drawing generation attempt
drawing._deliver|effect|artifact delivery policy|gate_internal|RC-GB-DRAWING|drawing file delivery/open
imac_workflows.browser|inert|none|not_applicable|RC-GB-IMAC|controller factory only
imac_workflows._browser_state_payload|disclosure|browser state disclosure policy|gate_internal|RC-GB-IMAC|browser state payload readout
imac_workflows._click_target|inert|none|not_applicable|RC-GB-IMAC|click target parser only
visual_workflow._render_mermaid|effect|execution broker write profile|gate_internal|RC-GB-VISUAL|renderer command and file output
desktop_file_opener._resolve|inert|none|not_applicable|RC-GB-FILEOPEN|file candidate resolver helper
desktop_file_opener._open_file|effect|desktop file open policy|gate_internal|RC-GB-FILEOPEN|opens local file
screen._norm|inert|none|not_applicable|RC-GB-SCREEN|normalization helper only
screen._is_visible_apps_question|inert|none|not_applicable|RC-GB-SCREEN|parse helper only
screen._requires_active_screen|inert|none|not_applicable|RC-GB-SCREEN|gate predicate only
screen._is_open_apps_question|inert|none|not_applicable|RC-GB-SCREEN|parse helper only
screen._is_named_app_open_question|inert|none|not_applicable|RC-GB-SCREEN|parse helper only
screen._explicit_command|inert|none|not_applicable|RC-GB-SCREEN|parse helper only
screen._is_query|inert|none|not_applicable|RC-GB-SCREEN|parse helper only
screen._looks_like_screen_question|inert|none|not_applicable|RC-GB-SCREEN|parse helper only
screen._mentions_known_app|inert|none|not_applicable|RC-GB-SCREEN|parse helper only
screen._screen_followup|inert|none|not_applicable|RC-GB-SCREEN|parse helper only
screen._same_app|inert|none|not_applicable|RC-GB-SCREEN|comparison helper only
screen._confidence|inert|none|not_applicable|RC-GB-SCREEN|confidence parser only
screen._remove_confidence|inert|none|not_applicable|RC-GB-SCREEN|output cleanup helper only
vision._is_query|inert|none|not_applicable|RC-GB-VISION|parse helper only
vision._allowed_for_channel|inert|none|not_applicable|RC-GB-VISION|permission predicate only
vision._safe_targets|disclosure|visual disclosure policy|gate_internal|RC-GB-VISION|filters visual target disclosure
vision._wants_pointing|inert|none|not_applicable|RC-GB-VISION|parse helper only
vision._confidence|inert|none|not_applicable|RC-GB-VISION|confidence parser only
vision._remove_confidence_line|inert|none|not_applicable|RC-GB-VISION|output cleanup helper only
vision._remove_repeated_see|inert|none|not_applicable|RC-GB-VISION|output cleanup helper only
vision._premium_may_help|inert|none|not_applicable|RC-GB-VISION|escalation predicate only
vision._barcode_or_serial_target|inert|none|not_applicable|RC-GB-VISION|private target predicate only
vision._orientation_context|disclosure|preference disclosure policy|gate_internal|RC-GB-VISION|reads saved orientation preference
model_lanes.build_imac_fast_responder|inert|none|not_applicable|RC-G0-MODEL|model factory only
model_lanes.build_harness_planner|both|planner prompt quarantine and kernel gate|gate_at_callsite|RC-G0-MODEL|constructs planner callable
model_lanes.should_use_artisan_path|inert|none|not_applicable|RC-G0-MODEL|route predicate only
model_lanes.artisan_lane|inert|none|not_applicable|RC-G0-MODEL|label helper only
model_lanes.should_use_pulse_path|inert|none|not_applicable|RC-G0-MODEL|route predicate only
model_lanes.should_use_source_research_path|inert|none|not_applicable|RC-G0-MODEL|route predicate only
model_lanes.should_use_complex_path|inert|none|not_applicable|RC-G0-MODEL|route predicate only
model_lanes.should_use_plan_path|inert|none|not_applicable|RC-G0-MODEL|route predicate only
model_lanes.should_use_steward_path|inert|none|not_applicable|RC-G0-MODEL|route predicate only
model_lanes._prompt|disclosure|prompt context disclosure policy|gate_at_callsite|RC-G0-MODEL|assembles memory and skill context into model prompt
telegram_commands.parse_command|inert|none|not_applicable|RC-G0-COMMAND|slash parser only
telegram_commands.bot_commands|inert|none|not_applicable|RC-G0-COMMAND|Telegram command metadata only
telegram_commands._remember_text|inert|none|not_applicable|RC-G0-COMMAND|rewrites passthrough memory text only
telegram_commands._create_skill_text|inert|none|not_applicable|RC-G0-COMMAND|rewrites passthrough skill text only
telegram_commands._complex_text|inert|none|not_applicable|RC-G0-COMMAND|rewrites complex route text only
telegram_commands._screen_text|inert|none|not_applicable|RC-G0-COMMAND|rewrites screen route text only
telegram_commands._imac_text|inert|none|not_applicable|RC-G0-COMMAND|rewrites iMac route text only
telegram_reliability._reliability_note_parts|inert|none|not_applicable|RC-G0-COMMAND|reliability note parser only
telegram_reliability._append_reliability_note|inert|none|not_applicable|RC-G0-COMMAND|reliability note formatting helper only
telegram_reliability._reliability_soak_path|inert|none|not_applicable|RC-G0-COMMAND|reliability log path resolver only
document_html._html_draft|disclosure|model prompt disclosure policy|gate_internal|RC-GB-DOC-MIXIN|draft generation prompt path
document_html._html_fallback|disclosure|model prompt disclosure policy|gate_internal|RC-GB-DOC-MIXIN|fallback draft prompt path
document_html._markdown_content|disclosure|document content disclosure policy|gate_internal|RC-GB-DOC-MIXIN|Markdown content helper
document_word._word_quality|disclosure|artifact QA disclosure policy|gate_internal|RC-GB-DOC-MIXIN|Word QA reads artifact content
document_word._repair_word_doc|effect|document edit and QA gates|gate_internal|RC-GB-DOC-MIXIN|Word repair writes artifact
document_office._restore_failed_edit|effect|document restore gate|gate_internal|RC-GB-DOC-MIXIN|PowerPoint edit restore mutates files
document_office._done_powerpoint|both|artifact delivery policy|gate_internal|RC-GB-DOC-MIXIN|PowerPoint delivery/readout
document_office._attach_powerpoint|both|artifact delivery policy|gate_internal|RC-GB-DOC-MIXIN|PowerPoint attach/readout
document_excel._excel_quality|disclosure|artifact QA disclosure policy|gate_internal|RC-GB-DOC-MIXIN|Excel QA reads artifact content
human_browser.browser|inert|none|not_applicable|RC-GB-HUMAN-BROWSER|browser controller factory only
human_browser._task|disclosure|browser state disclosure policy|gate_internal|RC-GB-HUMAN-BROWSER|reads active browser workflow state
human_browser._save|effect|browser workflow state policy|gate_internal|RC-GB-HUMAN-BROWSER|persists browser workflow state
human_browser._add_step|effect|browser workflow state policy|gate_internal|RC-GB-HUMAN-BROWSER|records browser workflow step
human_browser._set_pending|effect|browser confirmation policy|gate_internal|RC-GB-HUMAN-BROWSER|records pending sensitive browser action
human_browser._current_browser_state_payload|disclosure|browser state disclosure policy|gate_internal|RC-GB-HUMAN-BROWSER|reads browser state payload
human_browser._injected_page_guard|disclosure|browser untrusted action guard|gate_internal|RC-GB-HUMAN-BROWSER|inspects page for injected action guard
"""


CALLSITE_ROWS = """
assistant.learning|maya_core/assistant.py|gate0|both|owner-authored memory provenance gate|gate_at_callsite|RC-G0|self.learning.handle(|learning peer before command router
assistant.harness|maya_core/assistant.py|gate0|both|harness confirmation and approval binding|gate_at_callsite|RC-G0|self.harness.handle(|harness peer before command router
assistant.commands|maya_core/assistant.py|gate0|both|command router gates|gate_at_callsite|RC-G0|self.commands.handle(|command peer from product root
assistant.vision|maya_core/assistant.py|gate0|both|guided sight permission and disclosure gate|gate_at_callsite|RC-G0|self.vision_responder.handle(|vision peer from product root
assistant.screen|maya_core/assistant.py|gate0|both|screen sight permission and disclosure gate|gate_at_callsite|RC-G0|self.screen_responder.handle(|screen peer from product root
assistant.router|maya_core/assistant.py|gate0|both|assistant route chain gates|gate_at_callsite|RC-G0|self.router.route(|fallback router peer
assistant.direct_command|maya_core/assistant.py|gate0|both|direct slash command gates|gate_at_callsite|RC-G0|command_to_text(|direct slash command before router peers
assistant.context_command|maya_core/assistant.py|gate0|disclosure|private disclosure policy|gate_at_callsite|RC-G0|handle_context_command(|direct context command peer before command router
routes.commands_inner|maya_core/assistant_routes.py|gate0|both|command router gates|gate_at_callsite|RC-G0|self.commands.handle(|command peer inside AssistantRouter
routes.commands_segment|maya_core/assistant_routes.py|gate0|both|command router gates|gate_at_callsite|RC-G0|self.commands.handle(|command peer inside Telegram segment route
routes.learning_segment|maya_core/assistant_routes.py|gate0|both|owner-authored memory provenance gate|gate_at_callsite|RC-G0|self.learning.handle(|learning peer inside Telegram segment route
routes.policy_inner|maya_core/assistant_routes.py|gate0|disclosure|curated reply only|gate_at_callsite|RC-G0|self.policy.reply(|policy peer inside AssistantRouter
routes.policy_segment|maya_core/assistant_routes.py|gate0|disclosure|curated reply only|gate_at_callsite|RC-G0|self.policy.reply(|policy peer inside Telegram segment route
routes.fast_telegram_sight|maya_core/assistant_routes.py|gate0|disclosure|destination disclosure policy|gate_at_callsite|RC-G0|fast_telegram_response(|explicit sight Telegram responder peer
routes.fast_telegram_default|maya_core/assistant_routes.py|gate0|disclosure|destination disclosure policy|gate_at_callsite|RC-G0|fast_telegram_response(|default responder peer
routes.fast_telegram_normal|maya_core/assistant_routes.py|gate0|disclosure|destination disclosure policy|gate_at_callsite|RC-G0|fast_telegram_response(|normal Telegram responder peer
routes.fast_telegram_segment|maya_core/assistant_routes.py|gate0|disclosure|destination disclosure policy|gate_at_callsite|RC-G0|fast_telegram_response(|Telegram segment responder peer
routes.fast_imac|maya_core/assistant_routes.py|gate0|disclosure|destination disclosure policy|gate_at_callsite|RC-G0|fast_imac_response(|iMac responder peer
routes.complex_plan_explicit|maya_core/assistant_routes.py|gate0|both|planner quarantine and kernel gate|gate_at_callsite|RC-G0|self.model_lanes.complex_plan_response(|explicit complex planner route
routes.complex_plan_imac|maya_core/assistant_routes.py|gate0|both|planner quarantine and kernel gate|gate_at_callsite|RC-G0|self.model_lanes.complex_plan_response(|iMac complex planner route
routes.complex_explicit|maya_core/assistant_routes.py|gate0|disclosure|model responder disclosure policy|gate_at_callsite|RC-G0|self.model_lanes.complex_response(|explicit complex response route
routes.complex_imac|maya_core/assistant_routes.py|gate0|disclosure|model responder disclosure policy|gate_at_callsite|RC-G0|self.model_lanes.complex_response(|iMac complex response route
routes.artisan|maya_core/assistant_routes.py|gate0|both|artisan approval and execution gates|gate_at_callsite|RC-G0|self.model_lanes.artisan_response(|artisan route
routes.steward|maya_core/assistant_routes.py|gate0|disclosure|review output disclosure policy|gate_at_callsite|RC-G0|self.model_lanes.steward_response(|steward route
routes.source_imac|maya_core/assistant_routes.py|gate0|disclosure|source-aware disclosure policy|gate_at_callsite|RC-G0|self.model_lanes.source_research_response(|iMac source research route
routes.source_telegram|maya_core/assistant_routes.py|gate0|disclosure|source-aware disclosure policy|gate_at_callsite|RC-G0|self.model_lanes.source_research_response(|Telegram source research route
routes.pulse|maya_core/assistant_routes.py|gate0|disclosure|news responder disclosure policy|gate_at_callsite|RC-G0|self.model_lanes.pulse_response(|pulse route
"""


FIX_ROWS = """
relayed_content_owner|Relayed external content inherited owner_text|regression-pinnable|memory_relayed_content_provenance_smoke and router conformance
mcp_call_action_type|Broad mcp.call dangerous action_type bypass|regression-pinnable|security_reliability_matrix_smoke
skill_scaffold_private|Private-disclosure skill scaffold bypass|regression-pinnable|security_reliability_matrix_smoke
rewrite_swallow|Rewrite candidate swallowed relayed untrusted content|regression-pinnable|telegram_rewrite_context_smoke
document_edit_route|Document-edit routing gap|manual-or-regression|document route conformance
approval_boundary|Room Telegram approval boundary|manual-or-regression|approval source smokes and live proof
recovered_masks_work|Recovered reliability incident masking unfinished work|regression-pinnable|security_reliability_matrix_smoke
"""


def scope_inventories() -> tuple[ScopeInventory, ...]:
    return tuple(_parse_scope(line) for line in _lines(SCOPE_ROWS))


def route_surfaces() -> tuple[RouteSurface, ...]:
    scopes = {scope.scope_id: scope for scope in scope_inventories()}
    defaults = {scope_id: values for scope_id, *values in (_split(line) for line in _lines(DEFAULT_ROWS))}
    overrides = {key: values for key, *values in (_split(line) for line in _lines(OVERRIDE_ROWS))}
    surfaces: list[RouteSurface] = []
    for scope in scopes.values():
        default = defaults[scope.scope_id]
        for method in scope.methods:
            key = f"{scope.scope_id}.{method}"
            values = overrides.get(key, default)
            classification, gate, placement, test_id, reason = values
            surfaces.append(RouteSurface(
                surface_id=f"{scope.scope_id}.{method}",
                module_path=scope.module_path,
                qualname=f"{scope.module_name}.{scope.class_name}.{method}",
                layer=scope.layer,
                classification=classification,
                required_gate=gate,
                gate_placement=placement,
                conformance_test_id=test_id,
                justification=reason,
            ))
    return tuple(surfaces) + callsite_surfaces()


def callsite_surfaces() -> tuple[RouteSurface, ...]:
    rows = []
    for line in _lines(CALLSITE_ROWS):
        surface_id, module_path, layer, kind, gate, placement, test_id, _marker, reason = _split(line)
        rows.append(RouteSurface(surface_id, module_path, surface_id, layer, kind, gate, placement, test_id, reason))
    return tuple(rows)


def fix_register() -> tuple[FixRegisterEntry, ...]:
    return tuple(FixRegisterEntry(*_split(line)) for line in _lines(FIX_ROWS))


def validate_registry(surfaces: tuple[RouteSurface, ...] | None = None) -> list[str]:
    surfaces = surfaces or route_surfaces()
    issues: list[str] = []
    seen: set[str] = set()
    for item in surfaces:
        if item.surface_id in seen:
            issues.append(f"duplicate surface: {item.surface_id}")
        seen.add(item.surface_id)
        if item.classification not in CLASSIFICATIONS:
            issues.append(f"{item.surface_id}: bad classification {item.classification}")
        if item.gate_placement not in GATE_PLACEMENTS:
            issues.append(f"{item.surface_id}: bad gate placement {item.gate_placement}")
        if item.classification in ACTIVE_CLASSIFICATIONS:
            if item.required_gate in {"", "none"}:
                issues.append(f"{item.surface_id}: active surface has no gate")
            if item.gate_placement == "not_applicable":
                issues.append(f"{item.surface_id}: active surface missing gate placement")
            if not item.conformance_test_id:
                issues.append(f"{item.surface_id}: missing conformance test id")
    return issues


def source_inventory_issues(root: Path | str = ".") -> list[str]:
    root = Path(root)
    issues: list[str] = []
    for scope in scope_inventories():
        path = root / scope.module_path
        actual = _class_methods(path, scope.class_name)
        expected = set(scope.methods)
        if actual != expected:
            missing = sorted(actual - expected)
            stale = sorted(expected - actual)
            if missing:
                issues.append(f"{scope.scope_id}: unclassified methods {missing}")
            if stale:
                issues.append(f"{scope.scope_id}: stale classified methods {stale}")
    return issues


def callsite_marker_issues(root: Path | str = ".") -> list[str]:
    root = Path(root)
    grouped: dict[tuple[str, str], int] = {}
    for line in _lines(CALLSITE_ROWS):
        _surface_id, module_path, *_middle, marker, _reason = _split(line)
        grouped[(module_path, marker)] = grouped.get((module_path, marker), 0) + 1
    issues: list[str] = []
    for (module_path, marker), expected_count in grouped.items():
        text = (root / module_path).read_text(encoding="utf-8")
        count = text.count(marker)
        if count != expected_count:
            issues.append(f"{module_path}: marker {marker!r} count {count} != {expected_count}")
    return issues


def _parse_scope(line: str) -> ScopeInventory:
    scope_id, module_path, module_name, class_name, layer, methods = _split(line)
    return ScopeInventory(scope_id, module_path, module_name, class_name, layer, tuple(methods.split(",")))


def _class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if class_name == "<module>":
        return {
            item.name for item in tree.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name != "__init__"
            }
    raise AssertionError(f"{class_name} not found in {path}")


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def _split(line: str) -> list[str]:
    return [part.strip() for part in line.split("|")]
