// Sovereign OpenClaw compatibility helpers. No network or transcript mutations.
function sovereignMeasuredBoundary(message, index) {
  const u = message?.usage;
  if (message?.role !== "assistant" || message.provider !== "sovereign" ||
      message.api !== "openai-completions" || message.stopReason === "error" ||
      message.stopReason === "aborted" || u?.contextUsage !== undefined ||
      !Number.isFinite(u?.input) || u.input <= 0 ||
      !Number.isFinite(u?.output) || u.output < 0) return;
  // Sovereign's OpenAI adapter exposes prompt_tokens as input, including
  // cached prompt tokens. Do not add cacheRead again. Completion tokens include
  // the assistant tool-call payload which is now part of the transcript.
  return { index, totalTokens: Math.ceil(u.input + u.output), includesSystemPrompt: true };
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
