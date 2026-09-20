# Local role inference

Nightshift role dispatch supports Ollama (default) and an explicitly configured oMLX loopback service. This setting controls local specialist roles, not the top-level factory runtime selector. Codex remains the tool loop and Nightshift validates the final role contract locally.

Add a `local` object to the consumer routing.json with backend `omlx`, model matching the server ID, base_url `http://127.0.0.1:8000/v1`, reasoning_effort `none`, and context_window `32768`. Optional auth_settings_file points to the existing private oMLX settings JSON; alternatively supply OMLX_API_KEY in the launch environment. Settings files must be owned by the caller, regular, non-symlink, and mode 0600 or stricter. Keys are passed only through the process environment. Endpoint credentials and non-loopback URLs are rejected. Source: scripts/nightshift-agent.sh local dispatch branch.

Select provider `local` and the exact model ID in ordinary role gears. Automatic gear 0 uses local.model when configured, otherwise NIGHTSHIFT_LOCAL_MODEL/the existing Ollama default. Hosted escalations and independent-review policy remain configured separately. Source: scripts/nightshift-route.sh.

For Ollama, local reasoning effort now defaults to none because the installed Qwen coding models reject thinking requests; override only for models supporting the chosen effort. oMLX must already be running; the dispatcher does not start services or change global Codex settings.

## Verification, 2026-09-20

The real oMLX Qwen3-Coder-30B-A3B-Instruct-4bit server answered a chat-completion smoke request. The actual Nightshift dispatcher then returned a validated SUCCESS for extraction from controller-supplied numbered source excerpts. Two earlier filesystem-tool attempts failed (incorrect NOT_FOUND, then invalid contract); retain these as model capability failures. This verifies local inference and structured transport, not reliable filesystem tool use or broad model competence. No engineering gate may be passed on this smoke result alone.

Offline dispatcher suite: 122 assertions passed, including oMLX process-scoped configuration, no Ollama flags on oMLX, credential absence from argv, endpoint rejection and default non-thinking mode. Existing local failure fallback remains bounded.

Receipts: docs/jobs-night-coach/omlx-smoke.json and docs/jobs-night-coach/local-verification/result{,2,3}.json. Real role output is validated even when the installed oMLX lacks grammar-constrained decoding.
