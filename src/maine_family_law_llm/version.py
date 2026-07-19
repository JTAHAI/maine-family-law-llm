"""Canonical version and product metadata for Maine Family Law LLM."""

from __future__ import annotations

VERSION = "3.1.0"
BUILD_NUMBER = 7
PACKAGE_VERSION = f"{VERSION}.{BUILD_NUMBER}"
UI_TRACK = "family-justice-chat"
UI_VERSION = f"{VERSION}-{UI_TRACK}-b{BUILD_NUMBER}"
UI_PASS_MARKER = "v3.1-printables-and-private-index"
UI_FOOTER_LABEL = "v3.1.0"

APP_DISPLAY_NAME = "Maine Family Law LLM"
APP_EXECUTABLE_NAME = "MaineFamilyLawLLM.exe"
GITHUB_REPOSITORY_URL = "https://github.com/JTAHAI/maine-family-law-llm"
STORE_MISSION_TAGLINE = (
    "Built for Maine families. Open-sourced so every state can build its own verified, "
    "source-grounded edition."
)
FORK_GUIDE_RELATIVE_PATH = "docs/FORK_FOR_YOUR_STATE.md"
PRIVACY_POLICY_RELATIVE_PATH = "docs/PRIVACY_POLICY_MICROSOFT_STORE.html"
