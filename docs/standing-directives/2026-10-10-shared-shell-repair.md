# Shared cockpit shell repair

Delete interaction follow-up (verbatim):

> The Delete permanently does nothing, we need to fix that

Gallery removal request (verbatim):

> there should be a way / option to delete from the gallery / filesystem

Superseding operator direction (verbatim):

> i asked for delete, a full delete, no just a move to trash. and also it should work. not like right now

Implementation: confirmed, audited permanent deletion of one named generated PNG; no arbitrary path access.

Gallery report (verbatim):

> the gallery is not working properly..&#x20;
>
> This [http://127.0.0.1:8100/api/image-gen/artifact?name=2026-10-10T111429Z-8188.png](http://127.0.0.1:8100/api/image-gen/artifact?name=2026-10-10T111429Z-8188.png)
>
> returns&#x20;
>
> | error | "invalid artifact name" |
> | ----- | ----------------------- |

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
