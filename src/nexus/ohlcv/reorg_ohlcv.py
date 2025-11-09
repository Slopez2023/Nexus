#!/usr/bin/env python3
"""
Reorganize OHLCV CSV files into nested folders.

Moves files matching ASSET-TF-WEEKS-data.csv into either:
  - asset-timeframe: src/data/ohlcv/{ASSET}/{TF}/{ASSET}-{TF}-{WEEKS}-data.csv
  - asset:          src/data/ohlcv/{ASSET}/{ASSET}-{TF}-{WEEKS}-data.csv

Defaults to dry-run. Use --apply to actually move files.
"""

import os
import re
import argparse
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # src/data/ohlcv

PATTERN = re.compile(r"^(?P<asset>[A-Za-z0-9]+)-(?P<tf>[0-9]+[mhd])-(?P<wks>[0-9]+)wks-data\.csv$")


def find_csvs(root: str):
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith('.csv'):
                yield dirpath, fn


def plan_moves(root: str, mode: str):
    plans = []
    for dirpath, fn in find_csvs(root):
        if os.path.basename(dirpath) in {".git", "__pycache__"}:
            continue
        m = PATTERN.match(fn)
        if not m:
            continue
        asset = m.group('asset').upper()
        tf = m.group('tf')
        src_path = os.path.join(dirpath, fn)
        rel = os.path.relpath(dirpath, root)
        # Determine desired destination directory based on mode
        if mode == 'asset-timeframe':
            desired_rel = os.path.join(asset, tf)
            dst_dir = os.path.join(root, desired_rel)
        elif mode == 'asset':
            desired_rel = asset
            dst_dir = os.path.join(root, desired_rel)
        else:
            desired_rel = ''
            dst_dir = root
        if rel == desired_rel:
            # already in desired place
            continue
        dst_path = os.path.join(dst_dir, fn)
        plans.append((src_path, dst_dir, dst_path))
    return plans


def main():
    ap = argparse.ArgumentParser(description="Organize OHLCV CSVs into nested folders (asset or asset/timeframe).")
    ap.add_argument('--root', default=BASE_DIR, help='Root ohlcv directory (default: this folder)')
    ap.add_argument('--mode', default='asset', choices=['asset','asset-timeframe'], help='Nesting mode (default: asset)')
    ap.add_argument('--apply', action='store_true', help='Execute moves (otherwise dry-run)')
    ap.add_argument('--overwrite', action='store_true', help='Overwrite if destination exists')
    args = ap.parse_args()

    plans = plan_moves(args.root, args.mode)
    if not plans:
        print("No files to move.")
        return 0

    print(f"Planned moves: {len(plans)}")
    for src_path, dst_dir, dst_path in plans:
        rel = os.path.relpath(src_path, args.root)
        rel_dst = os.path.relpath(dst_path, args.root)
        print(f" - {rel}  →  {rel_dst}")

    if not args.apply:
        print("Dry-run only. Re-run with --apply to perform moves.")
        return 0

    for src_path, dst_dir, dst_path in plans:
        os.makedirs(dst_dir, exist_ok=True)
        if os.path.exists(dst_path):
            if args.overwrite:
                os.remove(dst_path)
            else:
                print(f"Skip existing (use --overwrite): {dst_path}")
                continue
        shutil.move(src_path, dst_path)
        print(f"Moved: {src_path} → {dst_path}")

    print("Done.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
