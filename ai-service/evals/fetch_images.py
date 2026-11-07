"""Download the evaluation photos from Wikimedia Commons. Developer tool: run once.

    cd ai-service && uv run python -m evals.fetch_images

Each photo is the Wikidata "image" (P18) of the item, resized by Commons to a
small thumbnail. Every file keeps its own licence; evals/images/ATTRIBUTION.md
records the author, licence and source page.
"""

import html
import re
from pathlib import Path

import httpx

IMAGES = Path(__file__).with_name("images")
HEADERS = {
    "User-Agent": "eliezer-course-project/0.1 "
    "(https://github.com/EASS-PART-A-2026-X/eliezer)"
}
# case file name -> Wikidata item whose P18 image is used
ITEMS = {
    "rosemary": "Q102240169",
    "basil": "Q38859",
    "lemon": "Q500",
    "olive": "Q37083",
    "bougainvillea": "Q156996",
    "aloe_vera": "Q80079",
    "fig": "Q36146",
    "pothos": "Q161809",
    "sunflower": "Q171497",
    "bicycle": "Q11442",  # the not-a-plant control case
}


def strip_tags(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def main() -> None:
    IMAGES.mkdir(exist_ok=True)
    rows = []
    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
        for name, qid in ITEMS.items():
            claims = client.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetclaims",
                    "entity": qid,
                    "property": "P18",
                    "format": "json",
                },
            ).json()
            filename = claims["claims"]["P18"][0]["mainsnak"]["datavalue"]["value"]
            info = client.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "titles": f"File:{filename}",
                    "prop": "imageinfo",
                    "iiprop": "url|extmetadata",
                    "iiurlwidth": 480,
                    "format": "json",
                },
            ).json()
            page = next(iter(info["query"]["pages"].values()))
            image = page["imageinfo"][0]
            meta = image["extmetadata"]
            data = client.get(image["thumburl"]).content
            (IMAGES / f"{name}.jpg").write_bytes(data)
            rows.append(
                f"| {name}.jpg | {strip_tags(meta.get('Artist', {}).get('value'))} | "
                f"{strip_tags(meta.get('LicenseShortName', {}).get('value'))} | "
                f"{image['descriptionurl']} |"
            )
            print(f"{name}: {len(data) // 1024} KB, {filename}")
    (IMAGES / "ATTRIBUTION.md").write_text(
        "# Evaluation photos\n\n"
        "Thumbnails (480 px wide) of Wikimedia Commons files, used unmodified apart "
        "from resizing by Commons. Each file keeps its own licence.\n\n"
        "| File | Author | Licence | Source |\n|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
