"""Three reproducible experiments. Run from repo root: python -m ai.train --help."""
import argparse
import copy
import json
from pathlib import Path
import time
import torch
from torch import nn
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score, f1_score
from .common import LABELS, build_model, dataset, seed_all, save_json
from .audit_dataset import audit

def epoch(model,loader,criterion,device,optimizer=None):
    model.train(optimizer is not None)
    # Keep pretrained batch statistics fixed during classifier-only warmup.
    if optimizer and not all(p.requires_grad for p in model.parameters()):
        for module in model.modules():
            if isinstance(module,nn.BatchNorm2d): module.eval()
    total,truth,pred = 0,[],[]
    with torch.set_grad_enabled(optimizer is not None):
        for inputs,targets in loader:
            inputs,targets = inputs.to(device),targets.to(device)
            outputs = model(inputs); loss = criterion(outputs,targets)
            if optimizer:
                optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step()
            total += loss.item()*len(targets)
            truth.extend(targets.cpu().tolist());pred.extend(outputs.argmax(1).detach().cpu().tolist())
    return {"loss":total/len(loader.dataset),"accuracy":float(accuracy_score(truth,pred)),"macro_f1":float(f1_score(truth,pred,labels=list(range(7)),average="macro",zero_division=0))}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dataset",required=True)
    parser.add_argument("--model",choices=["cnn","resnet18","mobilenet_v3_small"],default="mobilenet_v3_small")
    parser.add_argument("--output",default="ai/runs/mobilenet-v1")
    parser.add_argument("--epochs",type=int,default=30)
    parser.add_argument("--batch-size",type=int,default=32)
    parser.add_argument("--lr",type=float,default=1e-4)
    parser.add_argument("--warmup-epochs",type=int,default=3)
    parser.add_argument("--patience",type=int,default=7)
    parser.add_argument("--seed",type=int,default=42)
    parser.add_argument("--no-pretrained",action="store_true")
    parser.add_argument("--threads",type=int,default=4)
    args=parser.parse_args()
    if args.epochs<1 or args.batch_size<2 or args.lr<=0:
        parser.error("epochs>=1, batch-size>=2, lr>0")
    out=Path(args.output)
    if out.exists() and any(out.iterdir()):
        raise SystemExit("Output run directory must be empty; choose a new version.")
    out.mkdir(parents=True,exist_ok=True)
    seed_all(args.seed);torch.set_num_threads(args.threads)
    quality=audit(args.dataset);save_json(out/"dataset-audit.json",quality)
    if not quality["ok"]:
        raise SystemExit("Dataset audit failed. Fix errors/cross-split duplicates before training.")
    train,validation=dataset(args.dataset,"train",True),dataset(args.dataset,"val")
    generator=torch.Generator().manual_seed(args.seed)
    loaders=[DataLoader(d,batch_size=args.batch_size,shuffle=i==0,num_workers=0,generator=generator) for i,d in enumerate((train,validation))]
    device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model=build_model(args.model,not args.no_pretrained).to(device)
    weighted=torch.bincount(torch.tensor(train.targets),minlength=7).float()
    criterion=nn.CrossEntropyLoss(weight=(weighted.sum()/(7*weighted)).to(device))
    warmup=min(args.warmup_epochs,max(0,args.epochs-1)) if args.model!="cnn" and not args.no_pretrained else 0
    if warmup:
        for name,p in model.named_parameters():p.requires_grad=name.startswith("fc.") or name.startswith("classifier.")
    optimizer=torch.optim.AdamW(filter(lambda p:p.requires_grad,model.parameters()),lr=args.lr*5 if warmup else args.lr,weight_decay=1e-4)
    best,best_state,stale,history=-1,None,0,[]
    config={**vars(args),"device":str(device),"torch_version":torch.__version__,"labels":LABELS,"dataset_sha256":quality["dataset_sha256"],"preprocessing":"RGB 224x224 ImageNet normalization"}
    save_json(out/"config.json",config)
    for index in range(args.epochs):
        if warmup and index==warmup:
            for p in model.parameters():p.requires_grad=True
            optimizer=torch.optim.AdamW(model.parameters(),lr=args.lr,weight_decay=1e-4)
            stale=0
        start=time.perf_counter()
        row={"epoch":index+1,"train":epoch(model,loaders[0],criterion,device,optimizer),"val":epoch(model,loaders[1],criterion,device),"seconds":time.perf_counter()-start}
        history.append(row);save_json(out/"history.json",history)
        print(json.dumps(row),flush=True)
        if row["val"]["macro_f1"]>best:
            best=row["val"]["macro_f1"];best_state=copy.deepcopy(model.state_dict());stale=0
            torch.save({"state_dict":best_state,"config":config,"validation_macro_f1":best},out/"checkpoint.pth")
        else:stale+=1
        if stale>=args.patience and index>=warmup:break
    model.load_state_dict(best_state);model.cpu().eval()
    torch.jit.trace(model,torch.zeros(1,3,224,224)).save(str(out/"model.pt"))
    print(f"Best validation Macro-F1={best:.4f}. Exported {out/'model.pt'}. Test metrics not measured yet.")

if __name__ == "__main__":main()
