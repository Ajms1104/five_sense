import google.generativeai as genai
import os
from dotenv import load_dotenv
import time
import re
from tqdm import tqdm
from config import GEMINI_MODEL_NAME, BATCH_SIZE, MAX_RETRIES, RETRY_DELAY_MULTIPLIER, API_REQUEST_DELAY

# 시스템 프롬프트 (모델의 역할과 출력 형식을 정의)
system_prompt = """
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


def _clean_label(label: str) -> str:
    label = label.strip().lower()
    if re.match(r"^(positive|neutral|negative)$", label):
        return label
    return "unknown"


def _get_sentiment_batch(model, batch: list, current_batch_index: int, attempt=1) -> list or str:
    user_prompt = ""
    for i, text in enumerate(batch, 1):
        user_prompt += f"{i}. {text}\n"

    try:
        response = model.generate_content(user_prompt)
        labels = response.text.strip().split('\n')
        cleaned_labels = []
        for label_with_num in labels:
            match = re.match(r"^\d+\.\s*(positive|neutral|negative)$", label_with_num.lower())
            if match:
                cleaned_labels.append(match.group(1))
            else:
                cleaned_labels.append(_clean_label(label_with_num))

        if len(cleaned_labels) != len(batch):
            print(f"⚠️ 길이 불일치! (재시도 {attempt}/{MAX_RETRIES}) - Batch: {current_batch_index}")
            if attempt < MAX_RETRIES:
                return "RETRY"
            else:
                print(f"최대 재시도 초과. Batch {current_batch_index}는 'unknown'으로 처리합니다.")
                return ["unknown"] * len(batch)

        return cleaned_labels

    except Exception as e:
        print(f"API 에러 발생: {e} (재시도 {attempt}/{MAX_RETRIES}) - Batch: {current_batch_index}")
        if attempt < MAX_RETRIES:
            return "RETRY"
        else:
            print(f"최대 재시도 초과. Batch {current_batch_index}는 'unknown'으로 처리합니다.")
            return ["unknown"] * len(batch)


def analyze_descriptions(texts: list) -> list:
    print(f"\n{GEMINI_MODEL_NAME}로 뉴스 본문 감성 분석을 시작합니다...")
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY가 .env 파일에 설정되지 않았습니다.")
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(GEMINI_MODEL_NAME, system_instruction=system_prompt)

    all_labels = []
    batches_to_retry = []

    # --- 1. 초기 라벨링 ---
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Initial Labeling"):
        current_batch_index = i // BATCH_SIZE
        batch = texts[i:i + BATCH_SIZE]
        labels = _get_sentiment_batch(model, batch, current_batch_index, attempt=1)

        if labels == "RETRY":
            batches_to_retry.append({"batch_index": current_batch_index, "data": batch, "attempt": 1})
            all_labels.extend(["PENDING"] * len(batch))  # 재처리 대상을 위한 임시값
        else:
            all_labels.extend(labels)

        time.sleep(API_REQUEST_DELAY)

    # --- 2. 재처리 루프 ---
    retry_pass = 0
    while batches_to_retry:
        retry_pass += 1
        print(f"\n--- 재처리 시도 #{retry_pass} ({len(batches_to_retry)}개 배치) ---")

        failed_batches_in_this_pass = batches_to_retry[:]
        batches_to_retry = []

        for item in tqdm(failed_batches_in_this_pass, desc=f"Retrying Pass {retry_pass}"):
            batch_idx, batch_data, attempt = item["batch_index"], item["data"], item["attempt"]

            # 재시도 딜레이 (점점 길어짐)
            delay = API_REQUEST_DELAY * (RETRY_DELAY_MULTIPLIER ** attempt)
            time.sleep(delay)

            new_attempt = attempt + 1
            retried_labels = _get_sentiment_batch(model, batch_data, batch_idx, attempt=new_attempt)

            start_index = batch_idx * BATCH_SIZE

            if retried_labels == "RETRY":
                if new_attempt < MAX_RETRIES:
                    item['attempt'] = new_attempt
                    batches_to_retry.append(item)
                else:
                    # 최종 실패 처리
                    for k in range(len(batch_data)):
                        all_labels[start_index + k] = "unknown"
            else:
                # 재처리 성공
                for k, label in enumerate(retried_labels):
                    all_labels[start_index + k] = label

    # --- 3. 최종 정리 ---
    # PENDING으로 남아있는 라벨을 'unknown'으로 최종 처리
    final_unknown_count = all_labels.count("PENDING")
    if final_unknown_count > 0:
        print(f"\n{final_unknown_count}개의 라벨이 재처리 후에도 PENDING 상태로 남아 'unknown'으로 최종 처리합니다.")
        all_labels = ["unknown" if label == "PENDING" else label for label in all_labels]

    # 최종 길이 검증 (안전장치)
    if len(all_labels) != len(texts):
        print(f"⚠️ 최종 라벨 개수({len(all_labels)})가 원본({len(texts)})과 다릅니다. 길이를 조정합니다.")
        all_labels += ["unknown"] * (len(texts) - len(all_labels))
        all_labels = all_labels[:len(texts)]

    return all_labels