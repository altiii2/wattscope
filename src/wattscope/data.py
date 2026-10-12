"""Download and convert the original UCI data without loading all 370 columns."""

from __future__ import annotations

import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

SOURCE_URL = "https://archive.ics.uci.edu/static/public/321/electricityloaddiagrams20112014.zip"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/321/electricityloaddiagrams20112014"
CLIENTS = [f"MT_{i:03d}" for i in range(1, 9)]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def download_archive(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and zipfile.is_zipfile(destination):
        return destination
    partial = destination.with_suffix(".zip.part")
    print("Downloading the original UCI archive (approximately 249 MB)...", flush=True)
    with urllib.request.urlopen(SOURCE_URL, timeout=180) as source, partial.open("wb") as target:
        while chunk := source.read(1024 * 1024):
            target.write(chunk)
    if not zipfile.is_zipfile(partial):
        raise ValueError("The downloaded response is not a valid ZIP archive.")
    partial.replace(destination)
    return destination


def aggregate_hourly(frame: pd.DataFrame) -> pd.DataFrame:
    """Treat source labels as interval ends: four quarter-hour kW readings -> kWh."""
    frame = frame.sort_index()
    if frame.index.has_duplicates:
        raise ValueError("Duplicate timestamps in source data.")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("Source index must contain timestamps.")
    if not np.isfinite(frame.to_numpy(dtype=float)).all() or (frame < 0).any().any():
        raise ValueError("Source readings must be finite and non-negative.")
    groups = frame.resample("h", closed="right", label="right")
    counts = groups.count()
    hourly = groups.sum() / 4.0
    # Initial/final partial hours cannot be compared with full hourly intervals.
    return hourly.loc[(counts == 4).all(axis=1)]


def prepare_data(root: Path, archive: Path | None = None) -> pd.DataFrame:
    root = Path(root)
    archive = archive or download_archive(root / "data" / "raw" / "electricity.zip")
    with zipfile.ZipFile(archive) as zipped:
        members = [name for name in zipped.namelist() if Path(name).name == "LD2011_2014.txt"]
        if len(members) != 1:
            raise ValueError("Could not identify the original UCI text file.")
        with zipped.open(members[0]) as stream:
            source = pd.read_csv(stream, sep=";", decimal=",", usecols=[0, *range(1, 9)])
    source = source.rename(columns={source.columns[0]: "timestamp"})
    source["timestamp"] = pd.to_datetime(source["timestamp"], errors="raise")
    source = source.set_index("timestamp")
    if list(source.columns) != CLIENTS:
        raise ValueError(f"Unexpected client identifiers: {source.columns.tolist()}")
    hourly = aggregate_hourly(source).loc["2013-01-01":"2015-01-01 00:00:00"]
    expected = pd.date_range(hourly.index[0], hourly.index[-1], freq="h")
    if not hourly.index.equals(expected.rename("timestamp")):
        raise ValueError("The selected hourly series is not contiguous.")
    destination = root / "data" / "hourly.csv.gz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    hourly.to_csv(
        destination, index_label="timestamp", float_format="%.8f", compression={"method": "gzip", "mtime": 0}
    )
    metadata = {
        "source": "UCI ElectricityLoadDiagrams20112014",
        "source_url": SOURCE_URL,
        "source_page": SOURCE_PAGE,
        "citation": "Trindade, A. (2015). ElectricityLoadDiagrams20112014. DOI: 10.24432/C58C86.",
        "license": "CC BY 4.0",
        "archive_sha256": sha256_file(archive),
        "processed_sha256": sha256_file(destination),
        "selection": "First eight source columns, fixed before model evaluation; not chosen by performance.",
        "clients": CLIENTS,
        "rows": len(hourly),
        "start": hourly.index.min().isoformat(),
        "end": hourly.index.max().isoformat(),
        "unit": "kWh",
        "aggregation": "Sum four 15-minute power readings and divide by four; hourly intervals end at label.",
        "clock": "Original normalized Portuguese local clock, naive timestamps; not UTC.",
        "source_caveats": [
            "UCI documents DST zero readings in March and combined readings in October; retained, not imputed.",
            "Leading zeros can represent clients not yet active, rather than physical zero demand.",
            "Interval-end interpretation is a documented preprocessing assumption, not a timezone correction.",
            "Historic anonymized consumption cannot establish current or commercial forecasting performance.",
        ],
    }
    (root / "data" / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Prepared {len(hourly):,} hourly rows for {len(CLIENTS)} predetermined clients.", flush=True)
    return hourly


def load_hourly(root: Path) -> pd.DataFrame:
    path = Path(root) / "data" / "hourly.csv.gz"
    frame = pd.read_csv(path, index_col="timestamp", parse_dates=["timestamp"])
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Hourly data must have a sorted, unique timestamp index.")
    if not np.isfinite(frame.to_numpy(dtype=float)).all() or (frame < 0).any().any():
        raise ValueError("Hourly data contains invalid readings.")
    if not frame.index.equals(pd.date_range(frame.index[0], frame.index[-1], freq="h", name="timestamp")):
        raise ValueError("Hourly data must have an uninterrupted hourly index.")
    return frame
