# MSIX Privacy Boundaries

## Default privacy posture

The Microsoft Store edition is local-first by default.

- No telemetry is added for Store packaging.
- Matter files are processed from user-selected folders.
- Original source records are hashed and treated read-only.
- Private matter data is not used for shared-model training by default.

## Storage boundaries

- Installed package: read-only
- Local runtime state: `%LOCALAPPDATA%\MaineFamilyLawLLM`
- User matter builds: user-selected external folders

## Release-boundary rules

Do not package:

- real matter folders
- external legal-matter releases from real cases
- private forensic masters
- embeddings
- vector stores
- OCR caches
- logs
- generated work product from real matters

## Operator deletion model

To remove local traces:

1. uninstall the package
2. delete `%LOCALAPPDATA%\MaineFamilyLawLLM`
3. delete any user-created external corpus folders separately

## Optional networked modifications

The committed Store runtime does not require cloud APIs. If an operator later modifies the project to add third-party model lanes or connectors, those changes are outside the default Store package and must be disclosed separately.
