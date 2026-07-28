# v5.1.0 dependency security review

Review date: 2026-07-26

This review covers the Python dependency declarations shipped in the public source package and the pinned Microsoft Store build environment. It is not a claim that every transitive package will remain vulnerability-free after publication. A current advisory scan remains required for every signed installer or later release candidate.

## Changes made

- Raised `pypdf` from the old `>=4.3` floor and Store pin `5.9.0` to `>=6.14.2,<7` / Store pin `6.14.2`.
- Raised `pypdfium2` to `>=5.12.1,<6` / Store pin `5.12.1`; yanked `5.12.0` is not allowed.
- Raised the optional API stack to FastAPI `>=0.139.2,<1`, Starlette `>=1.3.1,<2`, Uvicorn `>=0.51,<1`, and HTTPX `>=0.28.1,<1`.
- Raised Store build pins to FastAPI `0.139.2`, Starlette `1.3.1`, Uvicorn `0.51.0`, Pillow `12.3.0`, and PyInstaller `6.21.0`.
- Added `scripts/check-dependency-security.py` and `mfl security dependencies` for an offline installed-version floor check.
- Added `pip-audit==2.10.1` to the development extra and the CI release gate for a current online advisory scan.
- Added weekly Dependabot checks for Python and GitHub Actions dependencies.

## Known advisories excluded by the new floors

### pypdf

- `GHSA-7hfw-26vp-jp8m` / `CVE-2025-55197`: crafted FlateDecode streams can exhaust RAM; fixed in 6.0.0.
- `GHSA-jfx9-29x2-rv3j` / `CVE-2025-62708`: crafted LZWDecode streams can exhaust RAM; fixed in 6.1.3.

The selected 6.14.2 floor includes later 2026 parser, XMP, decompression, loop-control, and memory hardening beyond those minimum patches.

### Starlette

- `GHSA-7f5h-v6xp-fcq8` / `CVE-2025-62727`: quadratic Range-header processing in `FileResponse`; fixed in 0.49.1.
- `CVE-2026-48710`: malformed Host handling while constructing `request.url`; fixed in 1.0.1.

The selected 1.3.1 floor is later than both fixes and includes later path-handling hardening.

### Pillow

- `GHSA-8vj2-vxx3-667w` / `CVE-2022-22817`: historical arbitrary expression injection, fixed in 9.0.1.
- `GHSA-xg8h-j46f-w952` / `CVE-2025-48379`: historical DDS encoding buffer overflow, fixed in 11.3.0.

The Store build now pins Pillow 12.3.0.

## Runtime boundaries

- The normal app remains bound to loopback by default.
- The new workflow, inventory, classification, QC, and knowledge-bundle components do not open sockets or fetch packages.
- The offline dependency check reads only installed distribution metadata.
- The online `pip-audit` step runs in CI/release preparation, not during ordinary local legal work.
- A passing version-floor check does not certify a package, operating system, browser, OCR engine, or model runtime as secure.

## Release commands

```bash
python scripts/check-dependency-security.py --strict-optional
python scripts/check-dependency-security.py --include-build --strict-optional
python -m pip_audit .
```

The second command is intended for the Store build environment, where the build-only packages are installed.
