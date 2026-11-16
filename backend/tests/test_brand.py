"""The brand follows the product: docs/brand/tokens.md is the table of
frontend/src/ui/tokens.css, every SVG of the docs uses only token colours, the
diagrams keep their text at 14 px or more at 1200 px wide and come in both themes,
and the funnel shows the demo seed's counts, labelled as example data."""

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SVGS = sorted([*(ROOT / "docs/brand").glob("*.svg"), *(ROOT / "docs/images").glob("*.svg")])
DIAGRAMS = ("flow", "agent-vs-you", "funnel")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# A colour given as an attribute (fill="...") or a style property (fill:...).
PAINT = re.compile(
    r'\b(?:fill|stroke|stop-color|flood-color|color)\s*(?:=\s*"([^"]*)"|:\s*([^;}"]+))'
)
NEUTRAL = {"none", "currentcolor", "transparent", "inherit"}


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


brand_tokens = load("brand_tokens")
brand_diagrams = load("brand_diagrams")


def test_tokens_md_is_generated_from_tokens_css():
    assert brand_tokens.TOKENS_MD.read_text() == brand_tokens.render(), (
        "docs/brand/tokens.md is out of date: run python3 scripts/brand_tokens.py"
    )


def test_both_themes_are_read_from_the_tokens():
    light, dark = brand_tokens.theme("light"), brand_tokens.theme("dark")
    assert light["bg"] == "#ffffff" and dark["bg"] != light["bg"]
    assert light["font"] == dark["font"] and "Inter" in light["font"]


def stray_colours(text, allowed):
    """The colours of an SVG that are not token values."""
    found = [value.lower() for value in HEX.findall(text)]
    found += [(attribute or style).strip().lower() for attribute, style in PAINT.findall(text)]
    return [
        value
        for value in found
        if not (value in NEUTRAL or value in allowed or value.startswith("url(#"))
    ]


def test_an_svg_uses_only_token_colours():
    allowed = brand_tokens.colours()
    assert SVGS
    wrong = [
        f"{path.name}: {value}"
        for path in SVGS
        for value in stray_colours(path.read_text(), allowed)
    ]
    assert not wrong, wrong
    stray = '<svg><rect fill="#123456"/><path style="stroke:red"/></svg>'
    assert stray_colours(stray, allowed) == ["#123456", "#123456", "red"]


def test_the_diagrams_come_in_both_themes_and_stay_readable():
    for stem in DIAGRAMS:
        for name in (f"{stem}.svg", f"{stem}-dark.svg"):
            text = (ROOT / "docs/images" / name).read_text()
            width = float(re.search(r'viewBox="0 0 ([\d.]+) ', text).group(1))
            sizes = [float(size) for size in re.findall(r'font-size="([\d.]+)"', text)]
            assert sizes, name
            assert min(sizes) * 1200 / width >= 14, name
            assert 'font-weight="700"' not in text, name


def text_of(name):
    return re.findall(r"<text[^>]*>([^<]*)</text>", (ROOT / "docs/images" / name).read_text())


@pytest.mark.parametrize("name", ["funnel.svg", "funnel-dark.svg"])
def test_the_funnel_is_example_data_from_the_demo_seed(name, demo_funnel):
    texts = text_of(name)
    assert "Example data" in texts
    numbers = [int(text) for text in texts if text.isdigit()]
    assert numbers == [demo_funnel[key] for key, _, _ in brand_diagrams.FUNNEL]


@pytest.fixture(scope="module")
def demo_funnel():
    return brand_diagrams.funnel_counts()
