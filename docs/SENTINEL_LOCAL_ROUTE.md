# SENTINEL configured local route

The optional **SENTINEL configured local route** is a narrow adapter for a
locally operated Ollama-compatible `/api/chat` gateway. It is integrated into
the existing Maine Family Law LLM local-agent approval flow; it is not a copy
of, connection to, or replacement for ProSe-SENTINEL AI.

## Safety boundary

- It is disabled unless the app host explicitly sets `AI_PROVIDER_ADAPTER` to
  `sentinel_ollama`.
- The gateway must be a literal loopback address (`127.0.0.1` or `::1`), and
  may use only the root or `/api/chat` path.
- The browser cannot set the gateway, select a model, discover models, pull a
  model, or send a model credential.
- Both configured models must be in the host allowlist. The fallback is tried
  only if the primary request fails.
- The normal app path still rehydrates matter-scoped sources on the server,
  quarantines instruction-like source text, requires exact-context approval,
  records an encrypted matter audit receipt, and labels output review-required.
- This route does not admit a model, establish legal quality, determine current
  law, make a finding, or permit filing, serving, signing, or other external
  action.

## Host configuration

Set these values in the local application host environment, never in browser
storage or an `.env` file committed to the repository:

```text
AI_PROVIDER_ADAPTER=sentinel_ollama
SENTINEL_MODEL_GATEWAY_URL=http://127.0.0.1:11434/api/chat
SENTINEL_LAW_PRIMARY_MODEL=qwen3:14b
SENTINEL_LAW_FALLBACK_MODEL=qwen3:8b
AI_MODEL_ALLOWLIST=qwen3:14b,qwen3:8b
```

The application deliberately performs no service start, model download, model
training, package installation, or remote fallback. If configuration is absent
or invalid, the route fails closed and the source-backed host answer remains
available.

## Verification scope

Focused tests prove host-only configuration, literal-loopback rejection,
allowlisting, primary-to-fallback sequencing, browser override resistance, and
the production UI label. They use a local mock gateway and do **not** prove the
quality, admission, safety, or availability of Qwen weights. Any deployment
needs its own licensed-model, hardware, output-quality, and release-admission
evidence.
