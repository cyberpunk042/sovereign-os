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

> ERROR 500 FFS

> FIX THE BIUG

> stilll error 500... wtf... wtf are you doing... GO INVESTIGATE THE FUCKING BUG.. LOOK AT THE LOG, DO SOMETHING

> good, we continue

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
