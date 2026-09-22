# Investigating LLM HTTP failures

OpenAI models created by `LangChainAgent` (including the abbreviation checker)
record each SDK HTTP attempt, including automatic retries:

- `LLM_HTTP_ATTEMPT_START`: sanitized endpoint, a client request ID, and the
  one-based attempt number when the SDK supplies its retry-count header.
- `LLM_HTTP_ATTEMPT`: HTTP status, allowlisted response headers, and
  `response_headers_elapsed_ms`. This measures time until response headers;
  it does not include reading the body or consuming a successful stream.
- `LLM_ERROR` / `LLM_RATE_LIMIT`: the existing workflow, project, model, and
  exception fields, plus a JSON `diagnostics` field. This includes the final
  attempt's HTTP diagnostics and `call_elapsed_ms` for the entire model call,
  including retries and any rate-limiter wait.

Each attempt gets an `x-client-request-id` unless one was already supplied.
A network timeout has a start record but no HTTP response record; the terminal
SDK exception retains its client request ID and `attempt_elapsed_ms`. Failed
attempts retried internally without a response have only their start records.
The hooks preserve existing SDK HTTP clients, proxy/TLS settings, retry policy,
and streaming behavior.

The final error's HTTP diagnostics are also persisted at
`WorkflowError.details.llm_metadata.http_error`. The existing error-details
dialog displays this under **Model response metadata** and includes it in
**Copy details**. Older errors are unchanged.

For RAND gateway failures, use the response body's `activityId` and the
`apim-request-id` / `x-ms-request-id` headers to trace the request through RAND's
gateway. If an OpenAI `x-request-id` is available, include it when escalating to
the upstream provider. A 500 with only `Internal server error` cannot tell us
which upstream component failed; these IDs enable the gateway/provider team to
find that information. A response-header duration around 240,000 ms would
support investigating a four-minute timeout, but does not prove its origin.

New diagnostics copy only selected error fields and response headers, cap text
values, and strip URL credentials and query strings. They do not copy request
bodies, authorization headers, cookies, or arbitrary response bodies. Existing
exception messages, tracebacks, and raw model-output diagnostics remain subject
to the application's existing log/error access controls.
