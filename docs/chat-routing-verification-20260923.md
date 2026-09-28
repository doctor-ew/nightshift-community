# Portal chat routing verification

The IF-325 portal attempted to read routing.json from its application worktree,
which has no routing file or Nightshift manifest. Chat submission and background
execution bypassed the shared runtime routing resolver.

Both paths now use the shared resolver. Submission records the resolved path as
private worker state, so an asynchronous child uses the same configuration even
if its environment changes. The explicit ticket project takes precedence over
ambient project context; explicit routing-file overrides retain precedence.
The private path is omitted from responses and removed on completion or failure.

Validation: 10 chat tests, 3 routing tests, and 11 HTTP tests passed. The added
chat regression reproduced the missing-file error before the fix, then exercised
submission and persisted completion with a stub provider and no consumer routing
file. The HTTP suite required loopback socket access outside the sandbox.
Whitespace validation passed. The portal loads the chat module on each request;
no server or ticket restart was performed.

Live IF-325 inspection confirmed its registered worktree has no routing.json and
its profile configuration exists. Automatic approval review rejected a live chat
POST because it would transmit private ticket evidence to an external model.
No live model answer or model usage is claimed; the user can retry from the portal.

MEX context used: .mex/ROUTER.md and .mex/patterns/change-cli-runtime.md, plus the
project context loaded earlier in this session. Local graph impact lookup was
unavailable because the worktree has no graph index. Scaffold updates cite source
files; they do not claim refreshed graph grounding. Naming, runtime-neutral role
prompts, upstream ticket authority and trajectory schemas remain unchanged.
