# SQLCipher Installation Blocker

**Date**: 2026-08-15  
**Status**: INSTALLATION FAILED - pysqlcipher3 cannot be built on this Windows environment

## Problem

Attempted to install `pysqlcipher3>=1.2.0` as per the encryption plan. Installation fails during wheel build with:

```
ValueError: No distribution was found. Ensure that `setup.py` is not empty and that it calls `setup()`.
```

The package source distribution has a broken build system (missing or empty setup.py) that the setuptools build backend cannot process.

## Root Cause

`pysqlcipher3` is an unmaintained package (last update 2021). The source distribution structure is incompatible with modern Python 3.13 + setuptools. No pre-built wheels are available on PyPI for Python 3.13 on Windows.

## Alternatives Evaluated

1. **pysqlcipher3**: ✗ Build fails (this attempt)
2. **cryptg**: Lightweight Fernet-based alternative, but requires manual wheel integration
3. **sqlcipher**: Modern maintained fork, but same build system issues (needs C compiler setup + SQLCipher library binary)
4. **sqlalchemy-utils**: Provides encryption wrappers but still requires the underlying cipher library

## Current State

- `pysqlcipher3` added to `pyproject.toml` but cannot be installed
- Partial code changes made to `packages/normalized_storage/store.py` and test files
- Changes are backwards-incompatible (now require `key_provider` parameter)
- **Full test suite is currently broken** and cannot run until this is resolved

## Options

### Option 1: Revert to plaintext, document with Option A only
**Status**: Safe but incomplete  
**Effort**: 15 min  
**Outcome**: Step 1 (honest disclosure) remains live, Steps 2-3 (encryption) deferred

**Action**: 
- Remove pysqlcipher3 from pyproject.toml
- Revert all code changes to normalized_storage/store.py, cli.py, dependencies.py, test files
- Keep SETUP_FIRST_RUN.md and diagnostics() changes (honest disclosure)
- Mark encryption as "future work" in KNOWN_LIMITATIONS.md

### Option 2: Build a Windows-compatible wheel locally
**Status**: Possible but time-consuming  
**Effort**: 2-3 hours  
**Outcome**: Custom wheel for this environment, not portable to users

**Action**:
- Download SQLCipher C library binary for Windows
- Set up build environment (compiler, headers)
- Manually build pysqlcipher3 wheel
- Add to repo or CI/CD to re-build for each Python version

**Issue**: Users cannot reproduce this build; not a sustainable production approach.

### Option 3: Implement encryption using existing cryptography library
**Status**: Possible, more work  
**Effort**: 4-5 hours (new approach, not just SQLCipher wrapper)  
**Outcome**: Fully implemented, portable, no external C dependencies

**Action**:
- Use `cryptography.Fernet` (already in dependencies, used by vault)
- Implement read/write encryption transparently at the SQLite level
- Pattern: intercept all data going to/from database, encrypt on write, decrypt on read
- Pro: Pure Python, no C compiler needed
- Con: Higher CPU overhead than SQLCipher's C implementation

### Option 4: Wait for pre-built wheel
**Status**: Unknown ETA  
**Effort**: 0, but blocked indefinitely  
**Outcome**: Hope upstream releases Python 3.13 wheels

**Issue**: pysqlcipher3 is unmaintained; wheels unlikely to appear.

## Recommendation

**Go with Option 1 immediately** (revert to safe state):
- Step 1 (honest disclosure) is a win on its own and must ship
- Steps 2-3 (encryption) can be deferred to a follow-up task that either:
  - Uses Option 3 (implement custom encryption layer above plain SQLite) — cleaner long-term, full control
  - Waits for a maintained SQLCipher binding to emerge — unlikely

This unblocks the test suite and lets you ship Step 1 without regressions.

## Files Currently in Broken State

- `pyproject.toml` — has `pysqlcipher3>=1.2.0`
- `packages/normalized_storage/store.py` — imports pysqlcipher3, expects key_provider param
- `apps/orchestrator/private_brain.py` — passes key_provider to NormalizedImportStore
- `apps/orchestrator/cli.py` — passes key_provider
- `apps/orchestrator/dependencies.py` — passes key_provider
- `tests/security/test_complete_deletion_fix_simple.py` — uses StaticKeyProvider
- `tests/integration/test_normalized_storage_api_cli.py` — uses StaticKeyProvider
- Plus ~13 other test files not yet updated (will break when test suite runs)

**All of the above need reverting before `pytest` can run successfully.**

---

**Next Action**: Confirm user decision on Option 1 vs 3 before proceeding.
