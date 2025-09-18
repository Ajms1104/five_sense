import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from collections import Counter
import re
from tqdm import tqdm
from config import FINBERT_MODEL_NAME, FINBERT_WEIGHT_PATH


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

def _split_sentences(text):
    sentences = re.split(r'(?<=[\.\?!])\s+|(?<=[다요죠])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def analyze_titles(titles: list) -> list:
    print("FinBERT 모델로 뉴스 제목 감성 분석을 시작합니다...")
    tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL_NAME)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 학습된 가중치 불러오기
    try:
        model.load_state_dict(torch.load(FINBERT_WEIGHT_PATH, map_location=device))
        print(f"'{FINBERT_WEIGHT_PATH}'에서 학습된 가중치를 성공적으로 불러왔습니다.")
    except FileNotFoundError:
        print(f"경고: '{FINBERT_WEIGHT_PATH}' 파일을 찾을 수 없어 사전 학습된 가중치를 그대로 사용합니다.")

    model.to(device)
    model.eval()  # 추론 모드로 설정

    label_map = {0: 'negative', 1: 'neutral', 2: 'positive'}

    overall_results = []
    for title in tqdm(titles, desc="Analyzing Titles with FinBERT"):
        # 1. 제목을 문장 단위로 분리
        sentences = _split_sentences(title)

        # 문장이 없는 경우 'neutral'로 처리
        if not sentences:
            overall_results.append('neutral')
            continue

        # 2. 문장별 감성 예측
        dataset = SentenceDataset(sentences, tokenizer)
        # 배치 사이즈는 너무 크지 않게 설정 (예: 16)
        loader = DataLoader(dataset, batch_size=16, shuffle=False)

        sentiments = []
        with torch.no_grad():
            for batch in loader:
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)

                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                preds = torch.argmax(outputs.logits, dim=1).tolist()
                sentiments.extend(preds)

        # 3. 문장별 감성 결과를 취합하여 제목의 전체 감성 결정
        # 가장 많이 등장한 감성을 전체 감성으로 선택
        counts = Counter(sentiments)
        overall_sentiment_num = counts.most_common(1)[0][0]

        # 숫자 레이블을 문자열 레이블로 변환하여 결과 리스트에 추가
        overall_results.append(label_map[overall_sentiment_num])

    return overall_results