import google.generativeai as genai
import os
from dotenv import load_dotenv
import time
import re
from tqdm import tqdm
from config import GEMINI_MODEL_NAME, MAX_RETRIES, RETRY_DELAY_MULTIPLIER, API_REQUEST_DELAY, GEMINI_PROMPT

# API에 한 번에 보낼 최대 토큰 수
# 시스템 프롬프트, 응답 토큰, 기타 오버헤드를 고려해야 함
MAX_TOKENS_PER_BATCH = 16000

# 시스템 프롬프트
system_prompt = GEMINI_PROMPT

def _get_sentiment_batch(model, batch: list):
    user_prompt = "".join([f"{i + 1}. {text}\n" for i, text in enumerate(batch)])
    response = model.generate_content(user_prompt)
    lines = response.text.strip().split('\n')

    scores = []
    for line in lines:
        match = re.search(r",\s*(-?\d+\.?\d*)$", line)
        if match:
            scores.append(float(match.group(1)))
        else:
            scores.append(0.0)  # 파싱 실패 시 중립(0.0)

    # 길이 불일치 시 예외 발생시켜 재처리 유도
    if len(scores) != len(batch):
        raise ValueError(f"Output length mismatch: Expected {len(batch)}, got {len(scores)}")

    return scores


def analyze_descriptions(texts: list) -> list:
    print("\nGemini API로 뉴스 본문 감성 점수 분석을 시작합니다 (토큰 기반 배치)...")
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: raise ValueError("GEMINI_API_KEY가 .env 파일에 설정되지 않았습니다.")
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(GEMINI_MODEL_NAME, system_instruction=system_prompt)

    all_scores = []
    current_index = 0

    with tqdm(total=len(texts), desc="Analyzing Texts") as pbar:
        while current_index < len(texts):
            # --- 1. 토큰 기반으로 동적 배치 생성 ---
            batch_texts = []
            batch_tokens = 0

            while current_index < len(texts):
                text_to_add = texts[current_index]

                # 현재 텍스트를 추가했을 때 토큰 수를 미리 계산
                # count_tokens는 리스트를 받아 전체 토큰 수를 계산
                temp_batch = batch_texts + [text_to_add]
                try:
                    tokens_for_temp_batch = model.count_tokens(temp_batch).total_tokens
                except Exception as e:
                    print(f"⚠️ 토큰 계산 중 에러 발생 (해당 텍스트 건너뜀): {e}")
                    pbar.update(1)  # 프로그레스 바 업데이트
                    current_index += 1  # 다음 텍스트로 이동
                    all_scores.append(0.0)  # 에러 발생 텍스트는 0.0으로 처리
                    continue

                if tokens_for_temp_batch > MAX_TOKENS_PER_BATCH and batch_texts:
                    # 토큰 한도를 초과하면 현재 배치를 확정하고 루프 종료
                    break
                else:
                    # 한도 이내이면 배치에 추가하고 인덱스 증가
                    batch_texts.append(text_to_add)
                    current_index += 1

            if not batch_texts:
                continue  # 처리할 배치가 없으면 다음으로

            # --- 2. 생성된 배치에 대해 API 호출 및 재시도 ---
            attempt = 1
            scores = []
            while attempt <= MAX_RETRIES:
                try:
                    scores = _get_sentiment_batch(model, batch_texts)
                    break  # 성공 시 재시도 루프 탈출
                except Exception as e:
                    print(f"API 에러 (배치 크기: {len(batch_texts)}): {e} (재시도 {attempt}/{MAX_RETRIES})")
                    attempt += 1
                    if attempt > MAX_RETRIES:
                        print(f"🚨 최종 실패. 해당 배치를 0.0으로 처리합니다.")
                        scores = [0.0] * len(batch_texts)  # 최종 실패 시 0.0으로 채움
                    else:
                        time.sleep(API_REQUEST_DELAY * (RETRY_DELAY_MULTIPLIER ** (attempt - 1)))

            all_scores.extend(scores)
            pbar.update(len(batch_texts))
            time.sleep(API_REQUEST_DELAY)

    return all_scores

