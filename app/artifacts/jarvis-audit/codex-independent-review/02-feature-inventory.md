# Independent Jarvis audit checkpoint — 2026-10-19 IST

Pinned `claude`: `36fbf3ce925080f7f54afa87eaf1d9b88414142d`. Isolated branch `codex-review`. This package reports actual execution, not a certification of the entire assistant.

All discovered first-party modules follow. Imports and symbols are in source-inventory.json. Status is **discovered**, not live verified. Consult the test matrix for executed behavior; absence of a matching test remains a gap.

| Module | Bytes | SHA-256 | Interfaces |
|---|---:|---|---|
| jarvis/__init__.py | 50 | 19a56bfd9efb33135b7a7c0b431268d2a4ffe8f72d51eed1fe8d4fb7201d33ca |  |
| jarvis/_vendor/__init__.py | 86 | 61e5749fb1c7013ef5c41c28cfe85394e64a352317fb4f7d6f745cffa9fad505 |  |
| jarvis/_vendor/deerflow_contracts.py | 7534 | 48940df7c9bb32a9e2217718bf647ce67450010cf86956debb2751f16c010c21 | _escape_tag_match, _neutralize_boundary_tokens, neutralize_untrusted_tags, receipt_id, format_citation, parse_citations |
| jarvis/_vendor/ui_tars_action_parser.py | 1659 | 849ac865a78c540d6d1f211fbd37ebdb8c5a653e26cb0328eb0b560d74bd3333 | parse_action |
| jarvis/ability_runner.py | 7622 | f0a38549f355358ad7e646f1a1fd2a1fd3dd0aa2f3ed9edbd61d21a3cf33479c | Refused, real, inside, guard, main |
| jarvis/actions.py | 111741 | df936abcb0cea1e97198857f6e7d167367584aa23fded1ea77378f3b64a6ed41 | Desktop, media_session_open, Actions |
| jarvis/agent_cli.py | 4365 | c204c75ffd0161219b7184b00a66d98c3bc72da3b4045b0111462712ccde9b87 | main |
| jarvis/agent_context.py | 10290 | 0100c958fc9cb3ddafe9a9be2c695e480ffaff70105359a2d405da1d237fe9cf | scoped, bounded_text, instruction_context, skill_catalog, selected_skills, repository_map, coding_context, learned_abilities, learned_references, compact_context |
| jarvis/agent_events.py | 4905 | 62ae3ae1e3c264dc444300ff12403b1baa0f279d84c5ed903b3961ec4c1340c6 | lifecycle_tools, lifecycle_metadata, runtime_base, check_policy, event |
| jarvis/agent_session.py | 19088 | 616493bb777d89d56e72601cc07738aaa949549ffcee6971e99e9e539f8e9d2a | missing_observations, ReadActions, AgentSession, OllamaProvider |
| jarvis/agent_tools.py | 16247 | 70393eb481e7356d033c0090570f637d5fe24ee99496d4bf30f6df81b09ad0bf | git_read, execute |
| jarvis/anticipation.py | 24961 | 91c84412fe9f5e25be0d4d11ebb6a95bb4115f1e89df301c7b8b678c6fed1842 | command, settings, safe_topic, request_signal, window_signal, Anticipation |
| jarvis/anticipation_worker.py | 6100 | eb5919c2b205354cb2938b2c91b89c03f65bec7b9e1cecd1bbbfb093088c4841 | public_url, search, synthesize, prepare, main |
| jarvis/app_adapters.py | 42548 | d74c4aa219839cac94532db6f5bbd09d6338d8e5867d94b862c139253265832b | scoped_path, settings, _root, _arguments, _sha256, _checked_file, package_features, part_hash, docx_text, interpreter, worker, _temporary, backup, _state, commit, _approve, _result, _cells, _sheet, verify_cells, office_xlsx, _edits, verify_document, office_docx, _pages, pdf_document, _stop_owned, office_automation, blender_executable, resource_budget, _blender, blender_task, unreal_task, vscode_paths, vscode, vscode_cli, execute |
| jarvis/app_knowledge.py | 33241 | d20f195f90d19ab1f46a36dc0ab15571448aeed61f68d484045d08d7628fa622 | _exe_name, profile_for, category_of, _executable, inventory, AppKnowledge |
| jarvis/application_discovery.py | 3130 | b2c2849f4bd38c5cc7a1cf31104ad29428c780e848686d46776ed0ffb1f61883 | matches, foreground, inspect |
| jarvis/audio.py | 18679 | d185137f417a1347b58387492dec9970610425b475d865f6b25454592e750497 | workers_alive, DecodeJob, DecodeQueue, command_text, TranscriptAssembler, Listener |
| jarvis/autoresearch.py | 18645 | 483e460b3945826667cdb6b237fae08c646c24f5ee292629cbf1b669e1c38247 | ExperimentCancelled, _gate_class, AutoResearch |
| jarvis/azr_dataset.py | 6086 | 51ca61383f90e88d9a769345eeba196495b4a274b426cd6ffbf330c664680585 | generate, build, write, load |
| jarvis/azr_proposer.py | 9674 | c874aad65453fdf992ccff4d9f99281b08e187fe19085825f7e0eee15e828eb2 | ollama, validate_deduction, abduction_from, validate_induction, Proposer |
| jarvis/azr_reward.py | 3154 | 84946064bf930837c0d5833e9efb7ce3397dd57f5197f486dbf69e23b660e223 | score_symbolic, score_induction_batch, score_all |
| jarvis/azr_sandbox.py | 5528 | 8f86488034a1f0ce1302e845e75398e06d11b52f775787c3fac1214f6b826340 | SandboxUnavailable, run_programs |
| jarvis/azr_tasks.py | 22778 | 7862b492964de7a43af538809993465adb4686d1cae11482ab0112925f223481 | ExecutionError, canonical, apply, execute, random_state, random_call, deduction_task, abduction_task, with_dependencies, resources, program_input, induction_task, parse_json_answer, check_deduction, topological_orders, check_abduction, extract_code, screen_program, task_id, signature, render_prompt, render_target |
| jarvis/brain.py | 119430 | 405dcc5b37d5d86cd81ae20367439429690a09179e9158c396a3d6b2f4ab5415 | RepeatedAction, navigation_step, replannable, validate_plan, normalize_plan, ground_file_scope, spotify_media_plan, youtube_search_plan, explicit_app_launch_plan, explicit_file_plan, explicit_command_plan, BrainClient, Brain |
| jarvis/brain_worker.py | 63677 | 3166a66e0a18e7deb99ac597266298e3d39f0803e5b1ef07f665042fec994ddd | Models |
| jarvis/browser.py | 2093 | 7c96d385c3c317ca74470840d1ee882f8fb20e39021c036721f3eccb139eb3a5 | url_for, browser_args, music_search_url |
| jarvis/browser_automation.py | 2362 | a32e04639c166080763a0b1863dfb581dfbf73d3ec2aa967f064c798331ad8c6 | BrowserAutomation |
| jarvis/browser_cursor.py | 2738 | bbe48d66ed0557b95f94c42754017fee530f972dc0b9f0aa406649590848014b | click |
| jarvis/browser_worker.py | 33879 | f5c5275c921a39901d90e81e617417425d5f00912cf3cb5a891e9c71381989e3 | parsed, player_message, reveal_controls, validate_request, validate_summary, Session, main |
| jarvis/buddy_engine.py | 15756 | c07ff6f60c49565418192721202ebd1f742e441fb4c2601d5d6035289125737a | categorize, foreground, idle_seconds, Buddy, look_at |
| jarvis/capabilities.py | 21722 | 940d23e1f0b9986f90e9dd192c96a838735ee03728256a9684e4138652498268 | tokens, relevant_tool, intents, gmail_readiness_question, _description_tokens, skill_ranking, skill_score, skill_tools, rank_tools, launch_target, program_matches, runtime_context, sync_note |
| jarvis/capability_guide.py | 12655 | b52c24067a642c2989707ae9637e0723f4f78a8a6f3c61ad1d58a388c650c8ea | capabilities_text, area_help, health_path, apis_text, live_realtime, check_apis, parse_command, answer |
| jarvis/catalog.py | 5882 | 75578c150545599d45c1169469892fa37d94d2afd0e0b83815d5831e297b0b9b | AmbiguousName, key, Catalog |
| jarvis/clarification.py | 1529 | 6ec3fecc4161a04187d971db5c173e48fa306947a9731cbd58e7ca91b4081b5d | TaskClarification, choice_index, short_reply |
| jarvis/claude_code.py | 15881 | 26c9ae53a8a8accbfd676349c37a1b263de51d970e3fa0f926881b25c4432a2d | display_text, executable, environment, event_progress, run |
| jarvis/claude_code_guard.py | 2744 | 2cfd02dc32cde1a1d3c30fd1ee2dddaec9c8267668cbce8bb562679a3e313415 | gui_script_target, decide |
| jarvis/claude_code_permissions.py | 4832 | a889b1e19ab4b0b368efef765c9d517b628d48cb44fe0be0e41e021d2153b9bc | approve, main |
| jarvis/claude_code_proxy.py | 3720 | 1297cceafda188a9dad04778d7b62efdac977410964a7b449ea518c8978a0e43 | prepare, serve |
| jarvis/cloud_architect.py | 22223 | 7ab4d2edc8cd85ff422e54907ceefcf1abacccea4d018c1848d661eeabef8d33 | now, internal_terms, PrivacyRejected, privacy_gate, ConsentStore, eligibility, screen_code, verify_in_sandbox, CloudArchitect, consult_tool |
| jarvis/cloud_cli.py | 1818 | 193551a672f77899259ab3deaee0380fb6751cecb2e3247e327fb717229d8e27 | main |
| jarvis/cloud_policy.py | 7414 | 10f056d2369085c9f2722ffbd66227e88874c2bd2807226bd692d66f3b58a9d1 | settings, credential, privacy_text, classify, screen_payload |
| jarvis/cloud_quota.py | 10330 | 4f5aa42edb8f16f12a3907ad754218185020f2c95b245ada98bd279708dc449f | QuotaDenied, duration, QuotaGuardian |
| jarvis/code_context.py | 8219 | dfd9e0b1eb46862efa4194b2fd141e867254908365aab0ae6974b8d8048d05ff | related_context, bounded_references, save_change_review, apply_replacements, check_python_interfaces |
| jarvis/code_stream.py | 7456 | 4d2e4b9c45aa9490a4f03cfcdfc510b64407965ce713fd9fe3b1c4ef31e1c077 | content_prefix, record_path, owned_draft, CodeDraft |
| jarvis/coder.py | 45051 | 429fb79b3d416017912acdd6b1eff079edc01c65c4b077b5b4370e0faa677e7b | python_file_request, named_folder_request, folder_matches_request, coding_folder, workspace_coding_request, explicit_coding_intent, simple_folder_request, requested_new_folder, single_python_target, calculator_template, test_calculator, create_python_from_goal, project_files, relative_parts, strip_project_prefix, target_path, draft_content, check_content, comment_markdown_preamble, generate_checked, Coder |
| jarvis/codex_browser_check.py | 14620 | ef3f95473e08ff66fbe98ac36f342ee687053309ceb90433d7e98cc8e5b7d6f1 | run |
| jarvis/codex_code.py | 30285 | c9d6def684e20963a67dffab46cf9abf59136d6003d96d0e0aad2580ab3358e5 | executable, environment, configuration, event_progress, changed_sources, _turn, run |
| jarvis/codex_files.py | 16721 | 193aeaae719a2a3406a47e28e3f71fd367ab5a33f3ee24d947edea3df7095585 | check_component_markup, digest, execute, tool_specs, main |
| jarvis/codex_proxy.py | 22066 | 3d28977b496fe0aaa97c9fe56beed6145ae3e5ef2d86912c47b71d37a6bb6554 | prepare, worker_scope, python_context, tested_peer_styles, validate, restore, serve |
| jarvis/codex_validation.py | 28608 | 236a37608283e746869c4f35835c13d78335d3b0c61562f35610a8dd1455d267 | source_path, fullstack, desktop_gui_target, contract, declare, placeholders, References, inspect, execute_check, test_evidence, retain_rejected_javascript, validate_project, repair_packet, error_summary |
| jarvis/codex_workload.py | 54674 | fe5e940d5344376442394bb990bc8eb8cfcc00dad09209813b1ed8b1922d85c3 | localgithub, planning_schema, proposal_diagnostics, static_assignment, explicit_browser_steps, single_python_source_goal, graphical_python_goal, complete_single_test_ownership, collapse_unowned_split, workload_contract, propose, fingerprint, promote, run |
| jarvis/coding_activity.py | 1664 | 5c7fc634a828a10717dadfb1a908090a9b4d6dd94054b5835e0a213646b4880b | emit, Activity, review |
| jarvis/coding_console.py | 5387 | 4c9d04e602687df95070c56ddc7f7b892097626b767b56fa391ff24457093f1c | CodingConsole |
| jarvis/coding_curriculum.py | 22206 | a20cefc387bca2e3be36b86e5628ec9335c5c419f9d24efc929ab2f6835aaca5 | fib, roman, intervals, rle, brackets, factor, edit, lcs, coins, knapsack, lis, maxsum, reachable, distance, dijkstra, topo, components, flatten, merge, business, cache, gridcost, rpn, catalogue |
| jarvis/coding_files.py | 9764 | a2e583b9ea202130df215ba3e356e5a213340628a6026897f76a1227f235a668 | UncertainCoding, patch_files, FileSession |
| jarvis/coding_languages.py | 9209 | 5a781722de948b9717f9f7d61460c590127dc43a8ddf444634618f4f1a860385 | context, Scripts, check_source, evidence_label |
| jarvis/coding_lessons.py | 8618 | 33d62a76220fc87f6c863a57328215cc14218e1b07b6da21c8613407665ccd46 | record, recall, related_cases, check_learned_imports |
| jarvis/coding_operations.py | 3369 | 275cc48756fa7cfac1bd2b5474b5d50345d69ea0e7a352c934b1b6a2c93b6071 | execute |
| jarvis/coding_processes.py | 5096 | 6bd01e7599da24b5eccdeecb178d0ae6fa03e299d883cf81e61be2d92f236724 | Processes |
| jarvis/coding_programs.py | 9475 | a7c04063551d56e2fd9d5b21414d899119bbd807890946bb3b09637cf0a186e8 | locate, inventory, checked_argv |
| jarvis/coding_training_data.py | 2276 | 120563c4b2dca3e19851c5394867659f2458124f468be36394b10eef8f1f78f2 | reference_source |
| jarvis/cognition.py | 40797 | 8ad33e2b0518c2ece3f23fc2d9ddc1b04abed27d84dc2cbf37af76bfc11af95e | recipient, describe, effect_of, Percept, Cognition, _seconds |
| jarvis/command_cleanup.py | 9738 | 403470847d3158e3a1141e192161d4a665f63b47e2002fe54fdbdff15125187f | proposal_payload, chosen_text, settings, allowed_edit, propose, stream_json, _stream_json, CommandCleanup |
| jarvis/command_reference.py | 6476 | 3dbc392330458e40c79881bf7800ebf3aeb6804ae87fade4dc7af696cb106922 | search |
| jarvis/commands.py | 34531 | 05162098e4b464be31b1d8404cbd6f8d49d9950e97627803cd69226c8d2054c4 | Command, normalize_spoken_code_request, filename, spoken_clean, parse, _parse_command, cloud_command, _parse |
| jarvis/config_contract.py | 2897 | be7bbd5c1910b46623d0a64d4d0a09ac2c122760d4c52c758568c81ef5976f7b | ConfigurationWarning, load_config, validate_root |
| jarvis/context_hub.py | 7080 | d865cd88a8689b79a31700482d9d5cd8e581b9dbafb74b08d448630b6fd322ba | foreground, situation, prompt_block |
| jarvis/context_selector.py | 7166 | e9c406b218b346b7c0aa3039d0c582ef9d2a9d35307dbfdc18994c516abb79c0 | settings, select_payload, select, ContextSelector |
| jarvis/conversation_intent.py | 5348 | 04b43f8118f41565c002fd305fbc279dcd4d40e1728d9144912763d142487b3f | normalize, quick_kind, model_kind |
| jarvis/conversation_memory.py | 6799 | 9a0bfe5f35ad7007a0f70e4911ac9a43d201216294e648f876cf3a8753bb34c1 | terms, messages, ConversationMemory, current_context |
| jarvis/dag_execution.py | 20148 | 20f68252fc5075c157b19da41c4e9c72d35bcd1d987aa5824af8af597d570ab9 | CapabilityError, Tool, Step, admission_order, bounded_number, bounded_payload, step_binding, references, argument_shape, validate_plan, resolve, Executor |
| jarvis/deerflow.py | 13162 | 87716b3a5b807fa3689847be5c19da4c5785b26b533ab75fe0da0b897747807d | skill_root, status, read_skill, search_skills, normalize_source_links, request, execute |
| jarvis/deerflow_cli.py | 1220 | 5f3ba3e2bb16152ad910fef9fb8a7e409e06d7f8f9a0c1b37470bfd5edd5ad07 | main |
| jarvis/deerflow_media.py | 6559 | 9b11a04018f7cca3fe2ceb9f7b96602fb01149e72082d740fb97dc99f7135097 | verify_artifacts, validate, execute |
| jarvis/deerflow_media_runner.py | 4928 | 163c6a23634794edb51910943aca9038b971066a6c205930ef0596864007d501 | render |
| jarvis/deerflow_model.py | 6249 | d6db9af2e983a21297d74b336206285d7940b213cb19a2e30c3c27709485fbc1 | JarvisChatModel |
| jarvis/deerflow_sandbox.py | 18267 | c3a0c4db6bf486eb865eab0523af6da9ef3f80ecb4aae66ed6644410507afa86 | SandboxJob, reap_orphans |
| jarvis/deerflow_worker.py | 11628 | e2b23867c855df554ef07911df7e568ce322745e2b125eb7b2894d3e52021a36 | run, main |
| jarvis/deliberation.py | 28297 | 3186cf653da1f8a8fb36832e2f1b19840c7691cfbb610d89abb65ab55ff60059 | ledger_text, valid_opinion, Deliberation, classify_failure, FailureRouter |
| jarvis/demonstration.py | 18268 | 73864baa5011a03c484ed3d89abe6bd467b8e08c51597367477764bd8b686d78 | now, MSLLHOOKSTRUCT, classify_input, HookProcess, MouseHook, describe, is_password, window_state, DemonstrationSession, promote, _hook_main |
| jarvis/desktop_actions.py | 5287 | 27d4381d8778afff2fd5bde3a8ae7010f22ebbe9d64a87712b211cc2935f2930 | shortcut_key, validate_desktop_step, explicit_desktop_plan, apply_control |
| jarvis/desktop_tasks.py | 8742 | f7ff518fcf934c12d197fd6d36709d53b3a1a7259c6d19343ed3a266c001c1dc | _process_path, close_app, write_new_file, modify_text_file |
| jarvis/development.py | 15584 | 2f8640252f25190753e7081a0d1340a035fe16f74d7a8487e19484be8042b5bd | tools_for, checkpoint, functional_tests, verify, run |
| jarvis/development_api.py | 5375 | ce548477ee34aa441b58487da28df315a334772327899fc6497ee371cf485f90 | execute |
| jarvis/development_browser.py | 12140 | f67306f92e1656fb92828100829ec99dd83971327a005cf9a930ea4fc47a3381 | preview_url, test_plan_schema, validate_tests, step, inspect |
| jarvis/development_design.py | 2981 | 175313e44d8222a3110572dd6c7b74ab08a7c4f9a1ed43006ff54dc73001130f | specification, save_spec |
| jarvis/development_knowledge.py | 3147 | d07a7d2888e7a0a30e4aaee787e57aecdb0d2cae92b33ae61c8bc4ad9a6129f5 | detect_stack, catalog, context, read |
| jarvis/development_learning.py | 7385 | 49d53ebd5a01e80845f04b5ab05a90835bc8e0b4cc041ed24f6e7a6526751c46 | fingerprint, store_path, record, recall, feedback, preferences |
| jarvis/development_native.py | 3193 | 43449f0a3e1cba41cd9fdf8fec47925e1e6327aab808066f105d7591f65d7210 | readiness, run |
| jarvis/development_projects.py | 9597 | 6aada3298387c23fc55e9f50077443801ce7f0e77e4eee0b5b77348e6985f8f4 | requested, batches, scaffold_files, scaffold |
| jarvis/development_tools.py | 11112 | f2eb3c6c8d5946f385737f8303d359d23d695bb27691835f0a1fc4e12ec936a2 | executable, binary, DevelopmentTools |
| jarvis/diagnostics.py | 2979 | b3e7b26b4964dc86366aa0fca8e48eb30af3affb012666f59f2df8b192f845be | service_status |
| jarvis/direct_execution.py | 9533 | 8923a59bac50accb146b51f100c16946c796b79ed0003d84c19ebe1c8ceccd54 | compile_steps, run, run_files |
| jarvis/display.py | 1722 | 33260fc5ce54550beb671124653ebbc15c6fb1c02a1920fdb6408b3927dc4444 | enable_high_dpi, window_scale, refresh_rate |
| jarvis/docker_runtime.py | 7040 | b8e53a68aa288219adbe5b5c9d28fa53bf298a481d9a7f0376f2d52c9958e0a2 | desktop_environment, desktop_start_lock, settings, engine_status, DockerService, start_background |
| jarvis/document_worker.py | 7963 | 2820429aaf561771752394ac0b3e00fe9945a5bb3d4b34fa2d4b4b75872ffc67 | _cell_value, xlsx_read, xlsx_write, docx_read, docx_write, pdf_inspect, pdf_text, pdf_compose, main |
| jarvis/documents.py | 42219 | 3a56ddf83a485380041d3335ed36ef4647ce75be6ed56722aa7751f04da99b39 | now_iso, terms, file_id, extract, chunk, Document, Library, parse_command, execute |
| jarvis/engine.py | 8991 | 52af3cee2c5e2e704c3b99302197cc93cc07c8bde34169b99a148a60a4ab7e11 | Engine |
| jarvis/everyday_runtime.py | 18766 | b60d1f5b617beba9aaa8e98c472b61007a841d0a60aada8c2f4698b2ac80900f | number, say, EverydayRuntime |
| jarvis/evolution_archive.py | 11256 | 40369f17310af02cdb464b8a97d2fce25e611ff34f3cfd7750b89857edfddcb9 | now, EvolutionArchive |
| jarvis/evolution_lab.py | 9265 | bf545711b7e92298989b96941c525acd7c07cf330438182b4554db27689603be | git_env, member_path, LabError, ExperimentLab |
| jarvis/evolution_promotion.py | 13203 | a70e13f22e9501bfcffd2ef0d00916cbdcf1eabb6db267abc99d2418e21d37e6 | _now, _sha, _normalize, PromotionError, EvolutionPromotion, status, execute, main |
| jarvis/evolution_surfaces.py | 8638 | 162462ec9e86a200339c43f5a9be015a65847ae4cf80e57c571071ae011fc90c | SurfaceViolation, surface, _assignment, extract, validate, render, _normalized, verify_bounded, digest, distance |
| jarvis/execution_adapters.py | 16159 | 0bb2dd65f16e74627e8ac3d313bbc5e5486db09eb08fdee773e607570c4e280c | Unsupported, access_denied, Prepared, pattern, selection, UFO, windows_patterns, WindowsMCP, CUA, OpenComputerUse, AgentS, JarvisPointer, desktop_order |
| jarvis/execution_contracts.py | 4216 | 6376d677f87fa865ea2adea300229c21e4810792baf1d1381df5600f6894271b | outcome_metadata, may_replay, record_outcome, read_outcomes |
| jarvis/execution_router.py | 6796 | 6d3b9aec0ce6fe5e2afe5830fcaf8686112522950cd088988b97fe0605e1c6b9 | validate, UncertainAction, execute |
| jarvis/execution_strategy.py | 26184 | 24f169f0d35280ed0c39ddcfec12042cf711aed8ffc15379be3c367a42e0e43d | Method, _m, files_in, Request, Candidate, ExecutionPlan, request_for, discover, _requirement, eligibility, measured, score, plan, method_for, observe, _operation, _request_from_step, strategy_tool, api_alternative, hint |
| jarvis/experience.py | 3956 | 33e40b51574789a1d76a2543a8f18a6bb50906f82d725c912f3eafa385126001 | _iso_timestamp, hotness, hotness_many, memory_score, recall_tasks |
| jarvis/experience_memory.py | 21273 | 59762bcfb3b0fba7859168b8bf2b370c5ea1637d579a030c44c326bbfbb81b13 | tokens, digest, scope, conditions, observe_conditions, failure_class, ExperienceMemory |
| jarvis/exploration.py | 17403 | 5ee0e89466a2966aedf1e52843f0636a15a4fdd0c6e76029e1c6d58495ce02d6 | now, IsolationUnavailable, desktop_environment, IsolatedBrowserEnv, BlenderSandboxEnv, Curriculum, plan_steps, Explorer |
| jarvis/f5_speech.py | 9214 | ffb3597dd1be3f0146fb60e3a07c3c56a29c0da5708ea7765453040d61977e0e | _wav_duration, reference_duration, number, reference, readiness, load_voice, chunks, render |
| jarvis/fast_workflows.py | 12170 | 775f0317a249be17519fb22f4f57289228379ddde39f529147292a27f766eeba | compile_workflow, executable, observe, search_ready, choose_result, run |
| jarvis/file_drop.py | 18223 | 10fc9d9307561c58c1b253b89bd3e879fee709c526638c1957abf391dcc4017c | DropTarget, card, describe, email_address, ChoicePrompt, ask_text, handle, ask_about, send_whatsapp, write_email, send_email, start, parse_paths |
| jarvis/firecrawl_tools.py | 2861 | f373fb7661a20e712c7251941988b3f23dcebb405b3523de6e3b9a2955b09512 | execute |
| jarvis/folder_lookup.py | 11627 | 860835e5a36fe7b79cfb247836d8c2b7daaccef6cde1926ed2a0b861d24331ad | folder_request, FolderLookup |
| jarvis/glass_ui.py | 7562 | 26bca23da864f7e2329b61dc51f1e4a86c0974e49f3be752a0ec7e99c1078925 | _glass_tile, render_glass, install_glass, GlassButton |
| jarvis/gmail_api.py | 32900 | 11159eb90d8bf7121da394b1b3a3f2d8662f54e11434ced46b50d7478d487b41 | directory, save_credentials, configured, credentials, API, identity, recipients, raw_message, attachment_message, draft_with_attachments, decode, MailText, approved, fresh_draft, run, sent_check, send_message, draft_action, label_names, modify_messages, message_summary, read_message, execute |
| jarvis/gmail_bridge.py | 4512 | 1bbe811e24754d420953c076fa94d79e8a7d8fbcedf0330201a1e2baa815b321 | GmailBridge, configured |
| jarvis/gmail_chrome_worker.py | 14118 | ae61c2d49ef20c6c1c31cb11b7f3c2c4e84292374cd23e1eb2fb7f7aa223f754 | select_compose, chrome_window, unique, guard, focus_host, activate, set_value, compose_windows, expand_compose, perform, serve |
| jarvis/gmail_workflows.py | 34939 | 6a3c0b185e2b0cd4a252fa5fc0fdaba174956260d8ed5cb3e423c3986418f533 | GmailResult, gmail_request, spoken_addresses, literal, quoted_subject, explicit_request, action_request, validate_request, sender_name, spoken_message, run_gmail, unread_request, run_unread |
| jarvis/gmail_writes.py | 3995 | 414751be503a65282fac7d437f494644fdc75d1c34a2f5dac68c9f28da6e15df | Journal, guard |
| jarvis/gods_eye.py | 55593 | e512cfd897d51af728251d4cfdc845b47f2e79984284d3d0e6448e28bbead5e4 | recent, nearby_distance, distance, bearing, parse_command, GodsEye, stop_vite, execute |
| jarvis/gods_eye_cameras.py | 9499 | d79d7dcd61fba788221cb8114f026effdeb565dd99299a4517a54cb9294e1119 | public_camera, pack_path, ontario_key, _heading, _point, toronto, ontario, configure_env, build, summary |
| jarvis/gods_eye_update.py | 4622 | b4b9edb43f48ca49cc234f94a6ff7a50d4722d764e549c36d76f79dd631a5a25 | digest, latest, update |
| jarvis/gods_eye_view.py | 2797 | 99a5ba525da5716063c7c4c1f38c79ff7a598481cb7d3455f89aac2e98497a55 | ready, GodsEyeView |
| jarvis/gpu_scheduler.py | 27789 | be3c0e0d65a510e5d9b22a61edfed1261ea06746319d8e02a59d9179b2f4f6cd | runtime_environment, request_context, model_label, validate_state, replace_state, settings, configured, memory, allocation, alive, status, Registry, Lease, install, native_turn |
| jarvis/groq_adapter.py | 12665 | 2f9354c2a83790b7f345746b1000dcab9bacefd3c9e074c2046674172074a51f | CloudFailure, GroqAdapter |
| jarvis/grounding.py | 888 | 93b2dc022fd41ff293033119197bb0e2ac0b556894f694afc75971b4deee96cb | direct_decision |
| jarvis/gui_contract.py | 6612 | 95305e1ece580c628f944be990e2090a1904bf316e8b69a4fce30ff8bc3251a2 | requested, instructions, check |
| jarvis/harness.py | 4735 | d5db908ca2833249b610a9d7205ac6030152e2781a9b149b3c534eea97cccf48 | validate_harness_proposal, validate_agent_response, readiness, HarnessClient, healthy, repair, HarnessProvider |
| jarvis/harness_process.py | 3013 | ed9943e728c614c3aae7d1f7fdfa841be9232f21dc5702c16b2e6099c331e6e5 | OwnedJob, hidden_spawn |
| jarvis/harness_worker.py | 18568 | 8619698f7fc6b87761c416b6108b404144446d25404efad58acfd94e5e29112c | audit_profile, exclusive_proposal_schema, agent_schema, Predictor, main |
| jarvis/hermes.py | 5045 | a4ab05b3636fc6237492ec2f982dd238aff6debf00de4e7e63651406caab0bc1 | readiness, validate_proposal, HermesClient |
| jarvis/hermes_ollama.py | 5356 | 44d80cc663842fbc78022375d33ac3a77a411a5781f5da8fd077e93670405dec | completion, start_provider |
| jarvis/hermes_skills.py | 11814 | 4f7327016a9beefa8faec4157def87037039de16f6526d173144b150d1a9bb28 | safe_resource, HermesSkills |
| jarvis/hermes_worker.py | 7151 | 92793fc1a3160c736807167e80a5496605497bd77a193be6369beb130fb374de | predict, main |
| jarvis/hierarchical.py | 24073 | aade8ed9866658debdcf3dee2360f3d1714e17a82675ddfef5946bfe18a61502 | settings, eligible, schema, literal_reads, legacy_step, adapters, implementation_hash, fingerprint, MacroMemory, run |
| jarvis/hud.py | 2509 | eebd44da45ab745864d3bbcff751bd19ad3be3e4dbdeee0a6e4782cdecada868 | logo_frames, render_hud |
| jarvis/hybrid_inference.py | 14209 | eaf608634b516c78f12b74b4df0f623ad92ac05a42bf09ad1f49d6f551fb18b5 | metadata_model, policy, configured, standalone_public, get_service, HybridGateway, maybe_answer, control |
| jarvis/independent_cursor.py | 9727 | a6bd230d17fd32e91975c62e5b574c30e27564bbe4ac0233a4c86fab9cf47a96 | CursorCue, at_point, physical_point, activate_point |
| jarvis/inference_limits.py | 3033 | cd75a6f21a02ea57aeb8f99740f83507181761176df4207daa61d352c480ec90 | planning_read_timeout, planning_worker_timeout, question_limits, coding_limits, planning_limits |
| jarvis/intent_catalog.py | 71201 | ba3ccf4258e716bcd5c3dda63165ae4c4d6a28e306d441919b2e070b7cf76332 | gev, cam, queued, _mail, _write, _layer, _style, match |
| jarvis/intent_handlers.py | 49931 | c84e2b724c819cda608b5d44623270832025e3b666262524486f49e6793489ca | behavior, conversation_style, filter_report, repeat_last, _ago, _ollama, jarvis_status, cognition_predict, _windows, _process_name, system_info, whatsapp_read, media_related, messenger_focus, memory_summarize, execute |
| jarvis/interface.py | 12493 | bba324c0b22ecdb0eaa6069b058837b904026a16c6f7e5104f5c71c881c6c035 | label, build_interface |
| jarvis/island.py | 50127 | a998a153b6d1bedb550b46b90d93316faa032b81eb6e293df6b0fcf62fa6c2c8 | clock_text, artwork, media_progress, font, wrap, fit_text, _fit_text, _text_tile, _curve_tiles, contour_mask, status_amplitude, media_amplitude, animate_frame, render_island, Activity, Morph, FrameClock, Island, export_preview, export_animation, export_hd_preview |
| jarvis/island_artwork.py | 2019 | 903e0697643d26936070bd7c065d0068716b3a4882f490d91397fb8890a9844f | unobscured, row_artwork |
| jarvis/island_buddy.py | 33738 | 7a64bf261108c9f2343853b2593f2f6a243f1a115609ea636621b8300ecabe53 | register, lerp, mix, blink, ease, superellipse, body_sprite, shadow_sprite, font, base_pose, pose_for, paint, body_color, heart, star, mouth, wear, badge, particles, draw_buddy, mood_for |
| jarvis/island_choices.py | 6154 | 10fd66bad7bd9ce856e6c9c22d774249ed8389e2bfe0f65f44447bf0597b150a | snapshot, resolve, navigation, task_answer |
| jarvis/island_desk.py | 32323 | 4dc1a15d030f28fa821a98897a9c7fc11bd73aadc422ee04ef1c1770eedd0ea8 | text, Approval, IslandDesk |
| jarvis/island_games.py | 10604 | 4fd43ccf52f2af340d20aeae2d06544898bcf4eb890d87fb5fc605f190dd7595 | merge, winner, best_move, Game |
| jarvis/island_media.py | 6349 | d5c069be8ef95a8c24ac5dad9e4e96b88a369a99809d8ca8a572478f471229a6 | metadata, thumbnail, MediaJobs, main |
| jarvis/island_mind.py | 10673 | a248b2b7bc18ea2f09123cd06bbbd2ba1bfdd6fea70fe3184f23e10050bb8605 | MindView |
| jarvis/island_surface.py | 6437 | fdaa0f732cc807c5be488b7193276d0286058a49e28fd8cd3a5df7437f61c1dd | AnimationTimer, EdgeSurface |
| jarvis/jarvis_pointer.py | 6153 | 677cd0bf141b262dffec02539e9b60f44abb36332da78f51ced923279f714cbd | POINTER_INFO, POINTER_TOUCH_INFO, user32, wait_for_idle_mouse, physical_pixels, tap, enabled |
| jarvis/knowledge.py | 25054 | 1b482fb40e74257cd59708928fee53980ebc318ca022d20b1d2cbb23a8538ef5 | wants_screen, Knowledge |
| jarvis/knowledge_acquisition.py | 24239 | d7ff8e16b160d9501e2d9127fd134cdc84370107335f0f1466395172db3cc85a | settings, interface_signature, safe_controls, source_rank, reconcile_source, Acquisition |
| jarvis/knowledge_worker.py | 32153 | 6b0792e5e1492e2ceb9541ebcdafb2ba216e7515f0d9fca68836f2127ef1630c | session, ensure_server, local_prompt_format, chat, search, answer_from_screen, answer, handle_request, main |
| jarvis/kokoro_speech.py | 16214 | 7ede67a84d5b6a5dc8e1c1b68c071e1be0903b393023efd1cf7f7d285acce53b | speed, synthesize, SpeedSession, load_voice, render, Player, main, raise_priority, queued_batch, serve |
| jarvis/launcher.py | 29900 | 79c7865b3220a44482c63ed003f10666d3d7f9efa8618833cc68e43edb1dc8b9 | OwnedApplication, session_heartbeat, source_snapshot, preflight, singleton, heartbeat_state, supervised_restart, runtime_command, prepare_runtime, run, check_imports, runtime_status |
| jarvis/learning_memory.py | 8067 | 0892709be600e4741742fa3988a4d57f6f28363bbdb414ef74a7ea67a6bfcacc | options, trajectory_from_task, sandbox_registry_factory, LearningMemory |
| jarvis/live_app_context.py | 5048 | 89091aef8c7d4c8176c5461169d2054e8b6a5249b646f6b8451f6422d52d33d8 | window_info, foreground_window, LiveAppContext |
| jarvis/local_embeddings.py | 1825 | de66e522f7bb197953b72fb2eadc4a522fd0f891912f083fed7a070d6da8747b | embed, normalize, cosine, status |
| jarvis/mcp_bridge.py | 12793 | 230e7b6b26807be04c164a6093dd27ef66fc2045c94ca424bb632b6f185f7a68 | configurations, _configured, StdioClient, execute |
| jarvis/mcp_synthesis.py | 20295 | 2471960bfc6d26ef475a31d5dea04e7829d522ea4f5e3c3a4dac23ce3b695324 | generated_root, registry_path, discover_existing, validate_spec, generate, screen, image_status, server_config, reap, _equal, run_tests, load_registry, save_registry, synthesize, health, unregister, configurations |
| jarvis/media_commands.py | 5917 | 950c988104e1682c88ac54f58f0dbb28db33a768e18e423776847a066ee71711 | parse_media |
| jarvis/media_player.py | 26006 | fa9e09628f98eb40bfaefde1b7360df2fb06001ba5db017a957227e367abccf9 | sound_key, similarity, _similarity, clean_query, youtube_key, iso_duration, clock_seconds, youtube_search, choose_youtube, fetch_image, card, pause_other, PlaybackUncertain, play_youtube, spotify_results, choose_spotify, spotify_window, spotify_now, play_spotify, control_text, control_card, youtube_state, active_service, resolve, play |
| jarvis/media_ui.py | 12679 | ab91b0e89c8a896a35dc9626b1a9e32686bcbe55af602a93e7bb17058ae231c2 | platform_of, find_media_handle, snapshot_for, resolve, search_current, key_for, fill_search, set_range, control |
| jarvis/memory_curator.py | 36663 | 1a91c759efba89338a8fb6d009aa50d4d46b0135eb7ce246b730130b02ff8cbb | terms, overlap, safe, subject, preference_slot, MemoryCurator, parse_command, first_person, execute, absolute_dates, guess_category, describe |
| jarvis/memory_index.py | 28145 | 5a9f7e8c8ba3db9286a1ec2d79211c1930d28a8d0f7a34f39f8ec2c1b07575ab | _tokens, _safe_line, _is_link, _summary, project_roots, discover_projects, installed_windows_apps, app_entries, tool_entries, build_index, _atomic_text, write_tools_note, write_index, load_index, context, project_matches, catalogue_answer |
| jarvis/messengers.py | 6870 | 0a7b6e0dcdb8a904afde02ff72ebb47fc7019bec7465479ce24c192f54da6281 | parse_command, _window, send, _items, send_telegram |
| jarvis/model_performance.py | 1837 | b932258669cf5714c253b1f660cd1575e053c441be2c9a9ef29d72fdd7f7b514 | PerformanceTracker |
| jarvis/model_recovery.py | 4019 | a56d4977590cf99595e2842b3cc9a78e78a93f8212129d8ac43706ed0a87fa9f | ModelRecovery |
| jarvis/model_registry.py | 3208 | 16fcac19b7dbc3a730277fd09eb5b1612e880565feb1cf4b03dcc43e647571a7 | _sha, ModelRegistry |
| jarvis/model_selection.py | 2253 | 99ce42b8025682fdbe762d869cf082e20a9d7bec7023a880b41ea0fed9477862 | required_models, installed_model |
| jarvis/names.py | 4154 | c1e1751d4d0a556ed6520a4605289e9512ec768c14bdddd35e7cb4e175dce5a0 | normalize, common, rank, spelling_score, rank_spelling |
| jarvis/native_coding.py | 25759 | cf9190757d2490b8958267d87b2b00ca1602a7822b8994fa1aea1af5bf582e61 | specifications, infer, run |
| jarvis/native_tools.py | 17068 | b48a497b7d97295aee57712cea710795377e89554bfc106219d8606b163ccbee | parameter_fields, functions, parse, estimate_tokens, conversation_key, step_update, plan |
| jarvis/natural_conversation.py | 3865 | 7decb76d1741dbb29a9d92805e87171811bc6f307db166acac60c9052d948587 | eligible, generate |
| jarvis/natural_voice.py | 16025 | fa1887f0ee0b9e4178cc26518422afc3fca3185b8037cc81d3ee085ff59df49d | Phrase, speech_unicode, number_words, ordinal_words, _number, _money, _file_name, _place, _time, speakable, tts_text, split_phrases, plan, breath, trim, finish, voice_style, language_for |
| jarvis/notch_widgets.py | 3929 | 59f6888240426408fffb099c31a4ec203772fcd982f01a20ddbb0c0b636f1dbc | RoundedCard, NotchPanel |
| jarvis/obsidian_memory.py | 16371 | 0a8a9a15ba5f8ced2868a6d424a255c18ed1bf30f301144c5ce802f36ee25863 | clean, ObsidianMemory |
| jarvis/office_com_worker.py | 5278 | ac5173bae9c3ee8318ad2c2808d862989217dc675ea0600a7267439c7462f594 | _owned_pid, excel_write, word_write, main |
| jarvis/ollama_models.py | 9802 | 084a32b59a018ba80a5cad0a4424b351f452c71530b02394f94ece365ebcb012 | IncompleteCache, local_endpoint, installed, model_plan, create_alias, coding_model, cache_roots, cached_payload, restore_cached |
| jarvis/paths.py | 2252 | ee9fb65ad1fe0a05d882f8584e2668e6ede1a209de83768710c1ae2aa7ba8b2e | linked, app_root, config_file, manifest_file, state_file, log_file, artifact_path |
| jarvis/pc_context.py | 6560 | 3a4e4539a4f71a9e8cabfabe3079e7f7ea547af6eaa6f9358aa21e104bb39842 | inventory, query_name, resolve_entries, requested_kind, prompt, canonical_resolution, validate_resolution, context |
| jarvis/pcm_ring.py | 4512 | efc780216a87e1b30b5b07e97b868e83486427604e32370480bd299eadcd9714 | PCMBuffer, CaptureQueue |
| jarvis/phrasing.py | 9845 | e0e09258adea9cb21731d10cd2c6949c231a40e8b73e1cdd1700a63b6e1cbedf | head_rewrite, keeps_punctuation, canonical |
| jarvis/piper_speech.py | 1724 | 3a609b46890874aa2d3080b65a0fa9a1908f67547721e8be6bab82f7b7f9522f | play_reply, main |
| jarvis/planner_settings.py | 1353 | 02458bf70c4783edd85f1a9062ce20e58d4a82994f0bfacf47caa1eccf3821f5 | settings |
| jarvis/polyglot_training_data.py | 8802 | 3db94ddd2a52ea9bca8d1ad13c372db7a7000de96e9d88cd7d76f005e626c8ee |  |
| jarvis/progress.py | 437 | 5e4d93f894dce1e298c1a5cff74a5fa661800697a7677e86f00631e28949d672 | status |
| jarvis/projects.py | 5471 | 09f6e89a8ee2c2b7a6551aac2f3eaada6f31c10bb99b4f611247b3399f27c35b | has_project_marker, project_paths, activity, Projects |
| jarvis/prompt_evolution.py | 10038 | 6eecfb77964431c491e197f6dbbc2d5bcf48381037452c8950f4839953fc3770 | halves, router_score, ollama_solver, ollama_reflector, PromptCoEvolution |
| jarvis/prompt_router.py | 4789 | 96a09d23f349f9517f3bbc0e202c251a92d5a2e89df6747ea9be415a4750ac3f | words, scores, route, guidance |
| jarvis/push_to_write.py | 9125 | 63a4a8bedd8588ca0f4bd5306455cddb87f489707ef8151653dd3056cee1326d | KBDLLHOOKSTRUCT, KEYBDINPUT, MOUSEINPUT, INPUTUNION, INPUT, PushToWrite |
| jarvis/question_client.py | 12202 | f0fccba9b4ad04d8c2bd2e59a29610ad953269630a95b6322b5e789626740f29 | bounded_request, QuestionClient |
| jarvis/quick_answers.py | 14189 | 382c0b151093c4a315cd4e2a4803c57bdfaa5697acbc483ba1b02b43617cd0f1 | WeatherService, QuickAnswers |
| jarvis/rea_tools.py | 26166 | 5071e608c0ab36b73d8de2d1ac6107dce568765e100573b2100096650df40340 | _config, _unlinked, _read_session, _exclusive, _root, _node, _entry, _commands, _session_dir, _target, _ledger_path, _append_ledger, status, _slug, _sessions, ingest, _run_rea, analyze, _analyze, ledger, record, execute, command |
| jarvis/realtime.py | 28609 | de7cdb6b5ed07ab524c687b2ff8f7f28fd670aeaa0fa5680d08bb5e693783f0a | command, settings, distance, epoch, _serious, serious, reader, Realtime |
| jarvis/realtime_catalog.py | 11223 | 2b05b32cb171a7f88b847b2fd3381090e6dbd0693f8e64ea9d0be75c4534d366 | Provider |
| jarvis/realtime_sources.py | 30237 | 5396ec35ab51c3b07e6a90fc233101f2150e9d2be8c8ec1002c5fc7823e23865 | countries_key, public_url, read_error, coordinates, endpoint, compact, xml_data, Sources |
| jarvis/reasoning_bank.py | 23369 | 67c33848ebe6533d56193f7556858e5058b1e921524adc30a0ca8b6df87b93ba | now, words, generic, pack, unpack, ReasoningBank, version_key, parse_items, validate_item |
| jarvis/recovery.py | 5555 | 65117bcb92ffc1640e61302d9bab3661150ea3c7227d5a60a0be74d9d75fc09c | ui_loop, record, restart_thread, Watchdog, OllamaService |
| jarvis/repo_abilities.py | 111660 | 23b7a7388b14b009e1cc13f8baa9cf9408838d0b6c09f7f8cf997eb2462305fb | AbilityError, Yield, memory_refusal, now_iso, slug, stdlib_modules, extract_code, check_code, clean_spec, trigger_pattern, needs_approval, AbilityForge, suppressed, references_for, parse_command, parse_learned, resolve_repo, execute, _execute |
| jarvis/repo_acquisition.py | 9602 | 1fc3badb829422addf8c964b087e55f6d3581a6d1fbfa901cd18830125d140c2 | environment, command, git, identity, eligible, acquire, verify_snapshot |
| jarvis/repo_analysis.py | 12421 | 4f9ebd88cdb76f0233c976f6798a7c1bb5c1df25dd3452ef5ecbbdc3fa46cef1 | annotation, validate, signature, analyze |
| jarvis/repo_learning.py | 68800 | f3d1c5d9c11f35d0ddab0ae806b9c89473e3601ef36127079a7613bbd38c2b9b | LearningError, TooLarge, canonical_name, safe_source_path, sensitive, text_data, public_query, atomic_json, words, repo_id, token, title_repo, python_symbols, regex_symbols, imports_of, analyze_zip, importance, RepoLearner, parse_command, execute, reference_for |
| jarvis/repo_runtime_runner.py | 8155 | db05263f5cef0a34afd6dca30ed3aee56675d64ac73a6ccf349745208f7a70df | harden, converted, bind, serializable, BoundedOutput, main |
| jarvis/repo_sandbox.py | 5776 | 13cdda50b28fd7dc4eebd6697c690d1ef00d3839f0aaedaa1c41a5715f9ec193 | RepositorySandbox |
| jarvis/repo_tools.py | 5954 | b10dfbe2d1cbdd0180877791259f423590c4552c6faf1903cb580990db7f1ae9 | execute, definitions, command |
| jarvis/repository_skills.py | 20780 | a3c30d22348632a6cdd27db9f95b00cb90c09fc9ac40911bc95e9edfa1e893ce | now, RepositorySkills, engine |
| jarvis/research_evidence.py | 1212 | 25f7e958a0d8c502e8dfae29875315a5ebed07eee4e96ba332ac94563ef3a6a7 | receipts, assess |
| jarvis/runtime_health.py | 4082 | c0178f238a933a2721a73542d043782a4f8b8be286fa3fbe383b35639e1829a5 | RuntimeHealth |
| jarvis/screen_awareness.py | 26419 | cc145de90ef8eb241303613e8664d611dda031e6363008fe9af15bd19257ecca | words, videos, match_titles, ordinal, safe_sum, ScreenAwareness |
| jarvis/screen_worker.py | 3943 | 110627f449fc2cc9f7d1efe3606472f6914436c0f8400286c2b8e7efdede45df | choose_window, capture |
| jarvis/self_evolution.py | 51436 | 795aef80477016fd07e0efeb14eefee97525599e27d6e6c5dbbebd089d263301 | _now, _settings, _battery_saver, _signature, CapabilityGapDetector, SelfEvolution, SafeEvolutionManager |
| jarvis/skill_evolution.py | 28263 | 4d7222ead93dc7e0fdb9c1638ad90c5c3d5ff0837e42c02471bc12d0be4cc546 | evolved_root, living_score, classify_failure, task_actions, finish_outcomes, update_trust, degraded, frontmatter, validate_skill, verify_execution, _write_skill, _slug, SkillEvolution |
| jarvis/skill_memory.py | 29071 | 362f5e6b3da72089774407e126909407015f85924608843db63db293b544c4c7 | words, atomic, linked, procedure_counts, procedure_reliability, SkillMemory |
| jarvis/skill_store.py | 19778 | 754e344c7f52149370f378f04c273aa9f76163a6ead89b0b3e6a9fa4915da5fb | now, content_hash, generate_skill_id, read_sidecar, ensure_sidecar, SkillStore |
| jarvis/speech.py | 28808 | 56ff85632d3acbaec180727b369fbe9550cf4b9689f3b3281a8dd9cb9f5b19fb | VoiceStartupError, spoken_text, speech_parameters, playback_timeout, speech_language, Speech |
| jarvis/speech_normalizer.py | 3153 | f4d1f67b46e07432ae765e561bd127e84c2f0b5ab617135fc4669b723fd6d2fd | integer, decimal, normalize, opening_clause |
| jarvis/spotify.py | 13107 | b311185f59767076483d0d648e6959b7662d7b687dca3a35b7158ef2fbf80ac2 | open_app, search, _spotify_session, _control, _track, _on_media_thread, control, _is_playing, is_playing, _audio_sessions, volume |
| jarvis/step_planning.py | 17637 | 7dcf0fae54f419e8a37991c680ff13fc69691c7fb250fc4e78211f20cc57f07e | compact_image, wants_image, StepSession, surface, recipe_control, fingerprint, WorkflowMemory, replay |
| jarvis/targeting.py | 1183 | b95bc86286ab4d16db6ecea7a05603111c2eb7842c8c2c55b6dc6a208eecde30 | disambiguate, scoped_matches |
| jarvis/task_graph.py | 2686 | 0ef6a77fe8935c09dd5ca6adbdc93f91b632a7a95f37a588c3ea585935f8cac3 | action_budget, resource_dependencies, validate_dependencies |
| jarvis/task_queue.py | 5765 | a72bebc4e7b3f8b55b4f6b2e49b42d9853756bf6610580779fa8e561ad6c3e9e | exact, words, score, describe, position, match, model_choice |
| jarvis/task_recovery.py | 2879 | b2a5723ed071adbce40909fa2d169e3088ef1c424bee384486f63220fa71b65e | retry_read, TaskFailure, action_key |
| jarvis/task_state.py | 14711 | c68e86c3b272a05f92e642f4a9c404a4a77b540fccfca521698e4d712c9b2ff6 | _now, TaskState |
| jarvis/templates/blender_ops.py | 3229 | 100a87fb0306ee09bcfea25d4f7bd34224480662f9e0a0588ca9b59f0e40c69a | describe, create, inspect, main |
| jarvis/templates/calculator.py | 1164 | d262a9bd8c14e649b2f4027a02f3c9afd103e20bf456cf29dc6fe5470d6c07f8 | calculate, main |
| jarvis/templates/calculator_gui.py | 3054 | 35c4a2619502b5f922ba48af53d9a9ee11cd2e968325e72952fffcd7240080fd | calculate, launch_ui, main |
| jarvis/tool_errors.py | 199 | c7bef23e0314507db80056466caa502e6788a1b6688986249fa9ae3cd2e99045 | ToolUnavailable |
| jarvis/toolkits.py | 31985 | 4e617dae14066d884fae721435e1c413a48f47472b891c6196f630f4f0b3f302 | _append_lock, status, available, arguments, validate_step, scoped_path, read_text, file_tool, _append, _scan, public_url, PageText, api, execute, remote_tool |
| jarvis/tools.py | 20057 | 00cc8aa3a4bed6fd26f6de5975316f6e50e6d8b0ba57b9e20a70c88f163dba9e | ToolSpec, ToolArgumentError, redact, validate_arguments, failure_category, ToolResult, _outcome, ToolRegistry |
| jarvis/trained_coder.py | 1592 | 21338ed707000cd554f31a0bae3ca1ffc941830ac050014182f26f74f202a903 | generate |
| jarvis/trained_pc.py | 1351 | 014801e4101e32c4597465c21f1fb27656cde0d82353d22ccf595215aa7d4f66 | resolve |
| jarvis/ui_controls.py | 20937 | 2dcd4ebfec3cfc07eff0c84161a73d95f778be878d0ce635491b85dec13106cc | label_key, matches, _safe, _ordered, _category, choice_text, UIControls |
| jarvis/ui_events.py | 2691 | 3f5c614377e667e446a5ef046d695a4d596272f8420c26a2c381070c4f323951 | UIEventBuffer |
| jarvis/ui_memory.py | 2301 | ca380dd605fedc39aaccb3885d7b9d09711e2c47e57e3420b947219c3e579452 | UIMemory |
| jarvis/ui_preview.py | 6941 | 81134162b28964011a809efed7f0fc49a204811e1c08fcdf60c5318a220ebd12 | export_preview |
| jarvis/ui_transport.py | 6473 | caa6fde694b35108882171a9bb720e7c25ff70dfb236e3aa95f6c50e12ba9c7c | UITransport |
| jarvis/ui_worker.py | 18994 | 3500bd59d78aaa8f104a84166635108b329e58299f4a332cd42fe0bcdb75ac91 | collect, routed, perform, serve |
| jarvis/upstream_windows_patterns.py | 13688 | 4f43c44023ec9319533d9ebfad00b89626a5ca7eb53d110e3d2c74f57e192bd9 | ExpandCollapsePattern, InvokePattern, ScrollPattern, SelectionItemPattern, TogglePattern, ValuePattern |
| jarvis/utility_audio_worker.py | 1263 | 83ee298dfa02d1b7b0a883628a7f96814e5922d56cdfa8d6ab7a4970d8c8a70f | main |
| jarvis/utility_container_runner.py | 3245 | 20ec039ac7d1a9b9883890c05ba46da3b74dffc55cf612908f742c6d81e90fd9 | main |
| jarvis/utility_core.py | 16336 | 9ddb933b8f32571a0e037816ab449a0f6736a6da18c0b17b0b131de0b97efc1d | scoped, read, write, execute |
| jarvis/utility_host.py | 9975 | 2a1d4a65e518a4cd654e747c1d716cd2c5121a60b2925fdb6d330a0b76e59099 | OwnedServer, execute |
| jarvis/utility_isolation.py | 2370 | b8fdfc283adb6537ec7186dfb7dd15dede1a0b54bd61a542dec8969089f8c63e | run |
| jarvis/utility_profiles.py | 13957 | dff8c5905c5476714b8fd6db5a8cc6fb38908caae662ee295a5ff57470832005 | schema, decorate, fingerprints, availability, tools |
| jarvis/utility_service_transport.py | 2431 | 3033dd4c33c5fdaf25496c97ee0ac0e622b136240d070523625bae36147abe53 | call |
| jarvis/utility_services.py | 9710 | 54574180bbe8d57a238b7efdc822f44423ebd6b13263525f3c215db659992551 | http, execute |
| jarvis/utility_tools.py | 6459 | 7a802b7ce07db4101a47e49784a808f00af771280e43f7d3b7e56d8d3facdc01 | core_call, key_for, run, execute |
| jarvis/utility_worker.py | 742 | a0a04a835da07452696bbfb3bb73fb92820bff317580e18aa4180bba38f95c1e | main |
| jarvis/viking_memory.py | 23875 | 6f866b7f60d560cdb263479a18ff32cd696ec6a32876f677735f585407de67e0 | now, sha256, slug, VikingMemory |
| jarvis/viking_worker.py | 4273 | c344b99d784aa637ba8aa039caa57b4aa1fa39ac2bccc48be2c91fb240fa65df | client, run, main |
| jarvis/visual_fallback.py | 24787 | d349dd7dc4e50e06b620e867967018c6504900b2b596e20c1572c4afc7f5f345 | readiness, click_point, Prepared, VisualOutcome, save_plan, VisualFallback |
| jarvis/visual_worker.py | 10932 | 691786799d62aec067936dfe8483108ae230787f399273a5718a73f5b71b3a8e | image_difference, unchanged, point, WindowsInput, perform |
| jarvis/voice_input.py | 1960 | 5691b7ff869caadcaf3849a5890fc7400b671a5a941a4663ce7fff1a4af86803 | echo_match, VoiceInput |
| jarvis/weather_units.py | 1584 | 91cb4f3c575f313df07a1cb5a19a65983a6ec4698bde7a49f22f56f05b0eeeec | normalize |
| jarvis/weather_watch.py | 21720 | f5b1b494a345fcbdd172bcb5ee8a0957609708405cc383006573b43031a32454 | distance, _moment, when, hazards, WeatherWatch, parse_command |
| jarvis/whatsapp.py | 56784 | 3f2c729eba47065fc0014e1a41acc07a4d2f186ade6f2a37078830644665c041 | WhatsAppError, _uia, physical, window, unread_total, ensure_window, document, read, _read, parse_row, chat_rows, search_box, set_value, search, clear_search, tokens, match_contacts, open_row, names_match, compose_box, open_chat_header, open_chat_name, is_open, messages, identity, normalized, compose_value, keys, type_draft, press_send, draft, Prompt, ask, answer_prompt, snapshot, sentence, card, request_data, find_contact, approve_and_send, send_approved_text, send_message, clipboard_files, restore_clipboard, send_files, unread_chats, auto_reply, reply_unread, call_controls, press, handle_call, Watcher, parse_command |
| jarvis/whatsapp_writes.py | 3315 | b70fcb286f326265024d73df9a7c91adcc23937b1218b9d922de5a21d24cbe07 | text_send |
| jarvis/whisper_backend.py | 4327 | cc351977157d8f2b028a99ce8d412c374eb56aac864ba582ba1649af6fdce44f | settings, WhisperUnavailable, prepare_cuda, check_cuda_libraries, load_model, CoordinatedWhisper |
| jarvis/window_focus.py | 4021 | 4dfe9f47fe0cf6dc23ef4b2d439da561648fc336b43e3c1227a7139217f687d7 | _process_name, windows, focus, focus_app |
| jarvis/windows_command_browser.py | 3149 | cccf0b4f09c9c0942dd74c3d71b896412f6840b2c547b00dccb4aec515f16809 | perform |
| jarvis/windows_command_desktop.py | 9367 | 2dd049d27b1494779250f4451704f8d3b37a535e551ec349265535d4a6c83d7b | matches_app, perform |
| jarvis/windows_commands.py | 19230 | c482c715ceb1595d0bde5cc925c7807c1faa573d441e5602f17c2dd6e7e72dcf | catalog, search, match, parse, prepare, ps_literal, powershell, run_ps, execute, interpret |
| jarvis/writing.py | 13486 | 539ddeb0f6798f5fddf576cbd2bcebe33f07014f0a948381b19c0038a05f7112 | parse_write, with_original_case, target_window, process_name, safe_text, resolve, write_exact, spoken_layout, SpokenWriter, compose |
