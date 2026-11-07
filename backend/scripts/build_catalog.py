"""Build app/data/plants.csv from Wikidata (CC0). Developer tool: run once, commit.

    cd backend && uv run python scripts/build_catalog.py

Strategy (the public endpoint stops queries after 60 s, and a single
"descends from Plantae" path query times out):
  1. Fetch every taxon (rank species or genus) that has a Hebrew Wikipedia
     article, with its scientific name, labels and direct parents (~10k rows).
  2. Walk the parent (P171) links upwards in small batches until each chain
     reaches Plantae (Q756) or ends.
  3. Keep the plants; write scientific name, English and Hebrew names.

Only Wikidata data (CC0) is used. Nothing is copied from Wikipedia articles.
"""

import csv
import re
import sys
import time
from pathlib import Path

import httpx

ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "eliezer-course-project/0.1 "
    "(https://github.com/EASS-PART-A-2026-X/eliezer)",
}
PLANTAE = "Q756"
OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "plants.csv"
BATCH = 400
HEBREW = re.compile(r"[֐-׿]")

TAXA_QUERY = """
SELECT ?item ?sci ?he ?title ?en ?common ?parent WHERE {
  ?article schema:isPartOf <https://he.wikipedia.org/>;
           schema:about ?item; schema:name ?title .
  ?item wdt:P105 ?rank . VALUES ?rank { wd:Q7432 wd:Q34740 }
  ?item wdt:P225 ?sci .
  OPTIONAL { ?item wdt:P171 ?parent . }
  OPTIONAL { ?item rdfs:label ?he . FILTER(LANG(?he) = "he") }
  OPTIONAL { ?item rdfs:label ?en . FILTER(LANG(?en) = "en") }
  OPTIONAL { ?item wdt:P1843 ?common . FILTER(LANG(?common) = "en") }
}
"""

PARENTS_QUERY = """
SELECT ?item ?parent WHERE {
  VALUES ?item { %s }
  ?item wdt:P171 ?parent .
}
"""


def qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def sparql(client: httpx.Client, query: str) -> list[dict]:
    for attempt in range(4):
        response = client.get(ENDPOINT, params={"query": query})
        if response.status_code == 429 or response.status_code >= 500:
            wait = int(response.headers.get("Retry-After", 5 * (attempt + 1)))
            print(f"  {response.status_code}; waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()["results"]["bindings"]
    raise RuntimeError("Wikidata kept failing; try again later")


def clean_hebrew(name: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()


def main() -> None:
    with httpx.Client(headers=HEADERS, timeout=90) as client:
        print("1/3 fetching taxa with a Hebrew Wikipedia article...")
        rows = sparql(client, TAXA_QUERY)
        taxa: dict[str, dict] = {}
        parents: dict[str, set[str]] = {}
        for row in rows:
            item = qid(row["item"]["value"])
            taxon = taxa.setdefault(
                item, {"sci": row["sci"]["value"], "he": "", "en": "", "common": []}
            )
            if "he" in row:
                taxon["he"] = row["he"]["value"]
            elif not taxon["he"]:
                taxon["he"] = row["title"]["value"]
            if "en" in row:
                taxon["en"] = row["en"]["value"]
            if "common" in row and row["common"]["value"] not in taxon["common"]:
                taxon["common"].append(row["common"]["value"])
            if "parent" in row:
                parents.setdefault(item, set()).add(qid(row["parent"]["value"]))
        print(f"   {len(taxa)} taxa")

        print("2/3 walking parent links up to Plantae...")
        frontier = {p for ps in parents.values() for p in ps} - parents.keys()
        rounds = 0
        while frontier:
            rounds += 1
            batch_ids = sorted(frontier)
            frontier = set()
            for start in range(0, len(batch_ids), BATCH):
                chunk = batch_ids[start : start + BATCH]
                values = " ".join(f"wd:{i}" for i in chunk)
                for row in sparql(client, PARENTS_QUERY % values):
                    item, parent = (
                        qid(row["item"]["value"]),
                        qid(row["parent"]["value"]),
                    )
                    parents.setdefault(item, set()).add(parent)
                for i in chunk:
                    parents.setdefault(i, set())  # mark as fetched
                time.sleep(1)  # be polite to the public endpoint
            frontier = {p for ps in parents.values() for p in ps} - parents.keys()
            print(f"   round {rounds}: {len(parents)} nodes, {len(frontier)} new")

    print("3/3 keeping plants and writing the CSV...")
    memo: dict[str, bool] = {}

    def is_plant(node: str, seen: frozenset = frozenset()) -> bool:
        if node == PLANTAE:
            return True
        if node in memo:
            return memo[node]
        if node in seen:  # Wikidata has a few parent cycles
            return False
        result = any(is_plant(p, seen | {node}) for p in parents.get(node, ()))
        memo[node] = result
        return result

    sys.setrecursionlimit(10_000)
    out_rows = []
    seen_sci: set[str] = set()
    for item, taxon in taxa.items():
        if not is_plant(item):
            continue
        sci = taxon["sci"].strip()
        he = clean_hebrew(taxon["he"])
        en = taxon["en"].strip()
        if not en or en == sci:  # English label is often just the Latin name
            en = min(taxon["common"], key=len) if taxon["common"] else sci
        if not sci or not HEBREW.search(he) or sci in seen_sci:
            continue
        if max(len(sci), len(he), len(en)) > 120:
            continue
        seen_sci.add(sci)
        out_rows.append(
            {
                "scientific_name": sci,
                "name_en": en[:1].upper() + en[1:],
                "name_he": he,
                "wikidata_id": item,
            }
        )
    out_rows.sort(key=lambda r: r["scientific_name"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"   wrote {len(out_rows)} plants to {OUT}")


if __name__ == "__main__":
    main()
