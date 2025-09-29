import os
import sys
import urllib.request
import json
import re
import time
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2 import Error
from bs4 import BeautifulSoup
import pandas as pd
from urllib.error import HTTPError, URLError

# .env 파일 로드
load_dotenv()

# 네이버 API 인증 정보
client_id = os.getenv("YOUR_CLIENT_ID")
client_secret = os.getenv("YOUR_CLIENT_SECRET")


# DB 연결
def DBconnect():
    global cur, conn
    try:
        conn = psycopg2.connect(
            host='localhost',
            user='postgres',
            password='5692',
            dbname='News_data'
        )
        cur = conn.cursor()
        print("Database Connect Success")

        # 테이블 생성
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS company_news (
                    id SERIAL,
                    query VARCHAR(255),
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    pub_date TIMESTAMP,
                    link VARCHAR(512),
                    cleaned_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (title, pub_date)
                );
            """)
            conn.commit()
            print("Table created successfully or already exists with primary key (title, pub_date).")
        except Exception as e:
            print(f"Error setting up table: {str(e)}")
            conn.rollback()

        return cur, conn
    except Exception as err:
        print(f"Error connecting to database: {str(err)}")
        return None, None


# DB 닫기
def DBdisconnect():
    try:
        if cur:
            cur.close()
        if conn:
            conn.close()
        print("DB Connect Close")
    except:
        print("Error: Database Not Connected.")


def clean_text(text):
    """HTML 태그 제거 및 텍스트 정제"""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    cleaned = soup.get_text()
    cleaned = re.sub(r' +', ' ', cleaned).strip()
    return cleaned


def get_naver_news_content(url, max_sentences=3, max_length=300):
    """네이버 뉴스 원문 크롤링 (길이 제한 추가)"""
    try:
        response = urllib.request.urlopen(url)
        if response.getcode() == 200:
            soup = BeautifulSoup(response.read(), 'html.parser')
            content = soup.find('div', {'id': 'newsct_article'})

            if content:
                # 불필요한 스크립트 제거
                for script in content(['script', 'style']):
                    script.decompose()
                text = content.get_text().strip()

                # 문장 단위로 분리 (한글 문장 끝 표시: ., !, ?)
                sentences = re.split(r'[.?!]\s+', text)
                # 최대 문장 수 제한
                limited_sentences = sentences[:max_sentences]
                limited_text = ' '.join(limited_sentences)

                # 문자 수로 추가 제한 (공백 기준으로 잘라서 자연스럽게 마무리)
                if len(limited_text) > max_length:
                    limited_text = limited_text[:max_length].rsplit(' ', 1)[0] + '...'

                return limited_text
            else:
                return "본문을 찾을 수 없습니다."
        else:
            return "페이지를 불러올 수 없습니다."
    except Exception as e:
        return f"에러 발생: {str(e)}"


def fetch_naver_news(query, display=100, start=1, max_retries=3):
    """네이버 뉴스 API로 데이터 가져오기"""
    enc_text = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={enc_text}&display={display}&start={start}&sort=date"

    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)

    for attempt in range(max_retries):
        try:
            response = urllib.request.urlopen(request)
            rescode = response.getcode()
            if rescode == 200:
                response_body = response.read()
                return json.loads(response_body.decode('utf-8'))
            else:
                print(f"Error Code: {rescode}")
                return None
        except HTTPError as e:
            if e.code == 429:
                print(f"429 Too Many Requests 에러 발생. {attempt + 1}/{max_retries} 재시도 중...")
                time.sleep(2 ** attempt)
                continue
            print(f"HTTPError: {e}. {attempt + 1}/{max_retries} 재시도 중...")
            time.sleep(2 ** attempt)
        except URLError as e:
            print(f"URLError: {e}. {attempt + 1}/{max_retries} 재시도 중...")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"Unexpected error: {e}. {attempt + 1}/{max_retries} 재시도 중...")
            time.sleep(2 ** attempt)

    print("최대 재시도 횟수 초과. API 요청 실패")
    return None


def process_news_data(news_data, query):
    """뉴스 데이터를 데이터프레임으로 변환 및 전처리"""
    if not news_data or 'items' not in news_data:
        return None

    items = news_data['items']
    if not items:
        return None

    df = pd.DataFrame(items)
    df['query'] = query
    df['title'] = df['title'].apply(clean_text)

    # 원문 크롤링으로 description 대신 full_content 가져오기 (길이 제한 적용)
    df['full_content'] = df['link'].apply(lambda x: get_naver_news_content(x, max_sentences=3, max_length=1000))
    df['full_content'] = df['full_content'].apply(clean_text)

    # 본문을 찾을 수 없거나 에러가 발생한 경우 해당 행 제거
    df = df[~df['full_content'].str.startswith("본문을 찾을 수 없습니다")]
    df = df[~df['full_content'].str.startswith("페이지를 불러올 수 없습니다")]
    df = df[~df['full_content'].str.startswith("에러 발생")]

    # 본문이 비어 있지 않은 경우만 유지
    df = df[df['full_content'].str.strip() != ""]

    # cleaned_text 생성
    df['cleaned_text'] = df['title'] + " " + df['full_content']
    df['pubDate'] = pd.to_datetime(df['pubDate'], errors='coerce', format="%a, %d %b %Y %H:%M:%S %z")
    df['link'] = df['link'].fillna(df['originallink'])

    df = df[['query', 'title', 'full_content', 'pubDate', 'link', 'cleaned_text']]
    df = df.rename(columns={'full_content': 'description'})
    df = df.dropna(subset=['title', 'pubDate'])

    return df


def fetch_all_news(query, display=100, max_pages=10):
    """여러 페이지를 조회하여 뉴스 데이터 수집"""
    all_data = []

    for page in range(1, max_pages + 1):
        start = (page - 1) * display + 1
        if start > 1000:
            print("Reached maximum start value (1000). Stopping.")
            break

        print(f"Fetching page {page} (start={start}) for query '{query}'...")
        news_data = fetch_naver_news(query, display=display, start=start)
        if not news_data or 'items' not in news_data:
            print("No more data or error occurred.")
            break

        df = process_news_data(news_data, query)
        if df is None or df.empty:
            print("No valid data on this page.")
            break

        all_data.append(df)
        print(f"Page {page}: Collected {len(df)} items.")

        time.sleep(1)
        if len(news_data['items']) < display:
            print("Reached end of available data.")
            break

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None


def insert_to_db(df, batch_size=1000):
    """뉴스 데이터를 PostgreSQL에 배치 삽입"""
    try:
        cur, conn = DBconnect()
        if cur is None or conn is None:
            raise Exception("DB 연결 실패")

        for start in range(0, len(df), batch_size):
            batch = df[start:start + batch_size]
            print(f"배치 삽입 시작: {start} ~ {start + len(batch) - 1} 행")

            for _, row in batch.iterrows():
                insert_query = """
                INSERT INTO company_news (query, title, description, pub_date, link, cleaned_text)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (title, pub_date) DO NOTHING;
                """
                cur.execute(insert_query, (
                    row['query'],
                    row['title'],
                    row['description'],
                    row['pubDate'],
                    row['link'],
                    row['cleaned_text']
                ))

            conn.commit()
            print(f"배치 삽입 완료: {len(batch)} rows")

        print("모든 데이터 삽입 완료")

    except Exception as err:
        print("데이터 삽입 중 오류:", str(err))
        if conn is not None:
            conn.rollback()

    finally:
        DBdisconnect()


def main():
    query = input("검색어를 입력하세요 (예: 005930, 삼성전자, 주가예측): ").strip()
    if not query:
        print("검색어를 입력해야 합니다.")
        return

    print(f"검색어: {query}")
    df = fetch_all_news(query)

    if df is not None and not df.empty:
        print(f"총 {len(df)} rows 데이터를 삽입합니다.")
        print(df[['query', 'title', 'description']].to_string(index=True))
        insert_to_db(df, batch_size=1000)
    else:
        print("수집된 데이터가 없습니다.")


if __name__ == "__main__":
    main()
