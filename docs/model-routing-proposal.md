# Proposal: model routing across Draft Detective agents

Status: proposal, not implemented. Based on the working tree inspected on September 22, 2026.

## Recommendation

Introduce a small, shared, **run-scoped model routing layer** beneath the existing agent constructors. Keep LangGraph, LangChain, Deep Agents, and Inspect doing their current jobs. Do not replace the agent frameworks or require a separate routing service.

The caller should be able to select a model for one agent, a workflow, or an entire evaluation; assign different models to different agents; and run independent comparisons across multiple models. Agent code should declare its identity and requirements, not contain provider credentials or decide which deployment to use.

The routing layer should resolve a request into an immutable model specification, validate it, and construct the framework-native model and tool configuration. An optional model gateway can sit underneath this layer later.

“Any model for any agent” should mean **any authorized model that satisfies that agent's capabilities**, without editing the agent's implementation. It cannot mean that a text-only model can inspect images, or that an OpenAI-compatible endpoint necessarily implements OpenAI's hosted tools. Unsupported combinations should fail clearly before execution, not silently change models or remove tools.

First release: explicit per-agent/per-workflow overrides, consistent provider configuration, end-to-end eval propagation, and auditable routing. Automatic quality-based selection, cross-provider fallbacks, and ensembles should be separate follow-on features.

## 1. What exists today

There is model construction and selection in several places, but no single application-wide model router.

| Invocation path | Current selection | Relevant source |
| --- | --- | --- |
| Conventional LangChain calls and tool-calling agents | Most subclasses declare a fixed `model`; `LangChainAgent` constructs and caches an instance's LLM. | [Base agent](../lib/models/agent.py), [reference extractor](../lib/agents/reference_text_extractor_v2.py), [citation validator](../lib/agents/citation_validator.py) |
| Custom Deep Agents | Usually pass `self.llm` from that same base class to `create_deep_agent`. | [Abbreviation checker](../lib/agents/abbreviation_checker.py), [reference validator](../lib/agents/reference_validator_v2.py) |
| Generic and skill-declared workflows | Many workflows share `SimpleDeepAgent`, with a fixed model and some per-workflow reasoning/timeout settings. | [Agent](../lib/workflows/simple_deep_agent/agent.py), [manifest construction](../lib/workflows/simple_deep_agent/manifest_base.py), [skill workflows](skill-workflows.md) |
| Interactive chat | An allowlisted picker chooses a model; a separate `build_llm` constructs it. Unknown picker IDs silently fall back to the default. | [Chat agent](../lib/agents/chat_agent.py), [shared builder](../lib/agents/deep_agent_setup.py) |
| Teams | Its Python entry point accepts a model, using the shared interactive builder. The Microsoft integration is a channel adapter, not another model-selection system. | [Teams agent](../lib/agents/teams_agent.py) |
| Auxiliary generation | Chat titles construct their own fixed-model client. | [Title generation](../lib/services/chat/title.py) |
| Embeddings | Separate OpenAI embedding construction and vector-store assumptions. | [Model definitions](../lib/config/llm_models.py), [vector store](../lib/services/vector_store.py) |
| Inspect / Flow | Local startup exports the active Inspect model into `EVAL_WORKFLOW_MODEL`. The abbreviation checker reads that variable into a class attribute at import time; other workflow agents still use their fixed defaults. | [Local backend](../evals_inspectai/common/local_backend.py), [model definitions](../lib/config/llm_models.py) |

Important consequences:

- Selecting a model in Inspect is **not currently a universal backend model override**. A remote API eval does not transmit that choice, and local startup only changes agents that consult the environment override. The all-workflow Flow config is therefore a smoke sweep, not a backend model comparison.
- Inspect generation settings, such as reasoning effort, are not automatically translated into backend agent settings. The separate structured abbreviation eval does call Inspect's selected model directly.
- `LLMModel` contains only provider and name. It does not distinguish endpoint, Azure deployment, credentials, API protocol, capabilities, or execution policy.
- Provider handling is inconsistent between `LangChainAgent` and `deep_agent_setup.build_llm`. Forwarding the same reasoning and temperature arguments to every provider/model is not a portable configuration contract.
- Some hosted-search declarations are built from **class-level defaults before the agent is constructed**. Changing just `self.model` would leave those tools configured for the wrong provider. See `agent_tools()` in the generic manifest and the [literature review node](../lib/workflows/literature_review_v2/nodes/literature_review.py).
- Authentication and preflight remain substantially OpenAI-oriented. `models.list()` success is not evidence that a selected deployment supports an agent's tools and output contract. See [preflight](../lib/services/preflight/service.py) and [workflow context creation](../lib/workflows/runner.py).
- Grader configuration is also split: [issue judging](../evals_inspectai/common/issue_judge.py) supports Inspect's `grader` role, while [the generic model-graded scorer](../evals_inspectai/common/scorers.py) uses an explicit argument or a fixed default. Solver and grader routing must be kept separate.

The inspected environment contains LangChain 1.3.9, LangGraph 1.2.6, Deep Agents 0.4.8, langchain-openai 1.6.0, Inspect AI 0.3.259, and Inspect Flow 0.12.0. Framework integration details below refer to that environment, not to a promise about every future version.

## 2. Options and tradeoffs

| Option | Advantages | Limitations | Recommendation |
| --- | --- | --- | --- |
| Add a `model=` argument to each agent | Small initial change; useful for direct Python callers. | Duplicates credential/parameter handling; does not solve persistence, remote evals, shared workflows, or tool compatibility. | Keep as a convenience entry point into the common resolver, not the whole design. |
| Central resolver plus framework-native adapters | One policy and identity contract; works with the current architecture; supports both public and private deployments. | Requires updating all construction paths and carrying routing through workflow execution. | **Recommended foundation.** |
| Put a model gateway/proxy in front of providers | Can centralize operational concerns across applications and expose approved deployment aliases. | Extra service and data boundary; feature parity and fallback behavior must be verified. It does not know this application's agent roles or evaluation semantics. | Optional transport beneath the resolver. |
| Choose a model dynamically on each agent turn | Can support escalation or cost-aware policies. | Harder reproducibility; provider-specific conversation state, tools, and summaries complicate switching. | Later, after static routing is reliable. |
| Replace the agent framework | May provide different orchestration features. | Large migration unrelated to the immediate configuration problem. | Not necessary for this request. |

There are also **two different endpoints** to keep distinct:

- `api_base_url`: the Draft Detective application being evaluated.
- A model endpoint: the provider, Azure resource, or approved gateway used by that application's agents.

Choosing one must not silently choose or reconfigure the other.

## 3. Give each invocation a stable identity

Route by an explicit machine-readable call-site ID, not a display name or Python class name. Many workflows instantiate the same `SimpleDeepAgent`, so class-based routing cannot distinguish them.

Proposed examples—not existing IDs:

```text
workflow.abbreviation_scan_v2.extract
workflow.about_this_ger.preface
workflow.about_this_ger.authors
workflow.literature_review_v2.review
workflow.reference_downloader.fetch
interactive.chat.respond
interactive.teams.respond
auxiliary.chat.title
```

Every invocation should identify its workflow or interactive surface, agent ID, role, parent invocation if any, and required capabilities. Workflow manifests should supply stable IDs for generic agents. Display names remain presentation-only.

An explicitly created child agent gets a child ID. Repeated fan-out calls, such as fetching many references, share the routing ID but have distinct invocation IDs. Thus one override selects the model for all reference fetches while logs still distinguish each call.

Keep model choices in routing configuration, not in portable skill prose. Skill/manifest metadata can declare requirements or a default role; any new metadata fields must be added to the existing validated schema.

## 4. Separate identity, selection, and construction

Start with three small typed contracts, rather than a large router framework:

1. **Model target:** provider, opaque model/deployment identifier, approved endpoint reference, protocol, credential reference, and supported capabilities.
2. **Routing policy:** defaults and overrides that select a target or named model profile for an invocation.
3. **Resolved invocation:** the selected target, validated effective parameters, tool/output strategy, policy version, and selection reason.

A profile can combine a target with tested settings—for example, a low-effort extraction profile and a higher-effort review profile targeting the same underlying model.

Provider model names should remain opaque strings. Do not assume every provider uses the same naming conventions or derive identity by replacing every colon with a slash. Inspect and LangChain names should be parsed/formatted at their adapter boundaries, splitting only the provider prefix. Azure deployment names must be distinct from underlying model identity when they differ.

Conceptually:

```python
# Proposed interfaces, not current APIs.
resolved = router.resolve(
    invocation=AgentInvocation(
        agent_id="workflow.abbreviation_scan_v2.extract",
        workflow_type="abbreviation_scan_v2",
        role="extractor",
    ),
    policy=context.model_routing,
    requirements=AgentRequirements(tool_calling=True, structured_output=True),
)
llm = model_factory.build_chat_model(resolved, credentials=context.credentials)
tools = tool_factory.build(requirements=tool_requirements, model=resolved)
```

Return a real framework-native `BaseChatModel`; do not wrap every agent in a new HTTP API or reduce its messages to strings. Preserve structured messages, tool-call IDs, streaming events, usage, and provider-specific content through tested adapters.

The resolved specification should be immutable. Cache a client only within an appropriately isolated scope or with a complete identity key: target, endpoint, credential identity, parameters, protocol, and relevant adapter configuration. Never mutate a global default or agent class to implement a request override.

## 5. Configuration and override precedence

Use a server-owned target/profile registry with deployment-local overrides. A normal API caller selects approved profiles; an authorized evaluation/developer interface can additionally submit a model name for an approved provider/endpoint. That preserves flexibility without allowing arbitrary destinations or secret references.

Illustrative server configuration; aliases and Azure deployment names below are examples, not validated deployments:

```yaml
schema_version: 1
targets:
  review_primary:
    provider: openai
    model: gpt-5.6-terra
    protocol: responses
    endpoint_ref: openai_default
    credential_ref: workflow_openai
  review_alternate:
    provider: anthropic
    model: claude-sonnet-4-5-20250929
    protocol: native
    endpoint_ref: anthropic_default
    credential_ref: workflow_anthropic
  private_deployment:
    provider: azure_openai
    deployment: document-review
    endpoint_ref: private_azure
    credential_ref: private_azure_identity

profiles:
  extraction:
    target: review_primary
    generation:
      reasoning_effort: low
  review:
    target: review_primary
    generation:
      reasoning_effort: medium
  alternate_review:
    target: review_alternate

routing:
  default_profile: review
  agents:
    workflow.abbreviation_scan_v2.extract:
      profile: extraction
    workflow.about_this_ger.authors:
      profile: alternate_review
```

The model identifiers above illustrate identifiers already present in this repository, not recommendations about model availability or quality. Registry entries must acquire verified capability/protocol metadata before use. Endpoints and credentials are configured outside this public example.

Precedence should be deterministic and explainable:

1. Server authorization, allowed destinations, data-handling rules, and budget limits are mandatory constraints, never overridable defaults.
2. Authorized invocation override: exact agent, then workflow, then run-wide override.
3. Saved deployment policy: exact agent, then workflow, then role, then deployment default.
4. Legacy agent default, only during migration and explicitly reported as such.

Within a layer, more specific beats less specific. An explicitly requested run-wide override must beat saved per-agent defaults; otherwise “evaluate all agents with model X” would not mean what it says. For a target-only experiment, override only the target agent instead.

Define merge semantics: unset fields inherit; a target/profile replacement discards incompatible inherited provider settings; explicit clearing of optional parameters is supported. Validate the final combination. Unknown agent IDs, unknown profiles, unsupported explicit parameters, and unavailable models should be errors—not fallback-to-default events.

Report the effective choice and the rule that selected it. Do not make a user infer precedence from a long series of environment variables.

## 6. Provider and capability handling

The adapter should own provider-specific translation and credential resolution. Agents should declare needs such as function tools, image input, streaming, structured output, and web search.

Validate the **model + deployment + API protocol + adapter version** combination. A provider name alone is insufficient. Native structured output and tool-based structured output are different strategies; selecting a strategy must preserve the agent's output contract.

For example:

- Resolve the model before constructing hosted web-search tools. Replace `web_search_tool(SomeAgent.model)` call sites with construction based on the resolved instance.
- Do not treat every non-Anthropic provider as OpenAI for hosted search, as the current helper does. Unsupported providers should fail clearly or use an explicitly configured portable search tool.
- A portable search tool can broaden compatibility, but changes retrieval behavior, permission boundaries, latency, and evaluation results. Treat it as a named tool strategy, not a hidden substitution.
- Translate or omit default-only reasoning/temperature settings according to verified support. Reject unsupported settings that the caller explicitly requested. Log effective settings and any documented default normalization.
- Keep timeouts, token limits, model-call retry budgets, and agent-turn budgets distinguishable.

For OpenAI, Responses and Chat Completions are distinct API contracts. OpenAI recommends Responses for new projects and documents its built-in tools; a generic chat-completions-compatible gateway is not proof of support for those features. [OpenAI Responses migration guide](https://developers.openai.com/api/docs/guides/migrate-to-responses), [OpenAI tool documentation](https://developers.openai.com/api/docs/guides/tools).

In the installed Deep Agents version, passing an `openai:` **string** selects Responses in its resolver, whereas passing an already-built model object leaves that object unchanged. This codebase normally passes objects. The common model factory should therefore choose the protocol explicitly rather than rely on a framework's string shortcut. This observation comes from the installed `deepagents/graph.py`, not an assumption that every provider shares that behavior.

Credential references must be provider/endpoint-scoped. An OpenAI user key must never accidentally accompany an Azure or third-party gateway request. Secrets stay in the runtime credential resolver, outside serializable routing policies, logs, and model metadata.

## 7. Integrate underneath each existing framework

### LangChain and LangGraph workflows

Make `LangChainAgent` resolve its invocation and build its model through the common factory. Preserve `self.llm` as an instance-level convenience. Update direct construction paths, including title generation, to use that same factory.

Extend `ContextSchema` with a frozen routing snapshot and workflow identity; keep credential access separate from that snapshot. Pass invocation identity when generic manifests instantiate `SimpleDeepAgent`. Plain LangChain calls, `create_agent`, and `create_deep_agent` can then receive the resolved model without replacing their orchestration.

### Deep Agents: include hidden model calls

In installed Deep Agents 0.4.8, the parent model is also used by the default general-purpose subagent and summarization middleware. Named custom subagents can specify a different model. A compiled subagent carries its own already-built runnable.

The first implementation should explicitly account for those inherited calls in the resolved plan and telemetry. A parent override must not leave an unnoticed second model running underneath it.

Later, support child routes such as `<agent-id>.subagent.research` and `<agent-id>.summarize`. Named subagents can receive separately resolved model objects. Independently routing the built-in general-purpose subagent or summarizer needs a tested factory/middleware integration: the current high-level constructor does not expose every desired override as a simple argument. Do not imply that appending middleware automatically replaces the framework's built-in middleware. Compiled subagents must opt into the shared construction contract or be reported as outside override coverage.

### Interactive chat and Teams

Have the picker and Python entry points produce routing overrides, not bypass the factory. Derive available picker options from the authorized registry and surface invalid selections explicitly.

Freeze a route for each agent run/interactive turn. Switching the next turn's provider on a durable thread requires validated history conversion: hosted-tool results, reasoning blocks, and provider-specific continuation IDs may not transfer. Initially reject incompatible switches or start a new thread; never silently drop conversation content.

### Inspect and Flow

Use the same serialized routing request against local and deployed backends. Local server startup should stop being responsible for model selection. This also allows a single backend to serve concurrent evaluations with different routing policies.

Add proposed eval arguments such as `routing_file`, `agent_model`, and `target_agent`; these do **not exist yet**. If using Inspect's active model as shorthand, explicitly map its name and supported generation configuration into the routing request. Record the effective backend model separately from the Inspect task model label.

Keep grader selection independent and make generic scorers respect the same explicit grader convention as issue judging. Embeddings likewise retain a separately configured route; swapping an embedding model can require vector dimension/index changes and reindexing. A chat-model override must not silently replace it.

## 8. Carry the choice through the entire workflow lifecycle

Adding a field to an agent constructor is insufficient for remote evaluation and delayed execution.

The proposed path is:

```text
API / Inspect / chat request
          |
          v
Authorize + validate + freeze routing policy
          |
          v
Persist on the run before queueing or waiting for approval
          |
          v
Workflow context -> invocation resolver -> model and tool factories
          |
          v
Existing LangChain / Deep Agents execution -> actual-route telemetry
```

Add a versioned optional `model_routing` field to both workflow start contracts and propagate it through `create_workflow_config`. Persist the sanitized policy/snapshot when the workflow run is created, including runs awaiting approval—not only after the first model call.

This specifically matters because [gate approval currently rebuilds configurations from the project](../lib/api/services/workflow_runner.py). It would otherwise lose a request-time route. Resume, dependency scheduling, and retry paths need the same treatment. A new nullable run-level JSON field is a reasonable storage option; existing runs should retain documented legacy-default behavior.

At execution, resolve credentials afresh and recheck authorization, while preserving the pinned target/settings. If a pinned route is revoked or unavailable, fail explicitly instead of silently using the deployment's newer default.

Distinguish the target workflow from prerequisites. A target-agent override should leave prerequisite routes pinned to a known baseline. A whole-pipeline experiment should explicitly override the dependency closure. Already-running or completed dependencies may have different routing provenance; record it and choose deliberate reuse versus recomputation. Do not reuse an incompatible result just because its workflow type matches.

Older deployed forks may ignore unknown request fields. Provide a routing capability/version check and require an echoed accepted routing fingerprint before spending money on an override-based evaluation. If the server cannot acknowledge enforcement, the eval should stop rather than label a default-model run as a requested-model run.

## 9. What “model(s)” should mean

Do not overload a plain model list with several incompatible meanings.

| Mode | Meaning | Execution semantics |
| --- | --- | --- |
| Fixed | One selected model for this invocation. | Default; stable throughout its agent loop. |
| Per-agent mapping | Different models for different named agents/roles. | One workflow with an explicit route map. |
| Comparison / sweep | Evaluate the same agent separately with A, B, and C. | Independent runs, outputs, state, and scores; use Inspect/Flow. |
| Fallback chain | Try B only if A suffers an eligible infrastructure failure. | Explicit retry/error policy; record every attempted target. |
| Ensemble | Run A and B, then combine or judge outputs. | An explicit workflow with isolated candidates and a separately routed aggregator. |
| Dynamic policy | Select or escalate according to defined criteria. | Later feature; version the policy and record every decision. |

For your model-variability work, comparisons and independent epochs are the right starting point. A fallback chain is not a comparison: a successful fallback must not be scored as though the requested primary model produced it.

Keep automatic fallbacks disabled in baseline evals. For production, bound total attempts across SDK retries, agent retries, and workflow retries. Retry eligible transient failures; do not use fallback to hide authentication, schema, capability, or authorization failures. Tool side effects make restarting an entire agent dangerous: isolate outputs or use idempotency keys and a documented recovery boundary. Avoid switching providers halfway through a tool conversation in the initial implementation.

Ensembles must not let multiple candidates write into the same report, occurrence collector, or persisted issue set. Aggregate isolated candidate outputs afterward, with provenance.

## 10. Evaluation validity and observability

Record both requested and actual routing on every invocation/model call: agent ID, parent ID, provider, endpoint/deployment reference, requested model, returned model identity when available, effective parameters, policy fingerprint, adapter version, selection reason, attempts, latency, usage, and errors. Never include credential values.

For workflows with several models, store the complete route map; one top-level model label is not enough. Attach that map to Inspect metadata and Langfuse traces. Gateways that internally change targets must either report actual routing or be marked as opaque; opaque routing is unsuitable for model-specific comparison claims.

Evaluation cache identity should include task/run identity, document content, epoch, routing fingerprint, relevant tool/prompt versions, and dependency provenance. Same-document abbreviation samples may share one extraction **within** a model/epoch; different epochs or route maps must execute independently. Fresh attempts must also avoid prior-workflow-state seeding and reused candidate outputs. Provider prompt-prefix caching is different from reusing a generated extraction; its presence does not itself mean that an epoch skipped inference.

Separate two experiments:

- **Agent comparison:** hold prerequisite artifacts, tools, prompts, and grader fixed; vary the target agent's model/settings.
- **Pipeline comparison:** vary the requested route map across the entire dependency graph and report the combined outcome.

Tests should cover concurrent route isolation, explicit precedence, provider-specific credentials and parameters, hosted-tool binding after selection, all construction paths, child/summarization inheritance, approval/resume persistence, rejection by unsupported servers, fallback labeling, and epoch/model cache separation. Contract tests with fake clients should precede small opt-in provider smoke tests.

## 11. Public repository and private fork

The public repository should own routing contracts, provider adapters, generic defaults, capability validation, and synthetic routing tests. Deployments should supply their own approved targets, endpoint/credential references, budgets, and private policy overlays.

The private fork should own its private prompts, datasets, and expected behavior alongside its deployment policy. The evaluation framework can submit the same routing contract to that fork's backend. It should not need a second implementation of agent model selection.

Prefer configuration overlays over fork-specific edits to shared constructors. Fingerprint the effective merged policy so a result can be traced back to the deployment configuration that produced it. Do not commit internal endpoints, secrets, or private evaluation content to public example configs.

## 12. Delivery plan

### Phase 1: reliable explicit routing

Create a small `lib/model_routing/` package for typed specs, resolution, credentials/factory integration, and capability validation. Extend the existing base agent and interactive builder to delegate to it. Inventory every direct model construction path and assign stable invocation IDs. Preserve existing defaults when no override is present.

Add routing to API requests, workflow configuration, run persistence, approval/resume, and execution context. Resolve models before tools. Expose authorized registry choices and fail on invalid explicit choices. Keep embeddings separate and account for inherited Deep Agents calls.

Wire Inspect's explicit agent override and selected generation settings through the same contract for local and remote backends. Require server acknowledgment. Deprecate the import-time `EVAL_WORKFLOW_MODEL` mechanism once that path works; do not keep two conflicting override systems indefinitely.

Acceptance demonstration: two concurrent requests to the same backend run the same agent with different authorized models, with correct tools and telemetry, without restarting the server or changing the grader. Repeat through an approval gate and across independent eval epochs.

### Phase 2: finer-grained control

Add role profiles, separately routable child agents/summarization where supported, consistent grader configuration, richer capability probes, and model-scoped rate limits. Rate-limit keys should reflect provider quota boundaries—credential/project/resource/deployment as appropriate—not model name alone or one undifferentiated `default` bucket.

### Phase 3: optional automation

Add gateway integration if operations require it, explicit production fallback chains, then ensembles or dynamic selection backed by evaluations. Each adds behavior and should have separate configuration and tests.

## Bottom line

Build one explicit routing contract and model factory underneath all current invocation paths. Make model choice request-scoped, persistent, capability-aware, and visible in results. Use Inspect/Flow for independent multi-model experiments; treat fallbacks and ensembles as different features. This gives flexibility without tying the public repository to a particular provider, gateway, deployment, or private fork.
