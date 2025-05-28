import pandas as pd

df = pd.read_csv("/content/drive/MyDrive/finance_train.csv")

label_map = {'negative': 0, 'neutral': 1, 'positive': 2}
# 'kor_sentence' 열만 선택하고 필요한 다른 열 유지
df_korean = df[['labels', 'kor_sentence']]
# df_korean['labels'] = df_korean['labels'].map(label_map)
# 데이터셋 확인
print(df_korean.head())

from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import torch

model_name = "snunlp/KR-FinBert-SC"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
# 예시로 하나의 문장을 토큰화
# inputs = tokenizer(df_korean['kor_sentence'].tolist(), padding=True, truncation=True, return_tensors='pt')
# print(inputs)

from torch.utils.data import Dataset, DataLoader

# Dataset 클래스 정의
class SentimentDataset(Dataset):
    def __init__(self, sentences, labels, tokenizer, max_length=256):
        self.sentences = sentences
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.label_map = {'negative': 0, 'neutral': 1, 'positive': 2}

    def __len__(self):
        return len(self.sentences)

    def __getitem__(self, idx):
        sentence = self.sentences[idx]
        label_str = self.labels[idx]
        label = self.label_map[label_str]

        encoding = self.tokenizer(sentence, padding='max_length',
                                  truncation=True, max_length=self.max_length,
                                  return_tensors='pt')

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }

# 데이터셋 준비
dataset = SentimentDataset(df_korean['kor_sentence'].tolist(), df_korean['labels'].tolist(), tokenizer)

# DataLoader 준비
dataloader = DataLoader(dataset, batch_size=16, shuffle=True)

from torch.optim import AdamW
from tqdm import tqdm

# optimizer 설정
optimizer = AdamW(model.parameters(), lr=1e-5)

# 학습 루프
model.train()
for epoch in range(3):
    loop = tqdm(dataloader, desc=f"Epoch {epoch+1}")
    for batch in loop:
        optimizer.zero_grad()

        # 모델 입력
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)

        # 모델 예측
        outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
        loss = outputs.loss
        logits = outputs.logits

        # 역전파
        loss.backward()
        optimizer.step()

        loop.set_postfix(loss=loss.item())

# 모델 저장
model_save_path = "/content/drive/MyDrive/model.pth"
torch.save(model.state_dict(), model_save_path)
print(f"Model saved at {model_save_path}")
