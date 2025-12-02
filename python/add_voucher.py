#!/usr/bin/env python3
"""
add_voucher.py – CLI-Tool für Eingangs- und Ausgangsbelege
Nutzt gemeinsame Logik aus bhl_voucher_base.py
"""

import sys
import argparse
from bhl_voucher_base import process_voucher

def main():
    ap = argparse.ArgumentParser(
        description="Erfasst Eingangs- oder Ausgangsbelege (ZUGFeRD/XRechnung-fähig)."
    )
    ap.add_argument("pdf", help="Pfad zur PDF-Datei")
    ap.add_argument("base_dir", help="Basisverzeichnis (z. B. ./belege)")
    ap.add_argument(
        "--direction",
        choices=["incoming", "outgoing", "auto"],
        default="incoming",
        help="Richtung des Belegs: incoming, outgoing oder auto (Standard: incoming)",
    )

    args = ap.parse_args()

    process_voucher(args.pdf, args.base_dir, mode=args.direction)

if __name__ == "__main__":
    main()
