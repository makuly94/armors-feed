#!/usr/bin/env python3
"""Fetch the Armors XML feed and publish Ukrainian and Russian variants."""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET


FEED_URL = os.environ.get("ARMORS_FEED_URL")
PUBLIC_DIR = Path("public")
SOURCE_FILE = Path("/tmp/armors-source-feed.xml")


def download_source() -> None:
    if not FEED_URL:
        raise RuntimeError("Set the ARMORS_FEED_URL GitHub Actions secret first.")

    request = urllib.request.Request(
        FEED_URL,
        headers={"User-Agent": "ArmorsFeedSync/1.0"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        with SOURCE_FILE.open("wb") as destination:
            while chunk := response.read(1024 * 1024):
                destination.write(chunk)


def build_variant(language: str) -> tuple[int, int]:
    tree = ET.parse(SOURCE_FILE)
    root = tree.getroot()
    offers = root.findall(".//offer")
    if not offers:
        raise RuntimeError("The downloaded file contains no <offer> products.")

    missing_ua_descriptions = 0
    for offer in offers:
        fields = {child.tag: child for child in list(offer)}

        # Expose the source's 1C product code as the standard YML vendorCode.
        code1c = fields.get("code1c")
        vendor_code = fields.get("vendorCode")
        if code1c is not None:
            if vendor_code is None:
                code1c.tag = "vendorCode"
            else:
                vendor_code.text = code1c.text
                offer.remove(code1c)

        for main_name, ua_name in (("name", "nameUA"), ("description", "descriptionUA")):
            main = fields.get(main_name)
            ukrainian = fields.get(ua_name)
            if language == "uk":
                if ukrainian is not None and ukrainian.text and main is not None:
                    main.text = ukrainian.text
                elif main_name == "description":
                    missing_ua_descriptions += 1
            if ukrainian is not None:
                offer.remove(ukrainian)

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    destination = PUBLIC_DIR / f"armors-feed-{language}.xml"
    tree.write(destination, encoding="utf-8", xml_declaration=True)
    return len(offers), missing_ua_descriptions


def main() -> int:
    try:
        download_source()
        for language in ("uk", "ru"):
            count, missing = build_variant(language)
            message = f"Published {count} products in {language} feed"
            if language == "uk" and missing:
                message += f" ({missing} Ukrainian descriptions use the source-language fallback)"
            print(message)
    except Exception as error:  # surfaced in the Actions log without printing the URL
        print(f"Feed update failed: {error}", file=sys.stderr)
        return 1
    finally:
        SOURCE_FILE.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
