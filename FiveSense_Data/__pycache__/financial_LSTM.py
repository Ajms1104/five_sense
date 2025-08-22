import requests
import pandas as pd
import psycopg2
import time
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv
from requests.exceptions import RequestException
import main  # buyTop50.py에서 사용한 main 모듈 가정

# .env 파일에서 환경 변수 로드
load_dotenv()

# DB 연결 함수
def DBconnect():
    global cur, conn
    try:
        conn = psycopg2.connect(
            host='localhost',
            user='postgres',
            password='5692',
            dbname='financial_data'
        )
        cur = conn.cursor()
        print("Database Connect Success")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS public.financial_statement (
                id SERIAL PRIMARY KEY,
                rcept_no TEXT,
                reprt_code TEXT,
                bsns_year TEXT,
                corp_code TEXT,
                stock_code TEXT,
                stlm_dt TEXT,
                idx_cl_code TEXT,
                idx_cl_nm TEXT,
                idx_code TEXT,
                idx_nm TEXT,
                idx_val TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT financial_statement_unique UNIQUE (rcept_no, reprt_code, bsns_year, corp_code, stock_code)
            );
        ''')
        conn.commit()
        print("테이블 설정 완료")
        return cur, conn
    except Exception as err:
        print(f"DB 연결 오류: {str(err)}")
        return None, None

# DB 연결 해제
def DBdisconnect():
    try:
        if 'cur' in globals() and 'conn' in globals():
            cur.close()
            conn.close()
            print("DB Connect Close")
    except:
        print("Error: Database Not Connected.")

# CORPCODE.xml 파싱 (stock_code → corp_code 매핑 , 종목코드에서 기업코드 변환)
def load_corp_code_dict(xml_path='CORPCODE.xml'):
    corp_dict = {}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for child in root.findall('list'):
            stock_code = child.find('stock_code').text
            corp_code = child.find('corp_code').text
            if stock_code and corp_code:
                corp_dict[stock_code] = corp_code
    except ET.ParseError as e:
        print(f"XML 파싱 오류: {e}")
    return corp_dict

# 데이터 조회
def fetch_data(api_key, corp_code, bsns_year, reprt_code, stlm_dt, idx_cl_code):
    url = "https://opendart.fss.or.kr/api/fnlttSinglIndx.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
        "stlm_dt": stlm_dt,
        "idx_cl_code": idx_cl_code
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "000" and data.get("list"):
            return data.get("list")
        else:
            print(f"데이터 조회 실패: {data.get('message')}")
            return None
    except requests.RequestException as e:
        print(f"오류 발생: {str(e)}")
        return None

# DB 삽입 함수
def insert_to_db(data_list, cur, conn):
    try:
        insert_query = """
            INSERT INTO public.financial_statement (rcept_no, reprt_code, bsns_year, corp_code, stock_code, stlm_dt, idx_cl_code, idx_cl_nm, idx_code, idx_nm, idx_val)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ON CONSTRAINT financial_statement_unique DO NOTHING;
        """
        for item in data_list:
            cur.execute(insert_query, (
                item.get("rcept_no"),
                item.get("reprt_code"),
                item.get("bsns_year"),
                item.get("corp_code"),
                item.get("stock_code"),
                item.get("stlm_dt"),
                item.get("idx_cl_code"),
                item.get("idx_cl_nm"),
                item.get("idx_code"),
                item.get("idx_nm"),
                item.get("idx_val")
            ))
        conn.commit()
        print("데이터 삽입 완료:", data_list)
    except Exception as err:
        print(f"데이터 삽입 중 오류: {str(err)}")
        conn.rollback()

# 상위 50 종목 조회 (buyTop50.py와 통합)
def fn_ka90003(token, data, max_retries=3, max_items=50):
    host = 'https://mockapi.kiwoom.com'
    endpoint = '/api/dostk/stkinfo'
    url = host + endpoint

    all_data = []
    cont_yn = 'N'
    next_key = ''
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'ka90003',
    }

    while len(all_data) < max_items:
        headers['cont-yn'] = cont_yn
        headers['next-key'] = next_key

        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=data)
                if response.status_code == 429:
                    print(f"429 Too Many Requests. 재시도 {attempt + 1}/{max_retries}")
                    time.sleep(2 ** attempt)
                    continue
                if response.status_code == 200:
                    response_data = response.json()
                    prm_list = response_data.get('prm_netprps_upper_50', [])
                    all_data.extend(prm_list)
                    cont_yn = response.headers.get('cont-yn', 'N')
                    next_key = response.headers.get('next-key', '')
                    break
                else:
                    print(f"API 요청 실패: {response.status_code}")
                    return None, None, None
            except RequestException as e:
                print(f"요청 중 오류: {e}")
                time.sleep(2 ** attempt)

        if cont_yn != 'Y':
            break

    all_data = all_data[:max_items]
    if not all_data:
        return None, None, None

    df = pd.DataFrame(all_data)
    df = df[['rank', 'stk_cd', 'stk_nm', 'cur_prc', 'acc_trde_qty']]
    df['rank'] = df['rank'].astype(int)
    df['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df = df.drop_duplicates(subset=['stk_cd']).sort_values(by='rank').reset_index(drop=True)
    return df, cont_yn, next_key

# 메인 실행
if __name__ == "__main__":
    # 환경 변수에서 API 키 로드
    DART_API_KEY = os.getenv("API_KEY")
    if not DART_API_KEY:
        print("DART_API_KEY가 .env 파일에 설정되지 않았습니다. 종료합니다.")
        exit()

    # DB 연결
    cur, conn = DBconnect()
    if cur is None or conn is None:
        exit()

    # 키움증권 API 토큰
    MY_ACCESS_TOKEN = main.fn_au10001()
    params = {
        'trde_upper_tp': '2',
        'amt_qty_tp': '1',
        'mrkt_tp': 'P00101',
        'stex_tp': '1',
    }

    # 상위 50 종목 조회 및 추출
    df, cont_yn, next_key = fn_ka90003(MY_ACCESS_TOKEN, params)
    if df is None:
        print("상위 종목 데이터를 가져오지 못했습니다.")
        exit()
    df_top20 = df.head(50)
    print(f"\n상위 50 종목 데이터:\n{df_top20}")

    # stock_code를 buyTop50.py 결과에서 추출
    stock_codes = df_top20['stk_cd'].tolist()

    # stock_code를 corp_code로 변환
    corp_dict = load_corp_code_dict()
    for stock_code in stock_codes:
        corp_code = corp_dict.get(stock_code)
        if not corp_code:
            print(f"stock_code {stock_code}에 해당하는 corp_code를 찾을 수 없습니다. CORPCODE.xml을 확인하세요.")
            continue

        reprt_code = "11011"    # 사업보고서
        idx_cl_code = "M210000" # 수익성지표

        # 연도 범위 설정
        current_year = datetime.now().year
        years = range(2020, current_year + 1)

        # 결산기준일 설정 (연도-12-31)
        stlm_dt = lambda year: f"{year}-12-31"

        # 각 연도별 데이터 조회 및 저장
        for year in years:
            print(f"\n{stock_code} - {year}년 데이터 처리 시작...")
            data_list = fetch_data(DART_API_KEY, corp_code, str(year), reprt_code, stlm_dt(year), idx_cl_code)
            if data_list:
                insert_to_db(data_list, cur, conn)
            else:
                print(f"{stock_code} - {year}년 데이터 조회 실패")
            time.sleep(1)

    # DB 연결 해제
    DBdisconnect()
    print("모든 작업 완료 !!!!!!!!!!!!")