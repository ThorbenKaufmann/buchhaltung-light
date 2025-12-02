#!/usr/bin/env python3
"""
add_outgoing_voucher.py – CLI-Tool für Ausgangsbelege
Wrapper für bhl_voucher_base.process_voucher()
"""

import sys
import argparse
from bhl_voucher_base import process_voucher

def main():
    ap = argparse.ArgumentParser(
        description="Erfasst Ausgangsbelege (Verkauf) – optional automatische Richtungserkennung."
    )
    ap.add_argument("pdf", help="Pfad zur PDF-Datei")
    ap.add_argument("base_dir", help="Basisverzeichnis (z. B. ./belege/ausgang)")
    ap.add_argument(
        "--direction",
        choices=["outgoing", "auto"],
        default="outgoing",
        help="Richtung: outgoing oder auto (Standard: outgoing)",
    )

    args = ap.parse_args()
    process_voucher(args.pdf, args.base_dir, mode=args.direction)

if __name__ == "__main__":
    main()
