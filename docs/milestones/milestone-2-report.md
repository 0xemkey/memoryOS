# Milestone 2 Report: Deterministic Privacy Detection

## Implemented

- `PrivacyFinding` model with offsets, sensitivity, recommended action, detector, and policy version.
- Local privacy scanner service.
- Deterministic pattern detectors for:
  - emails
  - phone numbers
  - IP addresses
  - access-token-bearing URLs
  - API keys
  - JWTs
  - private keys
  - recovery codes
  - password-like values
  - account-number-like values
  - credit-card-like values with Luhn validation
  - national-ID-like patterns
- Local NER interface.
- Deterministic placeholder NER for projects, organizations, and usernames.
- Local contextual-classification interface and deterministic placeholder classifier.
- Deterministic overlap resolution.
- Policy mapping where credentials default to `remove`.

## Tests Executed

```powershell
python -m pytest
```

Result:

```text
28 passed, 1 warning
```

## Migration Notes

No database migrations were added for Milestone 2. Findings are modelled and scanned but not persisted yet.

## Exact Run Commands

```powershell
cd C:\Users\mehme\Desktop\MemoryOS
python -m pytest
```

## Unresolved Risks

- Placeholder NER is not a full named-entity recognizer.
- Context classification is deterministic and conservative.
- Scanner output is not yet connected to pseudonymization or encrypted vault storage.
- No container network isolation is implemented yet.
