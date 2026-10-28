import hashlib
import json
from pathlib import Path
import random
import numpy as np
import torch
from torch import nn
from torchvision import datasets, models, transforms

LABELS = ["angry","disgust","fear","happy","neutral","sad","surprise"]

class BaselineCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3,32,3,padding=1),nn.BatchNorm2d(32),nn.ReLU(),nn.MaxPool2d(2),
            nn.Conv2d(32,64,3,padding=1),nn.BatchNorm2d(64),nn.ReLU(),nn.MaxPool2d(2),
            nn.Conv2d(64,128,3,padding=1),nn.BatchNorm2d(128),nn.ReLU(),nn.MaxPool2d(2),
            nn.Conv2d(128,128,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d(1))
        self.classifier = nn.Sequential(nn.Flatten(),nn.Dropout(.35),nn.Linear(128,7))
    def forward(self,x):
        return self.classifier(self.features(x))

def build_model(name,pretrained=True):
    if name == "cnn":
        return BaselineCNN()
    if name == "resnet18":
        model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT if pretrained else None)
        model.fc = nn.Linear(model.fc.in_features,7)
        return model
    if name == "mobilenet_v3_small":
        model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features,7)
        return model
    raise ValueError("Unsupported architecture")

def transform(training=False):
    steps = [transforms.Resize((224,224))]
    if training:
        steps += [transforms.RandomHorizontalFlip(),transforms.RandomRotation(10),transforms.ColorJitter(brightness=.15,contrast=.15)]
    return transforms.Compose(steps+[transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])

def dataset(root,split,training=False):
    data = datasets.ImageFolder(Path(root)/split,transform=transform(training))
    if data.classes != LABELS:
        raise ValueError(f"Expected folders {LABELS}; found {data.classes}")
    return data

def seed_all(seed):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

def save_json(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
