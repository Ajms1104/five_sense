import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification
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


def _split_sentences(text: str) -> list:
    if not isinstance(text, str): return []
    sentences = re.split(r'(?<=[\.\?!])\s+|(?<=[다요죠])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def analyze_titles(titles: list) -> list:
    print("FinBERT 모델로 뉴스 제목 감성 점수 분석을 시작합니다...")
    tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL_NAME)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    try:
        model.load_state_dict(torch.load(FINBERT_WEIGHT_PATH, map_location=device))
        print(f"'{FINBERT_WEIGHT_PATH}'에서 학습된 가중치를 성공적으로 불러왔습니다.")
    except FileNotFoundError:
        print(f"경고: '{FINBERT_WEIGHT_PATH}' 파일을 찾을 수 없어 사전 학습된 가중치를 그대로 사용합니다.")

    model.to(device)
    model.eval()

    overall_scores = []
    score_weights = torch.tensor([-1, 0, 1]).to(device)

    for title in tqdm(titles, desc="Analyzing Titles with FinBERT"):
        sentences = _split_sentences(title)
        if not sentences:
            overall_scores.append(0.0)
            continue

        dataset = SentenceDataset(sentences, tokenizer)
        loader = DataLoader(dataset, batch_size=16, shuffle=False)

        sentence_scores = []
        with torch.no_grad():
            for batch in loader:
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)

                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                probabilities = torch.nn.functional.softmax(outputs.logits, dim=1)
                scores = (probabilities * score_weights).sum(dim=1)
                sentence_scores.extend(scores.cpu().tolist())

        title_score = sum(sentence_scores) / len(sentence_scores) if sentence_scores else 0.0
        overall_scores.append(title_score)

    return overall_scores