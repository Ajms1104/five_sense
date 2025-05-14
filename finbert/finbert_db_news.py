import psycopg2
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from tqdm import tqdm
import re
from collections import Counter

# 1. PostgreSQL에서 뉴스 데이터 불러오기
conn = psycopg2.connect(
    dbname="News_data",
    user="postgres",
    password="0000",
    host="localhost",
    port=5432
)
query = "SELECT * FROM company_news;"
df = pd.read_sql(query, conn)
conn.close()

news_list = df['cleaned_text'].tolist()

# 2. 모델 및 토크나이저 로드
model_name = "snunlp/KR-FinBert-SC"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# 학습된 가중치 불러오기
model.load_state_dict(torch.load("model.pth", map_location=device))
model.eval()

# 3. 문장 단위 토크나이징용 Dataset
class SentenceDataset(Dataset):
    def __init__(self, sentences, tokenizer, max_len=256):
        self.sentences = sentences
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.sentences)

    def __getitem__(self, idx):
        encoded = self.tokenizer(
            self.sentences[idx],
            padding='max_length',
            truncation=True,
            max_length=self.max_len,
            return_tensors='pt'
        )
        return {
            'input_ids': encoded['input_ids'].squeeze(0),
            'attention_mask': encoded['attention_mask'].squeeze(0)
        }

#  4. 정규표현식 기반 문장 분리 함수
def split_sentences(text):
    # "다", "요", "죠", 점 등 종결형과 공백 기준으로 문장 나누기
    sentences = re.split(r'(?<=[\.\?!])\s+|(?<=[다요죠])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

# 5. 문장 단위 감성 분석 함수
label_map = {0: 'negative', 1: 'neutral', 2: 'positive'}

def predict_sentiments(sentences):
    dataset = SentenceDataset(sentences, tokenizer)
    loader = DataLoader(dataset, batch_size=16, shuffle=False)

    results = []
    with torch.no_grad():
        for batch in loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            preds = torch.argmax(outputs.logits, dim=1).tolist()
            results.extend(preds)
    return results

# 6. 뉴스 하나당 종합 감성 분석
def analyze_article_sentiment(article_text):
    sentences = split_sentences(article_text)
    if not sentences:
        return 1, []  # 기본값 neutral
    sentiments = predict_sentiments(sentences)
    counts = Counter(sentiments)
    overall = counts.most_common(1)[0][0]
    return overall, [label_map[s] for s in sentiments]

# 7. 전체 뉴스 분석
overall_results = []
for news in tqdm(news_list, desc="Analyzing News Articles"):
    overall_label, sentence_labels = analyze_article_sentiment(news)
    overall_results.append(label_map[overall_label])

# 8. 결과 DataFrame에 추가 및 출력
df['predicted_label'] = overall_results
print(df[['cleaned_text', 'predicted_label']].head())

# csv 저장
# df.to_csv("News_DB_sentiment_results.csv", index=False)