import requests
import json
import pandas as pd
import psycopg2
import time
import os
import zipfile
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
            password='1234',
            dbname='financial_data'
        )
        cur = conn.cursor()
        print("Database Connect Success")

        # 테이블 생성 및 복합 키 설정
        cur.execute('''
            CREATE TABLE IF NOT EXISTS public.assets (
                id SERIAL PRIMARY KEY,
                rcept_no TEXT,
                value TEXT,
                context TEXT,
                unit TEXT,
                CONSTRAINT assets_unique UNIQUE (rcept_no, value, context, unit)
            );
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS public.revenues (
                id SERIAL PRIMARY KEY,
                rcept_no TEXT,
                value TEXT,
                context TEXT,
                unit TEXT,
                CONSTRAINT revenues_unique UNIQUE (rcept_no, value, context, unit)
            );
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS public.labels (
                id SERIAL PRIMARY KEY,
                rcept_no TEXT,
                label_text TEXT,
                CONSTRAINT labels_unique UNIQUE (rcept_no, label_text)
            );
        ''')
        conn.commit()
        print("테이블 및 복합 키 설정 완료")
        return cur, conn
    except Exception as err:
        print(f"DB 연결 오류: {str(err)}")
        return None, None

# DB 연결 해제
def DBdisconnect():
    try:
        cur.close()
        conn.close()
        print("DB Connect Close")
    except:
        print("Error: Database Not Connected.")

# 상위 50 종목 조회
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

# CORPCODE.xml 파싱
def load_corp_code_dict(xml_path='CORPCODE.xml'):
    corp_dict = {}
    tree = ET.parse(xml_path)
    root = tree.getroot()

    for child in root.findall('list'):
        stock_code = child.find('stock_code').text
        corp_code = child.find('corp_code').text
        corp_name = child.find('corp_name').text
        if stock_code:
            corp_dict[stock_code] = {
                'corp_code': corp_code,
                'corp_name': corp_name
            }
    return corp_dict

# 종목코드 → 기업코드 매핑
def get_corp_codes_from_df(df, corp_code_dict):
    matched = []
    for _, row in df.iterrows():
        stock_code = row['stk_cd']
        corp_info = corp_code_dict.get(stock_code)
        if corp_info:
            matched.append({
                'stk_cd': stock_code,
                'stk_nm': row['stk_nm'],
                'corp_code': corp_info['corp_code'],
                'corp_name': corp_info['corp_name']
            })
        else:
            print(f"기업코드 매핑 실패: {stock_code}")
    return pd.DataFrame(matched)

# 접수번호 조회
def fetch_rcept_no(api_key, corp_code, bsns_year, reprt_code):
    url = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "000" and data.get("list"):
            for item in data["list"]:
                rcept_no = item.get("rcept_no")
                print(f"조회된 접수번호: {rcept_no}")
                return rcept_no
        else:
            print(f"접수번호 조회 실패: {data.get('message')}")
            return None
    except requests.RequestException as e:
        print(f"오류 발생: {str(e)}")
        return None

# XBRL/XML 파일 다운로드
def download_financial_document(api_key, rcept_no, save_dir="output"):
    extract_path = os.path.join(save_dir, rcept_no)
    zip_path = os.path.join(save_dir, f"{rcept_no}.zip")

    if os.path.exists(extract_path) and os.path.isdir(extract_path):
        print(f"기존 데이터가 {extract_path}에 이미 존재합니다.")
        return extract_path

    url = "https://opendart.fss.or.kr/api/fnlttXbrl.xml"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    params = {
        "crtfc_key": api_key,
        "rcept_no": rcept_no
    }
    try:
        response = requests.get(url, params=params, headers=headers, stream=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "N/A")
        if "application/zip" in content_type or "application/x-msdownload" in content_type:
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            with open(zip_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            print(f"ZIP 파일이 {zip_path}에 저장되었습니다.")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                for info in zip_ref.infolist():
                    original_filename = info.filename
                    try:
                        info.filename = info.filename.encode('cp437').decode('cp949')
                    except:
                        info.filename = original_filename
                    zip_ref.extract(info, extract_path)
            print(f"ZIP 파일이 {extract_path}에 압축 해제되었습니다.")
            return extract_path
        elif "application/xml" in content_type:
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            with open(zip_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            print(f"XML 파일이 {zip_path}에 저장되었습니다.")
            return zip_path
        else:
            print(f"응답이 ZIP 또는 XML 형식이 아님.")
            return None
    except requests.RequestException as e:
        print(f"다운로드 중 오류 발생: {str(e)}")
        return None

# XBRL 파일 파싱
def parse_xbrl_file(xbrl_path, rcept_no, batch_size=1000):
    try:
        ns = {
            'xbrl': 'http://www.xbrl.org/2003/instance',
            'ifrs': 'http://xbrl.ifrs.org/taxonomy/2010-03-31/ifrs',
            'dart': 'http://www.xbrl.or.kr/2007/taxonomy'
        }
        tree = ET.parse(xbrl_path)
        root = tree.getroot()
        contexts = {}
        for context in root.findall('.//xbrl:context', ns):
            context_id = context.get('id')
            period = context.find('.//xbrl:period', ns)
            instant = period.find('xbrl:instant', ns)
            start_date = period.find('xbrl:startDate', ns)
            end_date = period.find('xbrl:endDate', ns)
            if instant is not None:
                contexts[context_id] = f"Instant: {instant.text}"
            elif start_date is not None and end_date is not None:
                contexts[context_id] = f"Duration: {start_date.text} to {end_date.text}"
        assets_data = []
        revenues_data = []
        for elem in root.iter():
            if elem.tag.endswith('Assets'):
                context_ref = elem.get('contextRef')
                unit_ref = elem.get('unitRef')
                value = elem.text
                assets_data.append((rcept_no, value, contexts.get(context_ref, '알 수 없음'), unit_ref))
            if elem.tag.endswith('Revenue'):
                context_ref = elem.get('contextRef')
                unit_ref = elem.get('unitRef')
                value = elem.text
                revenues_data.append((rcept_no, value, contexts.get(context_ref, '알 수 없음'), unit_ref))
        if assets_data:
            insert_to_db('assets', assets_data, batch_size)
        if revenues_data:
            insert_to_db('revenues', revenues_data, batch_size)
    except ET.ParseError as e:
        print(f"XBRL 파싱 오류: {str(e)}")

# XML 파일 파싱
def parse_xml_file(xml_path, rcept_no, batch_size=1000):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        labels_data = []
        for label in root.findall('.//{http://www.xbrl.org/2003/linkbase}label'):
            label_text = label.text.strip() if label.text else ""
            if label_text:
                labels_data.append((rcept_no, label_text))
        if labels_data:
            insert_to_db('labels', labels_data, batch_size)
    except ET.ParseError as e:
        print(f"XML 파싱 오류: {str(e)}")

# DB 삽입 함수
def insert_to_db(table_name, data, batch_size=1000):
    try:
        cur, conn = DBconnect()
        if cur is None or conn is None:
            raise Exception("DB 연결 실패")
        if table_name == 'assets':
            insert_query = """
                INSERT INTO public.assets (rcept_no, value, context, unit)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT ON CONSTRAINT assets_unique DO NOTHING;
            """
        elif table_name == 'revenues':
            insert_query = """
                INSERT INTO public.revenues (rcept_no, value, context, unit)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT ON CONSTRAINT revenues_unique DO NOTHING;
            """
        elif table_name == 'labels':
            insert_query = """
                INSERT INTO public.labels (rcept_no, label_text)
                VALUES (%s, %s)
                ON CONFLICT ON CONSTRAINT labels_unique DO NOTHING;
            """
        else:
            raise ValueError(f"지원하지 않는 테이블 이름: {table_name}")
        for start in range(0, len(data), batch_size):
            batch = data[start:start + batch_size]
            for row in batch:
                cur.execute(insert_query, row)
            conn.commit()
            print(f"배치 삽입 완료 ({table_name}): {len(batch)} rows")
    except Exception as err:
        print(f"데이터 삽입 중 오류 ({table_name}): {str(err)}")
        if conn is not None:
            conn.rollback()
    finally:
        DBdisconnect()

# 메인 실행
if __name__ == "__main__":
    # 환경 변수에서 API 키 로드
    DART_API_KEY = os.getenv("API_KEY")
    if not DART_API_KEY:
        print("DART_API_KEY가 .env 파일에 설정되지 않았습니다. 종료합니다.")
        exit()

    # Kiwoom API 토큰
    MY_ACCESS_TOKEN = main.fn_au10001()
    params = {
        'trde_upper_tp': '2',
        'amt_qty_tp': '1',
        'mrkt_tp': 'P00101',
        'stex_tp': '1',
    }

    # 상위 50 종목 조회 및 상위 20개 추출
    df, cont_yn, next_key = fn_ka90003(MY_ACCESS_TOKEN, params)
    if df is None:
        print("상위 종목 데이터를 가져오지 못했습니다.")
        exit()
    df_top20 = df.head(20)
    print(f"\n상위 20 종목 데이터:\n{df_top20}")

    # 종목코드 → 기업코드 매핑
    corp_dict = load_corp_code_dict('CORPCODE.xml')
    corp_mapped_df = get_corp_codes_from_df(df_top20, corp_dict)
    print(f"\n기업코드 매핑 결과:\n{corp_mapped_df}")

    # 연도 범위 설정 (2022년부터 현재 연도까지)
    current_year = datetime.now().year
    years = range(2022, current_year + 1)
    reprt_codes = ['11011']

    # 각 종목에 대해 연도별 재무제표 처리
    for _, row in corp_mapped_df.iterrows():
        corp_code = row['corp_code']
        corp_name = row['corp_name']
        print(f"\n {row['stk_nm']} ({corp_name}) 처리 시작...")
        
        for year in years:
            for reprt_code in reprt_codes:
                print(f"연도: {year}, 보고서 코드: {reprt_code}")
                rcept_no = fetch_rcept_no(DART_API_KEY, corp_code, str(year), reprt_code)
                if rcept_no:
                    result = download_financial_document(DART_API_KEY, rcept_no)
                    if result:
                        if os.path.isdir(result):
                            for root, dirs, files in os.walk(result):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    if file.endswith(".xbrl"):
                                        parse_xbrl_file(file_path, rcept_no)
                                    elif file.endswith(".xml"):
                                        parse_xml_file(file_path, rcept_no)
                        else:
                            parse_xml_file(result, rcept_no)
                    time.sleep(1)
                else:
                    print(f"{year}년 {reprt_code} 보고서 접수번호 조회 실패")
                time.sleep(1)

    print("모든 작업 완료 !!!!!!!!!!!!")