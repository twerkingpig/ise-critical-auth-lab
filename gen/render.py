#!/usr/bin/env python3
"""
render.py — render a site YAML into a Cisco IOS config via Jinja2.

Usage:
    python3 render.py sites/branch-nyc-01.yml
    python3 render.py sites/branch-nyc-01.yml --template vlans.j2

Design notes:
    - Data lives in YAML. No logic.
    - Jinja templates live in templates/. Format only — no decisions.
    - Python glues them together. Nothing config-text lives here.

The StrictUndefined setting makes Jinja raise an error on any missing
variable. This is deliberate: a silently-empty variable in a router
config is worse than a loud error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined


HERE = Path(__file__).resolve().parent
TEMPLATES_DIR = HERE / "templates"
OUTPUT_DIR = HERE / "output"


def load_site(yaml_path: Path) -> dict:
    """Load a site YAML file and return its dict."""
    if not yaml_path.exists():
        sys.exit(f"error: site file not found: {yaml_path}")
    with yaml_path.open() as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        sys.exit(f"error: {yaml_path} did not parse into a mapping")
    return data


def build_env() -> Environment:
    """Create a Jinja2 environment with sensible defaults."""
    # Whitespace policy:
    #   trim_blocks=True   - strip the newline right after a block tag,
    #                        so '{% for %}\n' does not produce a blank line.
    #   lstrip_blocks=False - DO NOT strip leading whitespace before block tags.
    #                         lstrip_blocks=True is hostile to Cisco IOS submode
    #                         indentation: combined with '-%}' it eats leading
    #                         spaces from the next line, which destroys ' server
    #                         name ...' style submode indents inside loops.
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined,     # crash on missing vars
        trim_blocks=True,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )


def render(template_name: str, context: dict) -> str:
    """Render a single template with the given context."""
    env = build_env()
    template = env.get_template(template_name)
    return template.render(**context)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a site YAML into a Cisco IOS config.")
    parser.add_argument("site", help="Path to the site YAML file")
    parser.add_argument(
        "--template",
        default="full-config.j2",
        help="Template filename under templates/ (default: full-config.j2)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout instead of writing to output/",
    )
    args = parser.parse_args()

    site_path = Path(args.site)
    context = load_site(site_path)

    # Sanity: hostname is mandatory.
    if "hostname" not in context:
        sys.exit(f"error: {site_path} is missing required 'hostname' key")

    rendered = render(args.template, context)

    if args.stdout:
        print(rendered, end="")
        return 0

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{context['hostname']}.ios"
    out_path.write_text(rendered)
    print(f"wrote {out_path} ({len(rendered)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
