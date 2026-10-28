import argparse
from pathlib import Path
import time
import numpy as np
import torch
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from .common import LABELS, dataset, sha, save_json

def main():
    p=argparse.ArgumentParser();p.add_argument("--dataset",required=True);p.add_argument("--model",required=True);p.add_argument("--output",default="test-report.json");p.add_argument("--batch-size",type=int,default=32)
    args=p.parse_args();torch.set_num_threads(4)
    model=torch.jit.load(args.model,map_location="cpu").eval()
    data=dataset(args.dataset,"test");loader=DataLoader(data,batch_size=args.batch_size)
    truth,pred,elapsed=[],[],0.0
    with torch.no_grad():
        model(torch.zeros(1,3,224,224))
        for images,targets in loader:
            start=time.perf_counter();scores=model(images);elapsed+=time.perf_counter()-start
            truth.extend(targets.tolist());pred.extend(scores.argmax(1).tolist())
    report={"split":"test","model_sha256":sha(args.model),"labels":LABELS,"samples":len(data),"accuracy":float(accuracy_score(truth,pred)),"macro_f1":float(f1_score(truth,pred,labels=list(range(7)),average="macro",zero_division=0)),"classification_report":classification_report(truth,pred,labels=list(range(7)),target_names=LABELS,output_dict=True,zero_division=0),"confusion_matrix":confusion_matrix(truth,pred,labels=list(range(7))).tolist(),"latency_ms_per_image":elapsed/len(data)*1000,"model_mb":Path(args.model).stat().st_size/1024**2,"note":"CPU batched classifier timing; excludes detection, network and decoding. Not webcam FPS."}
    save_json(args.output,report)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8,7));image=ax.imshow(report["confusion_matrix"],cmap="Greens");ax.set_xticks(range(7),LABELS,rotation=45,ha="right");ax.set_yticks(range(7),LABELS);ax.set_xlabel("Predicted label");ax.set_ylabel("True label");fig.colorbar(image,ax=ax)
    for i,row in enumerate(report["confusion_matrix"]):
        for j,value in enumerate(row):ax.text(j,i,str(value),ha="center",va="center",fontsize=8)
    fig.tight_layout();fig.savefig(Path(args.output).with_suffix(".png"),dpi=170);plt.close(fig)
    print(f"Accuracy={report['accuracy']:.4f}, Macro-F1={report['macro_f1']:.4f}. Saved {args.output}")

if __name__ == "__main__":main()
