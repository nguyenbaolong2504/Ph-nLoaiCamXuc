import argparse
import csv
import json
from pathlib import Path

if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("reports",nargs="+");p.add_argument("--output",default="comparison.csv");args=p.parse_args()
    with Path(args.output).open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.writer(file);writer.writerow(["report","accuracy","macro_f1","latency_ms_per_image","model_mb"])
        for path in args.reports:
            data=json.loads(Path(path).read_text(encoding="utf-8"))
            writer.writerow([path,*[data[key] for key in ["accuracy","macro_f1","latency_ms_per_image","model_mb"]]])
    print(args.output)
