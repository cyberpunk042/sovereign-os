# Shared cockpit shell repair

Operator request (verbatim):

> the agent was working well for a while but it seems unable to achieve / resolve this one:
> http://127.0.0.1:18789/chat/main/shared-header-and-sidemenu-across-all-cockpits-3888c7ad
>
> the sidemenu and header dont render / crash and make my experience broken.

Scope: investigate the conversation and shared shell failure; repair its source and regenerate cockpit embeds, preserving unrelated work; verify rendering and regression coverage.

Follow-up (verbatim):

> image-generation cockpit content was lost or ?

Authorization to restore the image-generation content while retaining the shared shell repair (verbatim):

> go

Image API follow-up (verbatim):

> can you solve that for the image gen page again:
> Uncaught (in promise) TypeError: can't access property "length", st.image_probes is undefined
>
> And it says:
> No runtime profile marker found. Pick one in D-21 (LM Orchestration) or with the profile command below.
>
> But I did load the profile with image gen companion so normally the model should be up. I think we have missing work there.

Generation timeout report (verbatim):

> okay its there. now -> I think the image-gen call timeout somewhere:
> POST[http://127.0.0.1:8100/api/image-gen/generate](http://127.0.0.1:8100/api/image-gen/generate)[HTTP/1 502 Bad Gateway 30031ms]

Image viewing request (verbatim):

> i cant even click to see the image bigger ... lets solve that
