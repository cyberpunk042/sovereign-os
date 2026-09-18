# LM profile catalog and download readiness — 2026-09-10

## Operator words (verbatim)

> in sovereign-os we need to fix and have a proper list of Profile Language Model, in page lm orchestration.. I want at least one with Qwythos-9B-Claude-Mythos-5-1M-GGUF, which is in the catalogue and I want a better way to autodownload it if its missing when I apply the profile or to tell me to download it and how first

> yes please

> i do not want to have to do this manually

> it worked. now: verb='qwythos-deep-context' not in ['as-deployed', 'coding-focus', 'dense-4090', 'full-hybrid', 'full-orchestration', 'hybrid-coding-thinking', 'oracle-deepseek', 'oracle-glm', 'thinking-focus']

> when I try to activate a profile

> i want one profile where all three cards are qwythos

> I tried with openclaw and it failed:

> And I dont have all the card models available

> reboot done:

> nothing changed on openclaw, same response

> same error as before... can we take this seriously ?

> now I have a weird behavior, my list of models in openclaw is back to an old profile

> I never changed back to as-deployed, the last activated is the the Qwythos three card.. wtf..

> new bug:

> exec rail unreachable — run: sovereign-osctl trinity profile switch qwythos-three-card

> same crap...

> continue

> remaster it

> do it

> continue

> continue

> continue

> continue

> continue

> continue, better. more remaster

> continue, more remaster

> continue

> Bonsai 27b is not what I asked, that's another profile I want to test but I asked for Qwen

> jfortin@ai-workstation:~/sovereign-os$ sudo SOVEREIGN_OS_MODELS_DIR=/mnt/vault/models scripts/models/pull.sh Qwen3.6-27B-Coder --allow-candidate
>
> [sudo: authenticate] Password:
>
> INFO [build] ==== pulling Qwen3.6-27B-Coder ====
>
> INFO [build]   status: operator-must-confirm
>
> INFO [build]   repo:   Qwen/Qwen3.6-27B-Coder
>
> INFO [build]   dest:   /mnt/vault/models/Qwen3.6-27B-Coder
>
> WARN [build]   Qwen3.6-27B-Coder status='operator-must-confirm' — pulling ANYWAY (--allow-candidate bench-gate trial)
>
> INFO [build]   excluding: original/*
>
> INFO [build]   excluding: metal/*
>
> Traceback (most recent call last):
>
>   File "/usr/lib/python3/dist-packages/huggingface_hub/utils/_http.py", line 657, in hf_raise_for_status
>
>     response.raise_for_status()
>
> httpx.HTTPStatusError: Client error '401 Unauthorized' for url 'https://huggingface.co/api/models/Qwen/Qwen3.6-27B-Coder/revision/main'

> both are downloaded, the profile activated but I get error for the logic / rtx 5090 one in openclaw when I try to use

> WTF DO YOU FUCKING NOT UNDERSTAND: THE QWEN MODEL ON LOGIC CARD IS NOT WORKING

> WHY ARE YOU TROLLING ME ???? WHY IS THERE STILL NEMOTRON... retard ...

> JUST FIX THE FUCKING PROFILE SO THAT WHEN I ACTIVATE IT ACTIVATE PROPERLY..........

> we are going to create two new lm orchestration profiles:
>
> Strategy 1: The Dual-Agent Autocomplete Setup (Recommended)This configuration delivers maximum speed and utility by running two specialized models simultaneously.The RTX 5090's Role (Inline Autocomplete): Dedicate this card entirely to a lightning-fast fill-in-the-middle model. Run Qwen3.6-27B-Coder unquantized at FP8 or BF16. The 5090's massive 1,792 GB/s bandwidth will stream sub-second tab-completions as you type, utilizing only a fraction of its 32GB pool. [1] ([https://www.runpod.io/articles/guides/nvidia-rtx-5090](https://www.runpod.io/articles/guides/nvidia-rtx-5090)), [2] ([https://jarvislabs.ai/blog/coding-model-rtx-pro-6000](https://jarvislabs.ai/blog/coding-model-rtx-pro-6000)), [3] ([https://vrlatech.com/rtx-5090-vs-rtx-pro-6000-blackwell-ai-2026/](https://vrlatech.com/rtx-pro-6000-blackwell-ai-2026/)), [4] ([https://www.youtube.com/watch?v=pr9fsrK8nmQ)The](https://www.youtube.com/watch?v=pr9fsrK8nmQ) RTX 6000's Role (Agentic / Architectural Chat): Simultaneously run a heavy reasoning model like Qwen2.5-72B-Instruct at Q8 or native FP8 execution on the 6000. As you use an extension like Continue.dev or Cline, the fast autocomplete functions on one card while the larger card processes massive workspace index refactorings without freezing your IDE. [1] ([https://modelfit.io/gpu/rtx-6000-pro/)Strategy](https://modelfit.io/gpu/rtx-6000-pro/) 2: The Frontier Multi-File SpecialistIf your goal is to feed massive entire repositories into a single model for complex agentic coding (e.g., executing Python scripts, generating structural migrations, or auditing large C++ codebases), you can unify the VRAM pools using layer-splitting (Pipeline Parallelism) in vLLM or llama.cpp.The Model: Minimax 2.1 or DeepSeek-Coder-V2.How to deploy: Run the model at a Q4_K_M or EXL2 (3.5 to 4.0 bpw) quantization. The weights will occupy roughly 80GB on the RTX 6000.The VRAM Trick: Offload the remaining model layers and the massive KV Cache (Context Window) entirely onto the RTX 5090. This configuration enables you to digest a massive 64K to 128K context window locally. The 5090 handles the heavy context cache calculations efficiently due to its fast GDDR7 memory speeds. [1] ([https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/)), [2] ([https://www.reddit.com/r/LocalLLaMA/comments/1qew9df/best_coding_models_for_rtx_6000_pro_blackwell/](https://www.reddit.com/r/LocalLLaMA/comments/1qew9df/best_coding_models_for_rtx_6000_pro_blackwell/)), [3] ([https://www.runpod.io/articles/guides/nvidia-rtx-5090](https://www.runpod.io/articles/guides/nvidia-rtx-5090))

> continue

> continue

> ERROR 500 FFS

> FIX THE BIUG

> stilll error 500... wtf... wtf are you doing... GO INVESTIGATE THE FUCKING BUG.. LOOK AT THE LOG, DO SOMETHING

> good, we continue

> continue

> continue

> good, we continue

> we continue

> Error 500 when I try to apply Qwythos Dual + Local Memory

> same 500

> FFS... i SAID I GET ERROR 500 when I try to activate the profile . do you not listen ?

> continue

> go

> continue

> openclaw has the wrong profile againt, the wrongs models... how does that keep happening ? I DO NOT WANT TO HAVE TO REAPPLY MY PROFILE WITH Qwythos every 1 minute.... WAKE UP...

> I cannot even apply "Qwythos three-card pool" anymore, I get error 500

> so ? CPU-Only ? what are you talking about ? why are you not fixing things ?

> i dont see the qwythos rtx 4090 on Openclaw

> it present but not working:
>
> test
> You                                               just now
> The agent run failed before producing a reply.
> The agent run failed before producing a reply.
> sovereign/gpu-qwythos-worker request failed (provider internal error, HTTP 502). This is usually temporary — try again shortly.

> do the model not fit right on the card:
>
> Context overflow: this conversation is too large for the model. Try /compact, use /new to start a fresh session, or retry the command with a tighter output limit.

> i am starting a new conversation and It does this error. are older conversation poluting ?

> lets investigate openclaw 92de6d8d conversation together and find what is to improve and take over the work, read first

> Lets do SDD in sovereign-os to solve all those things

> okay lets start working on this, in order

> we continue

> continue.. we were no freeing the rtx 4090 for the openclaw ?

> replace the three card, make it dual instead with proper settings

> continue

## Status

Active — implementation in progress.  The profile picker must be catalog-grounded,
include an orchestration profile using the named Qwythos GGUF catalog entry, and
make missing model artifacts visible before profile application.  Model downloads
remain an explicit, confirmed operation under the default manual permission mode.

The follow-up approves a distinct RTX PRO 6000 deep-context Qwythos profile with
explicit conservative launch sizing and a benchmark gate before increasing its
context budget.

The live cockpit must automatically receive relevant development-checkout changes;
the operator must not need to manually copy or redeploy each dashboard edit.

> remove the confirmation step for apply profile in the lm orchestrator cockpit

> here is the latest error on openclaw with the logic card: Error: Context overflow: prompt too large for the model. Try /reset (or /new) to start a fresh session, or use a larger-context model.

> it was a fresh conversation...

> same error as before. take the time to think "Error: Context overflow: prompt too large for the model. Try /reset (or /new) to start a fresh session, or use a larger-context model."

> this time stuck at "Waiting for a response…"

> something is wrong. it takes too long for an answer. this model on this card should be much more powerful and fast

> we replace it with ternary bonsai then... why have a model I can't use?

> more precisely we will use Ternary-Bonsai-27B-dspark, its already downloaded

> when I try it I get "Context overflow: this conversation is too large for the model. Try /compact, use /new to start a fresh session, or retry the command with a tighter output limit."
>
> Is there a way to redownload the corrupt file ?

> okay now local-oracle, why does it not work ?

> lets resolve this issue, I want to use it in openclaw

> i just updated the active profile and openclaw models list did not update can we solve the code ?

> Ternary-Bonsai-27B should be another profile, I still need the profile with Qwen that was too big. (i will run desktop from the rtx 4090)

> do no hallucinate... removing the 4090 embedding/rerank allocations, I never said that.. wtf..

> after activating the profile I get this on openclaw: [gateway generation error: no local model loaded]

> I rebooted, what is the issue now ?
> can we not finetine, offload and whatnot:
> Error: Model context window too small (2048 tokens; source=modelsConfig). Minimum is 4000. OpenClaw is using the configured model context limit for this model. Raise contextWindow/contextTokens or choose a larger model.
> lets find how to have a normal context size without it being too slow either

> its too small

> should be downloaded now:
> id: GGML-Qwen3.6-27B-Coder

> on openclaw I get the response : Context overflow: this conversation is too large for the model. Try /compact, use /new to start a fresh session, or retry the command with a tighter output limit.

> I had a good run but then it started to bug: http://127.0.0.1:18789/chat/main/b3e14d12

> the logic model fail: The agent run failed before producing a reply.

> we need to remaster the project cockpits to make the Visual usable. we need to think more deeply about each cockpit and the cards and their shapes and size and content. lets start a big refactor

> continue, nothing noticeable improved in lm-orchestrator

> good, continue like this

> remaster the Profile library, I want the details but I want it displayed clean. I want it to be thorough UX

> okay good, lets continue the refactor and remaster of the cockpits

> good, we continue, remaster

> good, we continue, remaster next cockpit

> restart done. even the oracle fail with Error: Context overflow: prompt too large for the model. Try /reset (or /new) to start a fresh session, or use a larger-context model.

> i tried the oracle and I got Context overflow: this conversation is too large for the model. Try /compact, use /new to start a fresh session, or retry the command with a tighter output limit.
> [http://127.0.0.1:18789/chat/main/517001db](http://127.0.0.1:18789/chat/main/517001db)

> continue

> continue
