import os
import sys
import urllib.request
import json
import re
import time
from datetime import datetime
import psycopg2
from psycopg2 import Error
from bs4 import BeautifulSoup
import pandas as pd
from urllib.error import HTTPError, URLError
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 네이버 API 인증 정보
client_id = os.getenv("YOUR_CLIENT_ID")
client_secret = os.getenv("YOUR_CLIENT_SECRET")

# =============================
# DB 연결 관련 함수
# =============================
def DBconnect():
    """데이터베이스에 연결합니다."""
    global cur, conn
    try:
        conn = psycopg2.connect(
            host='localhost',
            user='postgres',
            password='1234',  
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
            print("Table created successfully or already exists.")
        except Exception as e:
            print(f"Error setting up table: {str(e)}")
            conn.rollback()

        return cur, conn
    except Exception as err:
        print(f"Error connecting to database: {str(err)}")
        return None, None

def DBdisconnect():
    """데이터베이스 연결을 해제합니다."""
    try:
        if 'cur' in globals() and cur:
            cur.close()
        if 'conn' in globals() and conn:
            conn.close()
        print("DB Connect Close")
    except:
        print("Error: Database Not Connected.")

# =============================
# 텍스트 정제 및 유효성 검사
# =============================
def clean_text(text):
    """HTML 태그 제거 및 텍스트 정제"""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    cleaned = soup.get_text()
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def is_relevant(title, content, query, related_keywords=[]):
    """
    기사의 관련성을 판단하는 필터링 함수
    1. 제목에 검색어가 포함되어야 함 (가장 중요)
    2. (선택) 연관 키워드가 제목 또는 본문에 1개 이상 포함되어야 함
    """
    if query.lower() not in title.lower():
        return False
    if related_keywords:
        found_related = False
        full_text = title + " " + content
        for keyword in related_keywords:
            if keyword.lower() in full_text.lower():
                found_related = True
                break
        if not found_related:
            return False
    return True

# =============================
# 뉴스 원문 크롤링
# =============================
def get_naver_news_content(url, max_sentences=3, max_length=1000):
    """네이버 뉴스 원문 크롤링 (길이 제한 추가)"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req)
        if response.getcode() == 200:
            soup = BeautifulSoup(response.read(), 'html.parser')
            content = soup.find('article', {'id': 'dic_area'})
            if not content:
                content = soup.find('div', {'id': 'newsct_article'})
            if content:
                for el in content(['script', 'style', 'a', 'span', 'em']):
                    el.decompose()
                text = content.get_text().strip()
                sentences = re.split(r'[.?!]\s+', text)
                limited_sentences = sentences[:max_sentences]
                limited_text = ' '.join(limited_sentences)
                if len(limited_text) > max_length:
                    limited_text = limited_text[:max_length].rsplit(' ', 1)[0] + '...'
                return limited_text
            else:
                return "본문을 찾을 수 없습니다."
        else:
            return "페이지를 불러올 수 없습니다."
    except Exception as e:
        return f"에러 발생: {str(e)}"

# =============================
# 네이버 뉴스 API 호출
# =============================
def fetch_naver_news(query, display=100, start=1, max_retries=3):
    """네이버 뉴스 API로 데이터 가져오기 (지수 백오프 적용)"""
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
                time.sleep(2 ** attempt)
        except HTTPError as e:
            if e.code == 429:
                print(f"Rate limit exceeded. Retrying in {2 ** attempt} seconds...")
                time.sleep(2 ** attempt)
            else:
                print(f"HTTPError: {e}. Retrying...")
                time.sleep(2 ** attempt)
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Retrying...")
            time.sleep(2 ** attempt)
    print("API 요청 실패: 최대 재시도 횟수를 초과했습니다.")
    return None

# =============================
# 뉴스 데이터 전처리 및 필터링
# =============================
def process_and_filter_news(news_data, query, related_keywords=[]):
    """뉴스 데이터를 전처리하고, 관련성 필터를 적용"""
    if not news_data or 'items' not in news_data or not news_data['items']:
        return None

    df = pd.DataFrame(news_data['items'])
    df['query'] = query
    df['title'] = df['title'].apply(clean_text)
    
    df = df[df['link'].str.contains('n.news.naver.com')]
    if df.empty:
        return None

    df['full_content'] = df['link'].apply(get_naver_news_content)
    
    df['is_relevant'] = df.apply(
        lambda row: is_relevant(row['title'], row['full_content'], query, related_keywords),
        axis=1
    )
    
    original_count = len(df)
    df = df[df['is_relevant']].copy()
    filtered_count = len(df)
    print(f"필터링: {original_count}개 기사 중 {filtered_count}개 선택됨.")

    if df.empty:
        return None

    df['cleaned_text'] = df['title'] + " " + df['full_content']
    df['pubDate'] = pd.to_datetime(df['pubDate'], errors='coerce', format="%a, %d %b %Y %H:%M:%S %z")
    
    df = df[['query', 'title', 'full_content', 'pubDate', 'link', 'cleaned_text']]
    df = df.rename(columns={'full_content': 'description', 'pubDate': 'pub_date'})
    df = df.dropna(subset=['title', 'pub_date'])

    return df

# =============================
# 특정 날짜의 모든 뉴스 수집
# =============================
def fetch_all_news_for_date(query, target_date, related_keywords=[], display=100, max_pages=10):
    """특정 날짜의 관련 뉴스만 수집"""
    all_filtered_data = []
    target_dt = pd.to_datetime(target_date).date()

    for page in range(1, max_pages + 1):
        start = (page - 1) * display + 1
        if start > 1000:
            print("API 제한(start=1000)으로 조회를 중단합니다.")
            break

        print(f"페이지 {page} (start={start})에서 '{query}' 검색 중... ({target_date})")
        news_data = fetch_naver_news(query, display=display, start=start)
        
        if not news_data:
            break
        
        items = news_data.get('items', [])
        daily_items = []
        stop_fetching = False
        for item in items:
            pub_date = pd.to_datetime(item['pubDate'], errors='coerce', format="%a, %d %b %Y %H:%M:%S %z")
            if pub_date and pub_date.date() == target_dt:
                daily_items.append(item)
            elif pub_date and pub_date.date() < target_dt:
                stop_fetching = True
                break
        
        if not daily_items:
            print(f"페이지 {page}에 '{target_date}' 날짜의 뉴스가 없습니다.")
            if stop_fetching:
                print("목표 날짜 이전의 기사가 발견되어 검색을 조기 종료합니다.")
                break
            continue

        daily_news_data = {'items': daily_items}
        df = process_and_filter_news(daily_news_data, query, related_keywords)
        
        if df is not None and not df.empty:
            all_filtered_data.append(df)
            print(f"페이지 {page}: '{target_date}' 날짜의 관련 뉴스 {len(df)}개 수집 완료.")
        else:
            print(f"페이지 {page}: 유효한 관련 뉴스가 없습니다.")
        
        if stop_fetching:
            break
        time.sleep(0.5)

    if all_filtered_data:
        return pd.concat(all_filtered_data, ignore_index=True)
    return None

# =============================
# 날짜 범위의 뉴스 수집 (새로운 함수)
# =============================
def fetch_news_for_date_range(query, start_date, end_date=None, related_keywords=[], display=100, max_pages=10):
    """시작 날짜부터 종료 날짜까지의 관련 뉴스를 수집"""
    # 종료 날짜가 없으면 현재 날짜로 설정
    if end_date is None:
        end_date = datetime.now().date()
    else:
        end_date = pd.to_datetime(end_date).date()
    
    start_date = pd.to_datetime(start_date).date()
    
    # 날짜 범위 생성
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    all_data = []

    print(f"'{start_date}'부터 '{end_date}'까지의 뉴스를 수집합니다.")
    
    for single_date in date_range:
        print(f"\n=== {single_date.strftime('%Y-%m-%d')} 뉴스 수집 시작 ===")
        df = fetch_all_news_for_date(query, single_date, related_keywords, display, max_pages)
        if df is not None and not df.empty:
            all_data.append(df)
            print(f"{single_date.strftime('%Y-%m-%d')}: {len(df)}개의 관련 뉴스 수집 완료.")
        else:
            print(f"{single_date.strftime('%Y-%m-%d')}: 관련 뉴스가 없습니다.")
    
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        print(f"\n총 {len(final_df)}개의 관련 뉴스를 수집했습니다.")
        return final_df
    else:
        print("\n지정된 날짜 범위에서 관련 뉴스가 없습니다.")
        return None

# =============================
# DB 삽입
# =============================
def insert_to_db(df):
    """뉴스 데이터를 PostgreSQL에 삽입"""
    try:
        cur, conn = DBconnect()
        if not (cur and conn):
            raise Exception("DB 연결 실패")

        inserted_count = 0
        for _, row in df.iterrows():
            insert_query = """
            INSERT INTO company_news (query, title, description, pub_date, link, cleaned_text)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (title, pub_date) DO NOTHING;
            """
            cur.execute(insert_query, (
                row['query'], row['title'], row['description'],
                row['pub_date'], row['link'], row['cleaned_text']
            ))
            if cur.rowcount > 0:
                inserted_count += 1

        conn.commit()
        print(f"총 {inserted_count}개의 새로운 데이터가 DB에 삽입되었습니다.")

    except Exception as err:
        print(f"데이터 삽입 중 오류: {err}")
        if 'conn' in locals() and conn:
            conn.rollback()
    finally:
        DBdisconnect()

# =============================
# 실행 Main
# =============================
def main():
    # 모든 검색어에 공통으로 적용될 기본 연관 키워드
    COMMON_KEYWORDS = ["주식", "주가", "실적", "판매량", "AI", "시장", "전망", "목표주가", "매출", "영업이익"]

    query = input("검색어를 입력하세요 (예: 삼성전자): ").strip()
    if not query:
        print("검색어를 입력해야 합니다.")
        return
    # 날짜 설정
    start_date = input("시작 날짜를 입력하세요 (YYYY-MM-DD): ").strip()
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        print("시작 날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)")
        return

    end_date = input("종료 날짜를 입력하세요 (YYYY-MM-DD, 미입력 시 현재 날짜): ").strip()
    if end_date:
        try:
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            print("종료 날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)")
            return
    else:
        end_date = None  # 현재 날짜로 설정

    related_keywords = COMMON_KEYWORDS
    print(f"'{query}'에 대한 연관 키워드 필터링이 활성화됩니다: {related_keywords}")

    df = fetch_news_for_date_range(query, start_date, end_date, related_keywords)

    if df is not None and not df.empty:
        print(f"\n총 {len(df)}개의 관련 뉴스를 DB에 저장합니다.")
        print(df[['title', 'pub_date']].to_string(index=True))
        insert_to_db(df)
    else:
        print("\n수집된 관련 뉴스가 없습니다.")

if __name__ == "__main__":
    main()