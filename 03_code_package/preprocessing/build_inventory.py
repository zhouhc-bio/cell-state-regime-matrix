#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import html
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

ACCESSIONS = [
    ("GSE153596", "RNA_velocity", "mouse skin wound; project reports scVelo + CellRank completed"),
    ("GSE75748", "RNA_pseudotime", "hPSC progenitor/endoderm pseudotime validation"),
    ("GSE147298", "RNA_pseudotime_BMP_WNT", "mouse melanocyte stem cell BMP/WNT differentiation"),
    ("GSE178758", "RNA_ATAC_spatial", "mouse wound fibroblast fate; scRNA/scATAC/spatial"),
    ("GSE239276", "multiome_ATAC_RNA", "10x Multiome FOXA2 lineage plasticity; project reports processed"),
    ("GSE157660", "SNARE_seq2", "SNARE-seq2 RNA+ATAC benchmark"),
    ("GSE126074", "SNARE_seq", "SNARE-seq RNA+ATAC paired nuclei"),
    ("GSE90546", "Perturb_seq_CRISPRi", "CRISPRi Perturb-seq; R14 causal candidate"),
    ("GSE195467", "developmental_timecourse_candidate", "human somitogenesis time course; RA/BMP label requires confirmation"),
]


def fetch_text(url: str, timeout: int = 45) -> tuple[int | None, str, str]:
    req = Request(url, headers={"User-Agent": "Codex inventory scanner"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, raw.decode("utf-8", errors="replace"), ""
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, body, f"HTTPError: {e}"
    except URLError as e:
        return None, "", f"URLError: {e}"
    except Exception as e:
        return None, "", f"{type(e).__name__}: {e}"


def head_url(url: str, timeout: int = 30) -> dict[str, str]:
    req = Request(url, method="HEAD", headers={"User-Agent": "Codex inventory scanner"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return {
                "http_status": str(resp.status),
                "content_length": resp.headers.get("Content-Length", ""),
                "last_modified": resp.headers.get("Last-Modified", ""),
                "content_type": resp.headers.get("Content-Type", ""),
                "head_error": "",
            }
    except Exception as e:
        return {
            "http_status": "",
            "content_length": "",
            "last_modified": "",
            "content_type": "",
            "head_error": f"{type(e).__name__}: {e}",
        }


def series_dir(acc: str) -> str:
    digits = acc[3:]
    return f"GSE{digits[:-3]}nnn"


def geo_text_url(acc: str) -> str:
    return f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}&targ=self&form=text&view=quick"


def ftp_supp_dir(acc: str) -> str:
    return f"https://ftp.ncbi.nlm.nih.gov/geo/series/{series_dir(acc)}/{acc}/suppl/"


def parse_geo_soft(acc: str, text: str) -> dict[str, object]:
    fields: dict[str, object] = {
        "dataset": acc,
        "series_title": "",
        "series_summary": "",
        "series_overall_design": "",
        "sample_organism": [],
        "platform_organism": [],
        "supplementary_files": [],
        "sample_ids": [],
        "pubmed_id": "",
        "status": "",
        "last_update_date": "",
    }
    mapping = {
        "!Series_title": "series_title",
        "!Series_summary": "series_summary",
        "!Series_overall_design": "series_overall_design",
        "!Series_pubmed_id": "pubmed_id",
        "!Series_status": "status",
        "!Series_last_update_date": "last_update_date",
    }
    for line in text.splitlines():
        if " = " not in line:
            continue
        key, value = line.split(" = ", 1)
        if key in mapping:
            fields[mapping[key]] = value
        elif key == "!Series_sample_organism":
            fields["sample_organism"].append(value)
        elif key == "!Series_platform_organism":
            fields["platform_organism"].append(value)
        elif key == "!Series_supplementary_file":
            fields["supplementary_files"].append(value.replace("ftp://", "https://"))
        elif key == "!Series_sample_id":
            fields["sample_ids"].append(value)
    for k in ["sample_organism", "platform_organism", "supplementary_files", "sample_ids"]:
        vals = fields[k]
        if isinstance(vals, list):
            fields[k] = ";".join(dict.fromkeys(vals))
    return fields


def parse_filelist(acc: str, text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        kind, name, time, size, typ = parts[:5]
        rows.append(
            {
                "dataset": acc,
                "source": "ftp_filelist",
                "archive_or_file": kind,
                "file_name": name,
                "modified_or_reported_time": time,
                "size_bytes": size,
                "file_type": typ,
                "url": ftp_supp_dir(acc) + name,
                "http_status": "",
                "content_length": size if size.isdigit() else "",
                "last_modified": "",
                "content_type": "",
                "availability_note": "listed_in_filelist_txt",
            }
        )
    return rows


def parse_directory_index(acc: str, text: str) -> list[str]:
    names: list[str] = []
    for m in re.finditer(r'href="([^"]+)"', text):
        href = html.unescape(m.group(1))
        if href.startswith("/") or href.startswith("?") or href == "../":
            continue
        if href == "filelist.txt":
            continue
        names.append(href)
    return list(dict.fromkeys(names))


def file_type_from_name(name: str) -> str:
    lowered = name.lower()
    for suffix in [
        ".loom.gz",
        ".tar.gz",
        ".mtx.gz",
        ".mtx.txt.gz",
        ".tsv.gz",
        ".csv.gz",
        ".h5",
        ".tar",
        ".bed.gz",
        ".png.gz",
        ".json.gz",
    ]:
        if lowered.endswith(suffix):
            return suffix.lstrip(".").upper()
    return Path(name).suffix.lstrip(".").upper()


def inventory_remote() -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    dataset_rows: list[dict[str, object]] = []
    file_rows: list[dict[str, str]] = []
    for acc, category, project_note in ACCESSIONS:
        status, text, err = fetch_text(geo_text_url(acc))
        meta = parse_geo_soft(acc, text if text else "")
        meta.update(
            {
                "project_category": category,
                "project_note": project_note,
                "geo_text_url": geo_text_url(acc),
                "geo_http_status": status if status is not None else "",
                "geo_fetch_error": err,
                "ftp_supp_dir": ftp_supp_dir(acc),
            }
        )
        dataset_rows.append(meta)

        filelist_url = ftp_supp_dir(acc) + "filelist.txt"
        fl_status, fl_text, fl_err = fetch_text(filelist_url)
        parsed = parse_filelist(acc, fl_text) if fl_status == 200 and fl_text.startswith("#Archive/File") else []
        if parsed:
            file_rows.extend(parsed)
            continue

        # Fallback: SOFT supplementary file lines, then directory index if needed.
        supps = str(meta.get("supplementary_files", "")).split(";") if meta.get("supplementary_files") else []
        if not supps:
            idx_status, idx_text, idx_err = fetch_text(ftp_supp_dir(acc))
            names = parse_directory_index(acc, idx_text) if idx_status == 200 else []
            supps = [ftp_supp_dir(acc) + n for n in names]
            fallback_note = f"directory_index_status={idx_status}; error={idx_err}"
        else:
            fallback_note = f"filelist_status={fl_status}; filelist_error={fl_err}; from_SOFT_supplementary_file"

        for url in supps:
            if not url:
                continue
            url = url.replace("ftp://", "https://")
            name = Path(urlparse(url).path).name
            h = head_url(url)
            file_rows.append(
                {
                    "dataset": acc,
                    "source": "soft_or_directory_fallback",
                    "archive_or_file": "File_or_Archive",
                    "file_name": name,
                    "modified_or_reported_time": "",
                    "size_bytes": h.get("content_length", ""),
                    "file_type": file_type_from_name(name),
                    "url": url,
                    "http_status": h.get("http_status", ""),
                    "content_length": h.get("content_length", ""),
                    "last_modified": h.get("last_modified", ""),
                    "content_type": h.get("content_type", ""),
                    "availability_note": fallback_note + ("; " + h.get("head_error", "") if h.get("head_error") else ""),
                }
            )
    return dataset_rows, file_rows


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_command(path: Path) -> str:
    try:
        res = subprocess.run(["file", "-b", str(path)], check=False, text=True, capture_output=True)
        return res.stdout.strip()
    except Exception as e:
        return f"file_error:{e}"


def inventory_local() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        st = path.stat()
        rows.append(
            {
                "relative_path": rel,
                "size_bytes": st.st_size,
                "mtime_iso": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).astimezone().isoformat(),
                "suffix": "".join(path.suffixes),
                "file_type": file_command(path),
                "sha256": sha256(path),
                "inventory_note": classify_local(rel),
            }
        )
    return rows


def classify_local(rel: str) -> str:
    if rel.startswith("outputs/reproducible_workflows/"):
        return "workflow_artifact"
    if rel.startswith("outputs/"):
        if rel.endswith(".svg"):
            return "figure_or_schema_artifact"
        if rel.endswith(".tsv"):
            return "table_artifact"
        if rel.endswith(".md"):
            return "report_or_protocol_artifact"
        return "output_artifact"
    if rel == "work/gse90546_head.tar":
        return "partial_remote_archive_header"
    if rel.startswith("work/test_"):
        return "synthetic_smoke_test_artifact"
    if rel.startswith("work/"):
        return "working_script_or_intermediate"
    return "workspace_file"


def write_tsv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in columns})


def main() -> int:
    local_rows = inventory_local()
    dataset_rows, remote_file_rows = inventory_remote()

    write_tsv(
        OUT / "inventory_local_artifacts.tsv",
        local_rows,
        ["relative_path", "size_bytes", "mtime_iso", "suffix", "file_type", "sha256", "inventory_note"],
    )
    write_tsv(
        OUT / "inventory_geo_datasets.tsv",
        dataset_rows,
        [
            "dataset",
            "project_category",
            "project_note",
            "series_title",
            "sample_organism",
            "platform_organism",
            "series_summary",
            "series_overall_design",
            "sample_ids",
            "pubmed_id",
            "status",
            "last_update_date",
            "geo_text_url",
            "geo_http_status",
            "geo_fetch_error",
            "ftp_supp_dir",
            "supplementary_files",
        ],
    )
    write_tsv(
        OUT / "inventory_geo_supplementary_files.tsv",
        remote_file_rows,
        [
            "dataset",
            "source",
            "archive_or_file",
            "file_name",
            "modified_or_reported_time",
            "size_bytes",
            "file_type",
            "url",
            "http_status",
            "content_length",
            "last_modified",
            "content_type",
            "availability_note",
        ],
    )

    summary_rows: list[dict[str, object]] = []
    by_dataset: dict[str, list[dict[str, str]]] = {}
    for row in remote_file_rows:
        by_dataset.setdefault(row["dataset"], []).append(row)
    for acc, category, _note in ACCESSIONS:
        files = by_dataset.get(acc, [])
        total_bytes = 0
        known = 0
        for f in files:
            raw = f.get("size_bytes") or f.get("content_length") or ""
            try:
                total_bytes += int(raw)
                known += 1
            except Exception:
                pass
        summary_rows.append(
            {
                "dataset": acc,
                "project_category": category,
                "n_listed_remote_files": len(files),
                "n_files_with_known_size": known,
                "known_total_size_bytes": total_bytes if known else "",
                "inventory_status": "metadata_and_remote_file_inventory_complete" if files else "metadata_only_no_remote_files_listed",
            }
        )
    write_tsv(
        OUT / "inventory_summary.tsv",
        summary_rows,
        [
            "dataset",
            "project_category",
            "n_listed_remote_files",
            "n_files_with_known_size",
            "known_total_size_bytes",
            "inventory_status",
        ],
    )

    report = [
        "# Inventory Report: Unified Cell Fate Dynamical System",
        "",
        f"Generated: {datetime.now().astimezone().isoformat()}",
        "",
        "Scope: local workspace artifacts plus GEO metadata/supplementary-file inventory for the declared working dataset set.",
        "",
        "This report is inventory only. It contains no modeling, no state scoring, no GRN inference, and no attractor claims.",
        "",
        "## Local Workspace",
        "",
        f"- Files inventoried: {len(local_rows)}",
        f"- Total local bytes: {sum(int(r['size_bytes']) for r in local_rows)}",
        "- No full `.h5ad`, `.loom`, `.rds`, full 10x matrix directory, ATAC fragment file, or full GEO archive is present in the workspace inventory.",
        "- `work/gse90546_head.tar` is a partial archive header, not a complete dataset.",
        "",
        "## Remote GEO Dataset Inventory",
        "",
        f"- Accessions scanned: {len(ACCESSIONS)}",
        f"- Remote supplementary file/archive rows listed: {len(remote_file_rows)}",
        "",
        "| Dataset | Category | Listed files | Known bytes | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        report.append(
            f"| {row['dataset']} | {row['project_category']} | {row['n_listed_remote_files']} | "
            f"{row['known_total_size_bytes']} | {row['inventory_status']} |"
        )
    report.extend(
        [
            "",
            "## Inventory Tables",
            "",
            "- `inventory_local_artifacts.tsv`",
            "- `inventory_geo_datasets.tsv`",
            "- `inventory_geo_supplementary_files.tsv`",
            "- `inventory_summary.tsv`",
            "",
            "## Inventory Boundary",
            "",
            "Inventory completion means that available local artifacts and declared GEO remote listings have been enumerated. It does not mean raw data were downloaded or biological analyses were run.",
        ]
    )
    (OUT / "inventory_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("inventory complete")
    print(f"local_files={len(local_rows)}")
    print(f"geo_datasets={len(dataset_rows)}")
    print(f"geo_remote_files={len(remote_file_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
