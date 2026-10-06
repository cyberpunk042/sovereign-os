// Only the isolated, tool-disabled recovery summary changes its thinking mode.
// Normal attempts, other providers and profiles without our budget are untouched.
function sovereignFinalizationParams(attempt) {
  if (attempt.provider !== "sovereign" || !["gpu-oracle", "gpu-logic"].includes(attempt.modelId)) return {};
  const params = attempt.config?.agents?.defaults?.models?.[`sovereign/${attempt.modelId}`]?.params ?? {};
  const body = params.extra_body ?? {};
  if (!Object.hasOwn(body, "reasoning_budget_tokens")) return {};
  return {
    thinkLevel: "off",
    streamParams: {
      ...attempt.streamParams,
      extra_body: {
        ...body,
        ...attempt.streamParams?.extra_body,
        reasoning_budget_tokens: 0,
        chat_template_kwargs: {
          ...body.chat_template_kwargs,
          ...attempt.streamParams?.extra_body?.chat_template_kwargs,
          enable_thinking: false
        }
      }
    }
  };
}
