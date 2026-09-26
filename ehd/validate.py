"""Cross-validate the parser against dplR, and check corpus-wide invariants.

Verifying our own output against itself cannot catch a systematic misreading of
the format, so the spans are compared against an independent implementation:
R's dplR::read.rwl, the community-standard Tucson reader.  Agreement on every
series' first and last measured year is the acceptance criterion.

dplR cannot read every file we can (it rejects BC years and some header
layouts), so the comparison is scoped to files both parsers accept, and the
size of that scope is reported rather than hidden.

Usage:
    python -m ehd.validate
"""

from __future__ import annotations

import collections
import csv
import os
import subprocess
import sys
import tempfile

from . import config, corpus


def build_reference(paths: list[str], out_csv: str) -> bool:
    """Run dplR over ``paths`` via a directory of symlinks."""
    script = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts",
        "dplr_reference.R",
    )
    with tempfile.TemporaryDirectory() as tmp:
        for p in paths:
            try:
                os.symlink(os.path.abspath(p), os.path.join(tmp, os.path.basename(p)))
            except OSError:
                pass
        proc = subprocess.run(
            ["Rscript", script, tmp, out_csv],
            capture_output=True,
            text=True,
        )
    if proc.returncode != 0:
        print("dplR failed:", proc.stderr[-2000:])
        return False
    for line in proc.stderr.splitlines():
        if "could not read" in line or "wrote" in line or "reading" in line:
            print("  dplR:", line.strip()[:160])
    return True


def load_reference(path: str) -> dict[tuple[str, str], tuple[int, int]]:
    ref: dict[tuple[str, str], tuple[int, int]] = {}
    with open(path) as fh:
        for row in csv.DictReader(fh):
            key = (row["file"], row["series"].strip())
            ref[key] = (int(float(row["first"])), int(float(row["last"])))
    return ref


def main(argv: list[str] | None = None) -> int:
    print("building corpus...")
    logs, stats = corpus.build_logs()
    print(f"  {stats.n_logs} logs from {stats.n_files_used} files")

    raw_dir = config.path(config.RAW, "itrdb", "europe")
    selected = corpus.select_files(
        sorted(
            os.path.join(raw_dir, f)
            for f in os.listdir(raw_dir)
            if f.endswith(".rwl")
        ),
        corpus.CorpusStats(),
    )
    paths = sorted(selected.values())

    out_csv = os.path.join(config.path(config.INTERIM), "dplr_reference.csv")
    print(f"running dplR over {len(paths)} files (this takes a few minutes)...")
    if not build_reference(paths, out_csv):
        return 1
    ref = load_reference(out_csv)
    print(f"  dplR produced {len(ref)} series")

    # Our logs, keyed the same way dplR keys them: (filename, series id), and in
    # the file's own year numbering - anchored logs are shifted onto the
    # calendar after parsing, which dplR knows nothing about.
    file_of_site = {site: os.path.basename(p) for site, p in selected.items()}
    mine: dict[tuple[str, str], tuple[int, int]] = {}
    for log in logs:
        fname = file_of_site.get(log.site)
        if fname:
            mine[(fname, log.series_id.strip())] = (
                log.first_year - log.year_shift,
                log.last_year - log.year_shift,
            )

    both = set(ref) & set(mine)
    agree = [k for k in both if ref[k] == mine[k]]
    differ = [k for k in both if ref[k] != mine[k]]
    only_dplr = set(ref) - set(mine)
    only_ours = set(mine) - set(ref)

    print("\n--- parser cross-validation vs dplR ---")
    print(f"  series compared        : {len(both)}")
    print(f"  spans agreeing         : {len(agree)}")
    print(f"  spans disagreeing      : {len(differ)}")
    print(f"  only dplR found        : {len(only_dplr)}")
    print(f"  only we found          : {len(only_ours)}")
    if both:
        print(f"  agreement rate         : {100 * len(agree) / len(both):.4f}%")

    for key in differ[:15]:
        print(f"    DIFF {key[0]} {key[1]}: dplR={ref[key]} ours={mine[key]}")
    if only_dplr:
        files = collections.Counter(k[0] for k in only_dplr)
        print("  files where dplR saw series we did not:", dict(files.most_common(5)))

    print("\n--- corpus invariants ---")
    bad = 0
    for log in logs:
        if log.last_year < log.first_year:
            bad += 1
        elif len(log.values) != log.n_rings:
            bad += 1
        elif log.values[0] is None or log.values[-1] is None:
            bad += 1
        elif not 0 < log.n_measured <= log.n_rings:
            bad += 1
    print(f"  logs failing invariants: {bad} of {len(logs)}")

    dating = collections.Counter(log.dating for log in logs)
    print(f"  dating: {dict(dating)}")

    return 0 if not differ and not bad else 1


if __name__ == "__main__":
    sys.exit(main())
