from pathlib import Path

def test_pass121_production_css_defines_and_uses_semantic_design_tokens():
 css=Path('src/maine_family_law_llm/ui/workbench.css').read_text(encoding='utf-8')
 for token in ('--color-canvas','--color-surface','--color-text','--color-text-muted','--color-border','--color-action','--color-focus','--color-status-success','--space-1','--type-base','--focus-ring','--motion-fast'):
  assert token in css
 assert 'outline: var(--focus-ring)' in css and 'color: var(--color-text-muted)' in css

def test_pass121_production_css_mirror_is_identical_and_accessibility_layers_remain():
 source=Path('src/maine_family_law_llm/ui/workbench.css');mirror=Path('maine_family_law_llm/ui/workbench.css')
 assert source.read_bytes()==mirror.read_bytes()
 css=source.read_text(encoding='utf-8')
 assert '@media (prefers-reduced-motion: reduce)' in css and '@media (forced-colors: active)' in css
