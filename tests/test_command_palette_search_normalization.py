"""Acceptance tests for punctuation-tolerant production command search."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "maine_family_law_llm" / "ui" / "workbench_components.js"
MIRROR = ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench_components.js"


def test_command_search_matches_punctuation_free_user_words() -> None:
    assert SOURCE.read_bytes() == MIRROR.read_bytes()
    program = r"""
const fs = require('fs');
const vm = require('vm');
const context = {window: {}};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const commands = [{
  id: 'evidence',
  group: 'Evidence',
  label: 'Open Evidence & tools',
  hint: 'Open source cards',
  aliases: 'drawer proof audit workbench',
}];
const result = context.window.MaineWorkbenchComponents
  .filterAndGroupCommands(commands, 'open evidence tools');
if (result.items.map((item) => item.id).join(',') !== 'evidence') process.exit(3);
"""
    completed = subprocess.run(
        ["node", "-e", program, str(SOURCE)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
