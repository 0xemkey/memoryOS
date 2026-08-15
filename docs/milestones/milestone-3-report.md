# Milestone 3 Report: Pseudonymization and Encrypted Vault

## Implemented

- HMAC-SHA256 typed pseudonym generation.
- Entity normalization for email, username, phone/card/account-like values, and general names.
- Key provider interfaces.
- OS keychain-backed provider.
- Static test-key provider.
- Development-only ephemeral provider that is disabled unless explicitly allowed.
- Authenticated encryption using `cryptography` Fernet.
- Encrypted vault entity storage.
- Stable encrypted mapping upsert and token resolution inside vault code.

## Tests Executed

```powershell
python -m pytest
```

Result:

```text
36 passed, 1 warning
```

## Migration Notes

- Updated `migrations/vault/001_initial.sql` with `key_version`.

## Exact Run Commands

```powershell
cd C:\Users\mehme\Desktop\MemoryOS
python -m pytest
```

## Unresolved Risks

- OS keychain integration is implemented but not mutated during tests.
- No review or reveal gateway exists yet.
- Sanitized handoff is not implemented yet.
- Runtime container isolation is not implemented yet.
