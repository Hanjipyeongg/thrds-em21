#!/usr/bin/env python3
"""Render @emmawt21 infographic images from 'Data Gambar' rows.

Usage:
  python3 render.py data.json            # render every row
  python3 render.py data.json --only EMMA-2026W41-1-1      # all images of one post
  python3 render.py data.json --only EMMA-2026W41-1-1-2    # one image of a post

data.json is either a list of objects keyed by the sheet's column names,
or the raw sheet values: [[header...], [row...], ...].

One row = one image. A post can have 1-4 images: give each row of that post
the same Post ID and a different "Urutan gambar" (1-4). An empty
"Urutan gambar" counts as 1.

Output: images/<Minggu ke>/<Post ID>-<Urutan gambar>.png (1080x1350) plus
manifest.json in the same folder. Each manifest entry has the raw GitHub URL
to give Buffer, and flags rows with missing fields or text that does not fit.
"""
import argparse, html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
REPO_RAW = "https://raw.githubusercontent.com/Hanjipyeongg/thrds-em21/main"

ICONS = {
    "%CHECK%": '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#141414" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    "%CHECK_SM%": '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#141414" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    "%CROSS%": '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#4D4A44" stroke-width="3.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    "%ARROW%": '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#141414" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h15M13 6l6 6-6 6"/></svg>',
    "%BOOKMARK%": '<svg width="30" height="34" viewBox="0 0 20 24" fill="#141414"><path d="M2 2.5C2 1.7 2.7 1 3.5 1h13c.8 0 1.5.7 1.5 1.5V23l-8-6-8 6z"/></svg>',
}

COMMON = ["Post ID", "Minggu ke", "Layout", "Label", "Sorotan", "Judul", "Subjudul"]
REQUIRED = {
    "checklist": COMMON + [f"Poin {i}" for i in range(1, 6)],
    "langkah": COMMON + [f"Poin {i}" for i in range(1, 6)],
    "perbandingan": COMMON + ["Label kiri", "Label kanan"]
    + [f"Kiri {i}" for i in range(1, 5)] + [f"Kanan {i}" for i in range(1, 5)],
    # Layout use case. "Tips" opsional di rumus dan contoh; "Rumus" opsional di contoh.
    "rumus": COMMON + ["Rumus", "Hasil", "Label kiri", "Label kanan"]
    + [f"Kiri {i}" for i in range(1, 5)] + [f"Kanan {i}" for i in range(1, 5)],
    "contoh": COMMON + ["Label kiri", "Label kanan"]
    + [f"Kiri {i}" for i in range(1, 5)] + [f"Kanan {i}" for i in range(1, 5)],
    "kasus": COMMON + [f"Poin {i}" for i in range(1, 6)],
}


def load_rows(path):
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if data and isinstance(data[0], list):
        header = [str(h).strip() for h in data[0]]
        rows = [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in data[1:]]
    else:
        rows = data
    return [{k: ("" if v is None else str(v).strip()) for k, v in r.items()} for r in rows if any(r.values())]


def image_id(row):
    return f"{row.get('Post ID', '')}-{row.get('Urutan gambar', '') or '1'}"


def fill(template, row):
    out = re.sub(r"%IF ([^%]+)%(.*?)%END%",
                 lambda m: m.group(2) if row.get(m.group(1)) else "", template, flags=re.S)
    for key, val in row.items():
        out = out.replace("{{" + key + "}}", html.escape(val))
    for key, svg in ICONS.items():
        out = out.replace(key, svg)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--only", help="render one Post ID (all its images) or one image id <Post ID>-<urutan>")
    args = ap.parse_args()

    rows = load_rows(args.data)
    for r in rows:
        r["Urutan gambar"] = r.get("Urutan gambar", "") or "1"
    if args.only:
        rows = [r for r in rows
                if r.get("Post ID") == args.only or image_id(r) == args.only]

    from playwright.sync_api import sync_playwright

    results = []
    seen = set()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        for row in rows:
            pid = row.get("Post ID", "")
            n = row["Urutan gambar"]
            iid = image_id(row)
            layout = row.get("Layout", "").strip().lower()
            entry = {"post_id": pid, "urutan": n, "image_id": iid, "layout": layout, "ok": False}
            if n not in {"1", "2", "3", "4"}:
                entry["error"] = f"Urutan gambar harus 1-4, bukan {n!r}"
                results.append(entry); continue
            if iid in seen:
                entry["error"] = f"Urutan gambar {n} dipakai dua kali untuk {pid}"
                results.append(entry); continue
            seen.add(iid)
            if layout not in REQUIRED:
                entry["error"] = f"Layout tidak dikenal: {row.get('Layout')!r}"
                results.append(entry); continue
            missing = [k for k in REQUIRED[layout] if not row.get(k)]
            if missing:
                entry["error"] = "Kolom kosong: " + ", ".join(missing)
                results.append(entry); continue

            tpl = (TEMPLATES / f"{layout}.html").read_text(encoding="utf-8")
            tmp = TEMPLATES / f"_render_{layout}.html"
            tmp.write_text(fill(tpl, row), encoding="utf-8")
            page.goto(tmp.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(150)
            overflow = page.evaluate(
                "(() => { const p = document.querySelector('.page');"
                " const f = document.querySelector('.foot');"
                " const prev = f.previousElementSibling.getBoundingClientRect();"
                " return p.scrollHeight > p.clientHeight || prev.bottom > f.getBoundingClientRect().top - 24; })()")
            week = row["Minggu ke"]
            out_dir = ROOT / "images" / week
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / f"{iid}.png"
            page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
            tmp.unlink()
            entry.update(ok=not overflow, file=str(out.relative_to(ROOT)),
                         url=f"{REPO_RAW}/images/{week}/{iid}.png")
            if overflow:
                entry["error"] = "Teks terlalu panjang dan menabrak footer; persingkat lalu render ulang"
            results.append(entry)
        browser.close()

    by_week = {}
    for r in results:
        if r.get("file"):
            by_week.setdefault(pathlib.Path(r["file"]).parent, []).append(r)
    for folder, entries in by_week.items():
        manifest = ROOT / folder / "manifest.json"
        existing = json.loads(manifest.read_text()) if manifest.exists() else []
        new_ids = {x["image_id"] for x in entries}
        keep = [e for e in existing if e.get("image_id", e["post_id"]) not in new_ids]
        merged = sorted(keep + entries, key=lambda e: (e["post_id"], e.get("urutan", "1")))
        manifest.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps(results, ensure_ascii=False, indent=1))
    sys.exit(0 if all(r["ok"] for r in results) else 1)


if __name__ == "__main__":
    main()
