from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


SPECS = [
    {
        "filename": "Square44x44Logo.png",
        "size": (44, 44),
        "purpose": "Start menu small tile and taskbar identity",
        "source": "focaf-family-law-llm-mark-1024.png",
        "kind": "square",
        "distribution": "msix",
    },
    {
        "filename": "StoreLogo.png",
        "size": (50, 50),
        "purpose": "Microsoft Store small logo",
        "source": "focaf-family-law-llm-mark-1024.png",
        "kind": "square",
        "distribution": "partner-center",
    },
    {
        "filename": "Square150x150Logo.png",
        "size": (150, 150),
        "purpose": "Start menu medium tile",
        "source": "focaf-family-law-llm-mark-1024.png",
        "kind": "square",
        "distribution": "msix",
    },
    {
        "filename": "Wide310x150Logo.png",
        "size": (310, 150),
        "purpose": "Wide tile",
        "source": "focaf-family-law-llm-horizontal.png",
        "kind": "wide",
        "distribution": "msix",
    },
    {
        "filename": "Square310x310Logo.png",
        "size": (310, 310),
        "purpose": "Large square tile",
        "source": "focaf-family-law-llm-mark-1024.png",
        "kind": "square",
        "distribution": "msix",
    },
    {
        "filename": "SplashScreen.png",
        "size": (620, 300),
        "purpose": "Packaged splash screen",
        "source": "focaf-family-law-llm-horizontal.png",
        "kind": "wide",
        "distribution": "msix",
    },
]


def _load(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def _make_square(base: Image.Image, size: tuple[int, int]) -> Image.Image:
    width, height = size
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    scale = min(width, height) * 0.76
    resized = base.resize((int(scale), int(scale)), Image.LANCZOS)
    left = (width - resized.width) // 2
    top = (height - resized.height) // 2
    canvas.alpha_composite(resized, (left, top))
    return canvas


def _make_wide(base: Image.Image, size: tuple[int, int]) -> Image.Image:
    width, height = size
    canvas = Image.new("RGBA", size, (255, 250, 244, 255))
    scale = min(width * 0.82 / base.width, height * 0.72 / base.height)
    resized = base.resize((max(1, int(base.width * scale)), max(1, int(base.height * scale))), Image.LANCZOS)
    left = (width - resized.width) // 2
    top = (height - resized.height) // 2
    canvas.alpha_composite(resized, (left, top))
    return canvas


def build_assets(brand_root: Path, output_dir: Path) -> list[dict[str, object]]:
    logo_root = brand_root / "assets" / "logo"
    square_source = _load(logo_root / "focaf-family-law-llm-mark-1024.png")
    wide_source = _load(logo_root / "focaf-family-law-llm-horizontal.png")
    inventory: list[dict[str, object]] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for spec in SPECS:
        image = _make_square(square_source, spec["size"]) if spec["kind"] == "square" else _make_wide(wide_source, spec["size"])
        destination = output_dir / str(spec["filename"])
        image.save(destination)
        inventory.append(
            {
                "filename": spec["filename"],
                "dimensions": {"width": spec["size"][0], "height": spec["size"][1]},
                "purpose": spec["purpose"],
                "source_brand_asset": spec["source"],
                "distribution": spec["distribution"],
            }
        )
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--inventory-path", required=True)
    args = parser.parse_args()

    inventory = build_assets(Path(args.brand_root), Path(args.output_dir))
    inventory_path = Path(args.inventory_path)
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
