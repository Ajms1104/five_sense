import psycopg2
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from tqdm import tqdm
import re
from collections import Counter
import os
from dotenv import load_dotenv
import google.generativeai as genai
import time

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
print(df.shape)
conn.close()

news_list = df['title'].tolist()

# 2. 모델 및 토크나이저 로드
model_name = "snunlp/KR-FinBert-SC"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# 학습된 가중치 불러오기
model.load_state_dict(torch.load("best_model.pt", map_location=device))
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

texts = df["description"].dropna().tolist()

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Google API 키 설정
genai.configure(api_key=api_key)

# Gemini 모델
model = genai.GenerativeModel("gemini-2.0-flash")

batch_size = 300  # 한번에 보낼 문장 수
all_labels = []
# 재처리할 배치와 해당 인덱스를 저장할 리스트
batches_to_retry = []
max_retries = 3 # 최대 재시도 횟수
retry_delay_multiplier = 2 # 재시도 시 딜레이 증가

def clean_label(label):
    label = label.strip().lower()
    if re.match(r"^(positive|neutral|negative)$", label):
        return label
    return "unknown"

# 감성 분석
def get_sentiment(batch, current_batch_index, attempt=1):
    prompt = """
다음은 한국어 금융 뉴스 문장들입니다. 각 문장의 감성을 오직 다음 세 가지 범주 중 하나로만 판단하여 출력해 주세요. 모든 판단은 금융 및 경제 분야의 전문적이고 객관적인 맥락에서 이루어져야 합니다.

positive: 시장, 경제 지표, 기업/산업의 성과, 투자 환경 등에서 명백하게 긍정적인 변화, 발전, 성공적인 기대, 탁월한 성과, 또는 뚜렷한 상향/개선 추세를 나타내는 경우.

예시 키워드: 상승, 증가, 개선, 호전, 회복, 강세, 확대, 성장, 낙관, 활황, 유리하게 작용, 기대치 상회, 흑자, 호황, 돌파, 최고치, 사상 최고, 성공적, 긍정적 영향, 효과 증대, 경쟁력 강화.
neutral: 특정 사건, 경제 지표, 시장 상황에 대한 객관적인 사실 전달, 현재 상태의 유지, 일반적인 정보 제공, 중립적인 상황 설명, 단순한 수치 기록, 혹은 불확실하거나 양면적인 의미를 포함하는 전망 등 감성적 판단이 배제된 경우. 명확한 긍정/부정의 경향이 드러나지 않을 때 이 범주를 사용합니다.

예시 키워드: 보도, 발표, 상황 설명, 기록, 유지, 전망, 관측, 분석, 조사, 언급, 예정, 포함, 형성, 변동, 변화, 집계, 보고서, 영향(중립적), 주목, 논의, 중립적, 불확실, 혼조세, 예측, 관망세, 의견.
negative: 시장, 경제 지표, 기업/산업의 성과, 투자 환경 등에서 명백하게 부정적인 변화, 문제 발생, 기대 이하의 성과, 또는 뚜렷한 하향/악화 추세를 나타내는 경우.

예시 키워드: 하락, 감소, 악화, 부진, 약세, 축소, 둔화, 우려, 손실, 적자, 불안, 위협, 붕괴, 저하, 압력, 경고, 불리하게 작용, 기대치 하회, 최저치, 위기, 부정적 영향, 부작용, 경쟁력 약화.
출력 형식:
각 문장 번호에 대해, 판단된 감성 레이블('positive', 'neutral', 'negative')만을 한 줄로 응답해 주세요. 다른 어떠한 설명이나 문구도 절대 포함하지 마세요. 각 문장 번호는 번호. 형식으로 시작해야 하며, 점 뒤에는 반드시 공백 하나를 포함해야 합니다.

예시:
주가가 크게 상승했습니다. -> positive
오늘 환율 변동은 미미했습니다. -> neutral
경제 성장률이 예상보다 낮아졌습니다. -> negative

정확한 감성 판단을 위한 핵심 기준:
문맥 우선: 단어 하나하나에 얽매이지 않고, 문장 전체가 전달하고자 하는 금융 및 경제적 메시지를 파악하여 감성을 판단합니다.
지배적 감성: 문장 내에 긍정적, 부정적, 중립적 요소가 혼재된 경우, 문장이 궁극적으로 표현하는 가장 강하고 명확한 감성적 방향성을 기준으로 분류합니다. 복합적인 내용이라도 한쪽 방향이 다른 쪽보다 뚜렷하게 우세하면 해당 감성으로 분류하고, 그렇지 않고 감성의 경중이 비슷하거나 불분명하면 'neutral'로 분류합니다.
단순한 사실 전달: 특정 지표의 수치 기록, 발표, 현상 유지 등은 감성적 판단 없이 'neutral'로 분류합니다. (예: "코스피 지수가 2,700포인트를 기록했다.")
감성적 함의가 있는 사실: 기록된 수치가 과거 대비 명확하게 긍정적이거나 부정적인 의미를 내포할 때는 해당 감성으로 분류합니다. (예: "코스피 지수가 사상 최고치를 경신했다." -> positive; "매출이 10년 만에 최저치를 기록했다." -> negative)
미래 전망: 미래에 대한 예측이나 전망이 명확하게 긍정적(예: "성장세가 지속될 것으로 기대")이거나 부정적(예: "경기가 더욱 악화될 것으로 우려")인 경우 해당 감성으로 분류합니다. '전망', '예측'과 같은 단어 자체는 중립적일 수 있으나, 그 내용이 감성적이면 내용을 우선합니다.
주체와 대상: 감성 표현이 누구(기업, 정부, 개인 등)나 무엇(산업, 시장, 상품)에 대한 것인지 명확히 파악하여 그 영향을 중심으로 판단합니다.
설득력: 판단 내린 감성이 객관적으로 설득력이 있어야합니다.
이제 아래 문장들에 대한 감성을 분석하여 순서대로 출력해 주세요:

"""
    for i, text in enumerate(batch, 1):
        prompt += f"{i}. {text}\n"

    try:
        response = model.generate_content(prompt)
        labels = response.text.strip().split('\n')
        cleaned_labels = []
        for label_with_num in labels:
            match = re.match(r"^\d+\.\s*(positive|neutral|negative)$", label_with_num.lower())
            if match:
                cleaned_labels.append(match.group(1))
            else:
                # 번호가 없거나 형식이 맞지 않으면 기존 clean_label로 정리
                cleaned_labels.append(clean_label(label_with_num))

        if len(cleaned_labels) != len(batch):
            print(f"⚠️ 길이 불일치 발생! (재시도 {attempt}/{max_retries}) - Batch index: {current_batch_index}")
            print(f"batch length: {len(batch)}")
            print(f"labels length: {len(cleaned_labels)}")
            print("response:\n", response.text)
            # 길이가 맞지 않으면 재시도 대상으로 추가
            if attempt < max_retries:
                print(f"재시도를 위해 {current_batch_index}번 배치를 추가합니다.")
                return "RETRY"
            else:
                print(f"최대 재시도 횟수({max_retries}) 초과. {current_batch_index}번 배치는 'unknown'으로 처리합니다.")
                # 최대 재시도 후에도 실패하면 'unknown'으로 채움
                return ["unknown"] * len(batch)

        return cleaned_labels
    except Exception as e:
        print(f"에러 발생: {e} (재시도 {attempt}/{max_retries}) - Batch index: {current_batch_index}")
        if attempt < max_retries:
            print(f"재시도를 위해 {current_batch_index}번 배치를 추가합니다.")
            return "RETRY"
        else:
            print(f"최대 재시도 횟수({max_retries}) 초과. {current_batch_index}번 배치는 'unknown'으로 처리합니다.")
            return ["unknown"] * len(batch)

# 초기 라벨링 및 재처리 큐 생성
for i in tqdm(range(0, len(texts), batch_size), desc="Initial Labeling"):
    current_batch_index = i // batch_size
    batch = texts[i:i+batch_size]
    labels = get_sentiment(batch, current_batch_index)

    if labels == "RETRY":
        batches_to_retry.append({"batch_index": current_batch_index, "data": batch, "attempt": 1})
        all_labels.extend(["PENDING"] * len(batch)) # 재처리할 위치에 임시 마커 삽입
    else:
        all_labels.extend(labels)

    time.sleep(30) # 요청 제한 방지 위해 딜레이

print(f"\n총 {len(batches_to_retry)}개의 배치가 재처리 대상으로 지정되었습니다.")

# 재처리 루프
retry_attempt_count = 0
while batches_to_retry:
    retry_attempt_count += 1
    print(f"\n--- 재처리 시도 {retry_attempt_count} ---")
    current_retries = batches_to_retry[:] # 현재 재시도할 배치 목록 복사
    batches_to_retry = [] # 다음 재시도를 위해 초기화

    for retry_item in tqdm(current_retries, desc=f"Retrying (Attempt {retry_attempt_count})"):
        batch_idx = retry_item["batch_index"]
        batch_data = retry_item["data"]
        attempt = retry_item["attempt"] + 1

        print(f"재시도 중: Batch index {batch_idx} (시도 {attempt}/{max_retries})")
        # 재시도 딜레이 적용 (점진적 증가)
        time.sleep(30 * (retry_delay_multiplier ** (attempt - 1)))

        retried_labels = get_sentiment(batch_data, batch_idx, attempt)

        if retried_labels == "RETRY":
            if attempt < max_retries:
                batches_to_retry.append({"batch_index": batch_idx, "data": batch_data, "attempt": attempt})
            else:
                # 최대 재시도 횟수를 초과하면 'unknown'으로 처리하고 PENDING 위치에 반영
                start_idx = batch_idx * batch_size
                for k in range(len(batch_data)):
                    if all_labels[start_idx + k] == "PENDING":
                        all_labels[start_idx + k] = "unknown"
                print(f"최대 재시도 횟수 초과로 Batch index {batch_idx}는 'unknown'으로 처리되었습니다.")
        else:
            # 성공적으로 라벨링 되면 해당 위치에 삽입
            start_idx = batch_idx * batch_size
            for k, label in enumerate(retried_labels):
                all_labels[start_idx + k] = label
            print(f"Batch index {batch_idx} 성공적으로 라벨링되었습니다.")

# 최종적으로 PENDING 상태로 남아있는 라벨이 있다면 'unknown'으로 처리
final_unknown_count = 0
for i in range(len(all_labels)):
    if all_labels[i] == "PENDING":
        all_labels[i] = "unknown"
        final_unknown_count += 1
if final_unknown_count > 0:
    print(f"\n{final_unknown_count}개의 라벨이 재처리 후에도 'unknown'으로 최종 처리되었습니다.")

# 본문 분석 결과
df = df.iloc[:len(all_labels)]
df["gemini_label"] = all_labels

#------ 제목-본문 불일치 시 'neutral'로 최종 라벨링 -------
# 1.
df['final_label'] = df['predicted_label']

# 2. 제목 라벨(predicted_label)과 본문 라벨(gemini_label)이 다른 행 마스킹
mismatched_mask = (df['predicted_label'] != df['gemini_label']) & (df['gemini_label'] != 'unknown')

# 3. 불일치하는 모든 행의 'final_label'을 'neutral'로 변경
df.loc[mismatched_mask, 'final_label'] = 'neutral'
#-----------------------------------------------------

# csv 저장
df.to_csv("News_DB_sentiment_results.csv", index=False)
