"""Convert the licensed, user-provided FER2013 CSV, preserving official test split."""
import argparse
import csv
from pathlib import Path
import numpy as np
from PIL import Image

FER_LABELS = ["angry","disgust","fear","happy","sad","surprise","neutral"]
SPLITS = {"Training":"train","PublicTest":"val","PrivateTest":"test"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv",type=Path)
    parser.add_argument("--output",type=Path,default=Path("data/datasets/fer2013"))
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit("Output must be empty to prevent mixing dataset versions.")
    count = 0
    with args.csv.open(encoding="utf-8",newline="") as source:
        for index,row in enumerate(csv.DictReader(source)):
            split = SPLITS[row["Usage"]]; label = FER_LABELS[int(row["emotion"])]
            pixels = np.fromstring(row["pixels"],sep=" ",dtype=np.uint8)
            if len(pixels)!=2304:
                raise ValueError(f"Invalid image at row {index}")
            directory = args.output/split/label; directory.mkdir(parents=True,exist_ok=True)
            Image.fromarray(pixels.reshape(48,48)).save(directory/f"fer-{index:05d}.png")
            count+=1
    print(f"Converted {count} images to {args.output}. Run ai.audit_dataset before training.")

if __name__ == "__main__":
    main()
