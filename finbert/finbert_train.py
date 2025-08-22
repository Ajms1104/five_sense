import pandas as pd
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt

# CSV 불러오기
test_df = pd.read_csv("./finbert/finance_big_test.csv")
train_val_df = pd.read_csv("finbert/finance_big_train.csv")

# 레이블 문자열을 숫자로 매핑
label_map = {'negative': 0, 'neutral': 1, 'positive': 2}
test_df['labels'] = test_df['labels'].map(label_map)
train_val_df['labels'] = train_val_df['labels'].map(label_map)

# test: 20%, 나머지 80%를 train/val로 사용
# train_val_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df['labels'])
print(train_val_df.shape)
# train/val: 90:10으로 분할
train_df, val_df = train_test_split(train_val_df, test_size=0.1, random_state=42, stratify=train_val_df['labels'])
print(train_df.shape)
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer

model_name = "snunlp/KR-FinBert-SC"
tokenizer = AutoTokenizer.from_pretrained(model_name)

class SentimentDataset(Dataset):
    def __init__(self, sentences, labels, tokenizer, max_length=256):
        self.sentences = sentences
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.sentences)

    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.sentences[idx],
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )
        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'labels': torch.tensor(self.labels[idx], dtype=torch.long)
        }

# Dataset 객체 생성
train_dataset = SentimentDataset(train_df['kor_sentence'].tolist(), train_df['labels'].tolist(), tokenizer)
val_dataset = SentimentDataset(val_df['kor_sentence'].tolist(), val_df['labels'].tolist(), tokenizer)
test_dataset = SentimentDataset(test_df['kor_sentence'].tolist(), test_df['labels'].tolist(), tokenizer)

# DataLoader 생성
train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=16)
test_loader = DataLoader(test_dataset, batch_size=16)

# 과적합 방지 EarlyStop
class EarlyStopping:
    def __init__(self, patience=3, delta=0.0, save_path='best_model.pt'):
        self.patience = patience
        self.counter = 0
        self.best_score = None
        self.early_stop = False
        self.delta = delta
        self.save_path = save_path

    def __call__(self, val_score, model):
        if self.best_score is None:
            self.best_score = val_score
            self.save_checkpoint(model)
        elif val_score < self.best_score + self.delta:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_score = val_score
            self.save_checkpoint(model)
            self.counter = 0

    def save_checkpoint(self, model):
        torch.save(model.state_dict(), self.save_path)
        pass

from transformers import AutoModelForSequenceClassification
from torch.optim import AdamW
from tqdm import tqdm

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(device)
model = AutoModelForSequenceClassification.from_pretrained(model_name)
model.to(device)

optimizer = AdamW(model.parameters(), lr=1e-5)

# 가중치
from sklearn.utils.class_weight import compute_class_weight
import numpy as np

class_weights = compute_class_weight(class_weight='balanced', classes=np.unique(train_df['labels']), y=train_df['labels'])
class_weights = torch.tensor(class_weights, dtype=torch.float).to(device)

print(class_weights)

from torch.nn import CrossEntropyLoss
loss_fn = CrossEntropyLoss(weight=class_weights)

train_losses = []
val_accuracies = []
val_losses = []
# 학습 루프

early_stopping = EarlyStopping(patience=2, save_path='best_model.pt')

epochs = 10
for epoch in range(epochs):
    model.train()
    train_loss = 0
    train_total = 0
    loop = tqdm(train_loader, desc=f"[Train] Epoch {epoch+1}")
    for batch in loop:
        optimizer.zero_grad()
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        # 라벨 불균형 가중치 부여
        outputs = model(input_ids, attention_mask=attention_mask)
        loss = loss_fn(outputs.logits, labels)

        loss.backward()
        optimizer.step()
        
        batch_size = labels.size(0)
        train_loss += loss.item() * batch_size
        train_total += batch_size

        loop.set_postfix(loss=loss.item())

    avg_train_loss = train_loss / train_total

    # validation
    model.eval()
    val_loss = 0
    correct = 0
    total = 0
    with torch.no_grad():
        for batch in val_loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss

            batch_size = labels.size(0)
            val_loss += loss.item() * batch_size
            total += batch_size

            preds = torch.argmax(outputs.logits, dim=1)
            correct += (preds == labels).sum().item()

    avg_val_loss = val_loss / total
    val_acc = correct / total

    train_losses.append(avg_train_loss)
    val_losses.append(avg_val_loss)
    val_accuracies.append(val_acc)

    print(f"Epoch {epoch + 1} - Train Loss: {avg_train_loss:.4f}, Val Loss: {avg_val_loss:.4f}, Val Acc: {val_acc:.4f}")
    early_stopping(val_acc, model)

    if early_stopping.early_stop:
        print("조기 종료 triggered. 학습을 중단합니다.")
        break

plt.figure(figsize=(10, 5))
plt.plot(train_losses, label='Train Loss', marker='o')
plt.plot(val_accuracies, label='Validation Accuracy', marker='s')
plt.title('Training Loss & Validation Accuracy per Epoch')
plt.xlabel('Epoch')
plt.ylabel('Value')
plt.legend()
plt.grid(True)
plt.show()

from sklearn.metrics import classification_report, accuracy_score

# 모델 불러오기
model.load_state_dict(torch.load('best_model.pt'))
model.eval()

all_preds = []
all_labels = []

with torch.no_grad():
    for batch in test_loader:
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        outputs = model(input_ids, attention_mask=attention_mask)
        preds = torch.argmax(outputs.logits, dim=1)

        all_preds.extend(preds.cpu().numpy())
        all_labels.extend(labels.cpu().numpy())

# 정확도 및 분류 리포트 출력
acc = accuracy_score(all_labels, all_preds)
total = len(all_labels)
incorrect = sum(p != l for p, l in zip(all_preds, all_labels))

print("[Test Set Evaluation]")
print(f"정확도 (Accuracy): {acc:.4f}")
print(f"전체 개수 (Total): {total}")
print(f"틀린 개수 (Incorrect): {incorrect}")
print()
print(classification_report(all_labels, all_preds, target_names=['negative', 'neutral', 'positive']))
