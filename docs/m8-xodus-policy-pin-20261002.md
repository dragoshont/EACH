# M8 — Xodus policy, source, and issue-state pin (2026-10-02)

This document records the **exact, freshly re-fetched** state of the upstream
Xodus contribution/clean-room policy, the two motivating repositories, and
the single bounded issue selected for the M8 shadow demonstration, at the
moment this Run actually fetched them (not reused from any earlier session
or cached knowledge). All content below is public (fetched via the
unauthenticated GitHub REST API / `gh` CLI against public repositories);
none of it is proprietary, decompiled, or otherwise restricted.

## Repositories

| Repo | License | Default branch HEAD (fetched 2026-10-02) |
|---|---|---|
| `xodus-gaming/xodus` | GPL-3.0 | `a3afa0569332e32ce2677c0edc643ef85477ee3e` |
| `xodus-gaming/xgameruntime` | LGPL-2.1 | `791710510d9ba0746bbd60754215eb321800e4f0` |
| `xodus-gaming/.github` (org-wide contribution policy) | — | `ae13b61ce23f68e376e6f0562d5a690e41bd1587` |

## Pinned upstream contribution/LLM-use policy

Source: `xodus-gaming/.github` `CONTRIBUTING.md` at commit
`ae13b61ce23f68e376e6f0562d5a690e41bd1587`, fetched 2026-10-02T14:05:21Z via
`gh api repos/xodus-gaming/.github/contents/CONTRIBUTING.md`.

Full text (verbatim, this is the authoritative basis for
`policies/xodus-shadow.yml`):

> ## Xodus Contributing Guidelines
>
> We're really happy you are reading this, we always need new contributions
> in the Xodus project.
>
> Below you'll find a list of topics to consider before you submit your
> first contribution to any of `xodus-gaming` projects.
>
> #### Found a bug? Have a feature idea?
>
> - Make sure similar topic was not already reported by searching on GitHub
>   under `Issues`
> - If you're unable to find an open issue referring to the problem/feature
>   idea, **open a new one**. Make sure to include a title and a clear
>   description, with as much information as possible.
> - Try to use an issue template form that best fits the problem category.
>
> #### Intending to write a code patch?
>
> - Let us know what do you intend to work on via Discord or discussion in a
>   GitHub issue.
> - Follow our LLM use guidelines
> - Ensure all tests still succeed after your changes, add new if applicable
> - Submit a patch by creating a Pull Request
> - Write/update documentation if applicable
> - Ensure the PR description clearly describes the problem and the
>   solution. Include the relevant GitHub issue number
> - Iterate on the PR together with reviewers.
>
> ### LLM use guidelines
>
> We recognize LLMs (commonly called "AI" as speech mannerism) becoming part
> of the modern developer experience. However, given the sensitiveness of
> the project, and the main axis being directed on reverse engineering, we
> are forced to impose certain rules and limits as to where LLMs are
> acceptable, especially repositories that have a chance of bringing the
> code upstream, where similar rules are already in place.
>
> - Reverse engineering efforts driven by LLM are not allowed
> - LLM assisted code will be rejected from most repositories - see Wine
>   Clean Room Guidelines
>   - With the exception of parts of `xodus-gaming/xodus` that don't
>     interact with Microsoft or XBOX services. Code quality and
>     performance improvements not impacting api layer logic are welcome.
> - Ensure any comments in code are where actually needed
> - Please do not write tests to a point that it becomes irrelevant
> - Use of LLMs is welcome for documentation related tasks

### Reading this policy for EACH's purposes

`xgameruntime` is precisely the kind of repository this policy rejects
LLM-assisted code from outright: it is a clean-room reimplementation of
Microsoft's `xgameruntime.dll` GDK surface, i.e. API-layer logic that
interacts with Microsoft/XBOX services. **Any EACH-generated candidate for
`xgameruntime` must therefore remain shadow-only and must never be proposed
upstream** — this is a stricter, independently-confirmed version of EACH's
own general shadow-only default, not merely an EACH-internal preference.

## Selected issue (one bounded issue, not a subsystem)

**xodus-gaming/xgameruntime#22** — "XSystemGetXboxLiveSandboxId returns
E_POINTER when the optional sandboxIdUsed is NULL" (open, filed
2026-09-27T19:00:21Z, no assignee, no linked PR at fetch time).

Summary of the public, verbatim issue text: the Wine-style stub
implementation of `XSystemGetXboxLiveSandboxId` in `xsystem.c` currently
returns `E_POINTER` whenever its `sandboxIdUsed` output parameter is NULL —
but the function's published Microsoft GDK documentation marks that
specific parameter `_Out_opt_` (optional), meaning NULL is a documented,
valid argument there and only the write to it should be skipped. The issue
reporter's own text claims this was traced against ten real, commercially
shipped Game Pass titles and reports nine calling this function with
`sandboxIdUsed = NULL` during startup, naming Balatro and DREDGE as
failing to proceed past this call once `E_POINTER` is returned. This is
the reporter's own third-party claim, quoted from the public issue; EACH
has not independently reproduced or verified these specific game traces.

### Public vendor API documentation (independently confirmed, not reused from the issue)

Fetched live, 2026-10-02, from
`https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/system/xsystem/functions/xsystemgetxboxlivesandboxid`
(public Microsoft documentation page; no authentication required):

- `sandboxIdSize` — `_In_`
- `sandboxId` — `_Out_writes_bytes_to_(sandboxIdSize, *sandboxIdUsed)` — i.e.
  this parameter is **not** optional.
- `sandboxIdUsed` — `_Out_opt_` — i.e. this parameter **is** documented as
  optional.

This independently confirms the issue's core factual claim directly against
Microsoft's own published parameter annotations, without relying on the
issue text alone, and without any proprietary/decompiled source.

### Current public source at the pinned commit

`xgameruntime` at `791710510d9ba0746bbd60754215eb321800e4f0`,
`xsystem.c`, function `x_system_XSystemGetXboxLiveSandboxId` (LGPL-2.1,
public, unmodified):

```c
static HRESULT WINAPI x_system_XSystemGetXboxLiveSandboxId( IXSystemImpl5 *iface, INT32 sandboxIdSize, char *sandboxId, SIZE_T *sandboxIdUsed )
{
    /* Always assume RETAIL environment for Wine */
    const char *Id = "RETAIL";

    TRACE( "iface %p, sandboxIdSize %d, sandboxId %p, sandboxIdUsed %p\n", iface, sandboxIdSize, sandboxId, sandboxIdUsed );

    if (!sandboxId || !sandboxIdUsed)
        return E_POINTER;

    if (sandboxIdSize < XSystemXboxLiveSandboxIdMaxBytes)
        return HRESULT_FROM_WIN32( ERROR_INSUFFICIENT_BUFFER );

    strcpy_s( sandboxId, sandboxIdSize, Id );
    *sandboxIdUsed = strlen( Id ) + 1;
    return S_OK;
}
```

This is the exact, complete, scoped slice the M8 spec's `allowed_paths`
will bind to (`xsystem.c`, this function only). No other file, and no
proprietary/decompiled Microsoft source, is part of the Builder's declared
material.

## Known limitation, stated up front

Full native Wine/winelib compilation of this patch on macOS/Linux is not
yet proven by EACH (consistent with the mandate's own acknowledgement in
section 63 that Xodus native validation "will likely run at lower
assurance... until native isolation is proven"). M8's validation will use
the same structural patch-apply/scope machinery already proven in M1–M7,
plus a syntax-only check where practical; it will **not** claim a full
native compile or runtime execution against real Xbox/GDK services. Any
receipt produced will report this honestly as an explicit assurance
limitation, not omit it.
