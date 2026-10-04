# Transport-budget follow-up, declared before inspecting accuracy

The original frozen 72-attempt comparison continues unchanged. Its 48,000-byte
local Jev guard rejected a 49,253-byte first-round request and a 63,803-byte
second-round request. A separate development-only live probe successfully sent
a 63,392-byte request and obtained scores for both complete programs. These
failures were local transport guards, not Jev answer rejections.

A separately frozen configuration changes only `jev_max_request_bytes` from
48,000 to 96,000. The scoring algorithm still splits requests by size without
truncating subjects. Raising the cap can allow more subjects in the same request;
therefore this is explicitly a configuration comparison, not an assertion that
individual scores will be identical. The service's maximum context size is not
established by this single successful probe.

All 12 original official-test images receive three new full-harness runs. All
36 original vanilla runs are reused as the unchanged control. No trial is
selected by its outcome, and no ground-truth accuracy result was inspected when
choosing this amendment. The original harness's failures remain in its own
36-attempt denominator. There are **108 unique trials**, not 144. This is a
follow-up on the same images, not a new independent validation cohort.

Original jobs use four concurrent workers; the new configuration uses three.
Both run concurrently on the same host with unchanged per-trial CPU/memory caps.
Timing is observational under this deployment load. All code, prompts, images,
reference masks, model identities and other configuration values are unchanged
in the copied task environments.

Artifacts:

- [Accepted development-only probe](transport-diagnostic-dev-only/diagnostic.json)
- [Variant protocol and hashes](test-transport96/selection.json)
- [Variant configuration](test-transport96/frozen-config.toml)
- [Variant preflight](test-transport96/variant-preflight.json)

Both configurations have completion watchers that generate their paginated
reports after their jobs finish. The shared control is explicitly labeled.
