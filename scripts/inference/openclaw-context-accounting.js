// Sovereign OpenClaw compatibility helpers. No network or transcript mutations.
function sovereignMeasuredBoundary(message, index) {
  const u = message?.usage;
  if (message?.role !== "assistant" || message.provider !== "sovereign" ||
      message.api !== "openai-completions" || message.stopReason === "error" ||
      message.stopReason === "aborted" || u?.contextUsage !== undefined ||
      !Number.isFinite(u?.input) || u.input < 0 ||
      !Number.isFinite(u?.output) || u.output < 0) return;
  // OpenClaw normalizes input to UNCACHED tokens. Cached prompt tokens still
  // occupy context; include each normalized bucket exactly once.
  const cached = u.cacheRead ?? 0;
  const written = u.cacheWrite ?? 0;
  if (!Number.isFinite(cached) || cached < 0 ||
      !Number.isFinite(written) || written < 0 ||
      u.input + cached + written <= 0) return;
  return { index, totalTokens: Math.ceil(u.input + cached + written + u.output), includesSystemPrompt: true };
}

function sovereignRecoveryProgress(input) {
  if (input.provider !== "sovereign") return;
  const state = input.state;
  const seen = state.sovereignSeenToolWork ??= new Set();
  const successful = new Set((input.attempt.toolMetas ?? [])
    .filter(t => t.isError === false && !t.codeModeSuspended && !t.asyncStarted)
    .map(t => t.toolCallId));
  let progress = false;
  for (const message of input.attempt.messagesSnapshot ?? []) {
    if (message.role !== "assistant" || !Array.isArray(message.content)) continue;
    for (const block of message.content) {
      if (block.type !== "toolCall") continue;
      // IDs alone are insufficient: re-reading the same file with a new ID
      // is not forward progress. Compare the tool name and actual arguments.
      const key = JSON.stringify([block.name, block.arguments]);
      if (!seen.has(key) && successful.has(block.id)) progress = true;
      seen.add(key);
    }
  }
  // Keep the upstream 3-failure guard for unchanged payloads. Renew it only
  // after successful compaction AND distinct successful work; cap renewals.
  if (state.sovereignCompacted && progress && (state.sovereignProgressResets ?? 0) < 8) {
    state.overflowCompactionAttempts = 0;
    state.toolResultTruncationAttempted = false;
    state.sovereignProgressResets = (state.sovereignProgressResets ?? 0) + 1;
  }
  state.sovereignCompacted = false;
}
