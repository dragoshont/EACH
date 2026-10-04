/*
 * Minimal, independently-written stand-ins for the small set of public
 * Win32/COM ABI names that xgameruntime's xsystem.c relies on, sufficient
 * to compile and exercise exactly one function in isolation on a
 * non-Windows host.
 *
 * Every name/value here is part of the long-published, public Win32 ABI
 * contract (HRESULT error-code layout, S_OK/E_POINTER well-known values,
 * the WIN32_FROM_HRESULT encoding scheme, etc.) -- the same public contract
 * Wine's own (LGPL) winerror.h/windef.h independently re-implement. Nothing
 * here is copied from, or derived by inspecting, any Microsoft or Wine
 * header file; it is written from first principles against values that are
 * part of Microsoft's own public API documentation (learn.microsoft.com).
 *
 * This header exists solely as EACH's own human/coordinator-authored test
 * scaffold for the bounded M8 demonstration (xgameruntime#22) -- it is
 * never Builder input and never part of the generated candidate.
 */
#ifndef EACH_M8_WINSTUBS_H
#define EACH_M8_WINSTUBS_H

#include <stddef.h>
#include <string.h>

typedef long HRESULT;
typedef unsigned long SIZE_T;
typedef int INT32;
typedef int BOOL;
#define WINAPI

#define S_OK ((HRESULT)0x00000000L)
#define E_POINTER ((HRESULT)0x80004003L)
#define E_NOTIMPL ((HRESULT)0x80004001L)
#define E_NOINTERFACE ((HRESULT)0x80004002L)

#define FACILITY_WIN32 7
#define ERROR_INSUFFICIENT_BUFFER 122L

static inline HRESULT HRESULT_FROM_WIN32(long error)
{
    return (HRESULT)(error) <= 0
        ? (HRESULT)(error)
        : (HRESULT)(((error) & 0x0000FFFFL) | (FACILITY_WIN32 << 16) | 0x80000000L);
}

/* strcpy_s (C11 Annex K) is not always available; a minimal, bounds-checked
 * stand-in with the same signature/semantics used by xsystem.c's call sites. */
static inline int strcpy_s(char *dest, size_t destsz, const char *src)
{
    size_t needed = strlen(src) + 1;
    if (!dest || !src || destsz < needed) return 1;
    memcpy(dest, src, needed);
    return 0;
}

/* TRACE is Wine's own debug-logging macro; a no-op stand-in is sufficient
 * since this harness only exercises return-value/output-parameter behavior. */
#define TRACE(...) ((void)0)

/* Opaque COM interface pointer type -- this function never dereferences
 * `iface`, so an opaque declaration is sufficient to compile it in isolation. */
typedef void IXSystemImpl5;

/* Public, Microsoft-documented constant (GDK XSystem reference docs state
 * the sandbox id buffer must be at least this many bytes) -- not derived
 * from inspecting the fix location, independently known from the same
 * public documentation page cited in docs/m8-xodus-policy-pin-20261002.md. */
#define XSystemXboxLiveSandboxIdMaxBytes ((SIZE_T)16)
#define XSystemConsoleIdBytes ((SIZE_T)39)

#endif
