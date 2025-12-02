#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import pypandoc

def export_data(data, fmt="md", out_path=None):
    df = pd.DataFrame(data)
    if out_path is None:
        out_path = Path(f"report.{fmt}")

    if fmt == "csv":
        df.to_csv(out_path, index=False)
    elif fmt == "md":
        table = df.to_markdown(index=False)
        out_path.write_text(table)
    elif fmt == "pdf":
        md = df.to_markdown(index=False)
        tmp_md = Path(out_path).with_suffix(".tmp.md")
        tmp_md.write_text(md)
        pypandoc.convert_text(md, "pdf", format="md", outputfile=str(out_path), extra_args=["--standalone"])
        tmp_md.unlink(missing_ok=True)
    else:
        raise ValueError("Unsupported export format")

    return out_path
