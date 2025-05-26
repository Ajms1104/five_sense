import requests
import os
import zipfile
import xml.etree.ElementTree as ET
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# DB 연결
def DBconnect():
    global cur, conn
    try:
        conn = psycopg2.connect(host='localhost', user='postgres', password='1234', dbname='financial_data')
        cur = conn.cursor()
        print("Database Connect Success")

        # 테이블 생성 및 복합 키 설정
        try:
            # 자산 테이블 생성
            cur.execute('''
                CREATE TABLE IF NOT EXISTS public.assets (
                    id SERIAL PRIMARY KEY,
                    rcept_no TEXT,
                    value TEXT,
                    context TEXT,
                    unit TEXT
                );
            ''')
            cur.execute('''
                ALTER TABLE public.assets
                DROP CONSTRAINT IF EXISTS assets_unique;
            ''')
            cur.execute('''
                ALTER TABLE public.assets
                ADD CONSTRAINT assets_unique UNIQUE (rcept_no, value, context, unit);
            ''')

            # 매출 테이블 생성
            cur.execute('''
                CREATE TABLE IF NOT EXISTS public.revenues (
                    id SERIAL PRIMARY KEY,
                    rcept_no TEXT,
                    value TEXT,
                    context TEXT,
                    unit TEXT
                );
            ''')
            cur.execute('''
                ALTER TABLE public.revenues
                DROP CONSTRAINT IF EXISTS revenues_unique;
            ''')
            cur.execute('''
                ALTER TABLE public.revenues
                ADD CONSTRAINT revenues_unique UNIQUE (rcept_no, value, context, unit);
            ''')

            # 레이블 테이블 생성
            cur.execute('''
                CREATE TABLE IF NOT EXISTS public.labels (
                    id SERIAL PRIMARY KEY,
                    rcept_no TEXT,
                    label_text TEXT
                );
            ''')
            cur.execute('''
                ALTER TABLE public.labels
                DROP CONSTRAINT IF EXISTS labels_unique;
            ''')
            cur.execute('''
                ALTER TABLE public.labels
                ADD CONSTRAINT labels_unique UNIQUE (rcept_no, label_text);
            ''')

            conn.commit()
            print("테이블 및 복합 키 설정 완료")
        except Exception as e:
            print(f"테이블 설정 중 오류: {str(e)}")
            conn.rollback()

        return cur, conn
    except Exception as err:
        print(f"DB 연결 오류: {str(err)}")
        return None, None

# DB 닫기
def DBdisconnect():
    try:
        conn.close()
        cur.close()
        print("DB Connect Close")
    except:
        print("Error: Database Not Connected.")

# 접수번호 조회 함수
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

# 재무제표 XBRL 파일 다운로드 및 처리 함수 (중복 방지 추가)
def download_financial_document(api_key, rcept_no, save_dir="output"):
    extract_path = os.path.join(save_dir, rcept_no)
    zip_path = os.path.join(save_dir, f"{rcept_no}.zip")

    # 기존 데이터 존재 여부 확인
    if os.path.exists(extract_path) and os.path.isdir(extract_path):
        print(f"기존 데이터가 {extract_path}에 이미 존재합니다.")
        print("기존 데이터를 재사용합니다.")
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
        print("API 호출 시작...")
        response = requests.get(url, params=params, headers=headers, stream=True)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "N/A")
        print(f"응답 Content-Type: {content_type}")
        print(f"응답 상태 코드: {response.status_code}")
        print(f"응답 헤더: {response.headers}")
        print(f"응답 첫 100바이트: {response.content[:100]}")

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
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        try:
                            info.filename = info.filename.encode('cp437').decode('utf-8', errors='replace')
                        except (UnicodeEncodeError, UnicodeDecodeError):
                            print(f"파일 이름 인코딩 실패 (원본 유지): {original_filename}")
                    zip_ref.extract(info, extract_path)
            print(f"ZIP 파일이 {extract_path}에 압축 해제되었습니다.")

            extracted_files = []
            for root, dirs, files in os.walk(extract_path):
                for file in files:
                    extracted_files.append(os.path.join(root, file))
            print("추출된 파일 목록:")
            for file in extracted_files:
                print(f" - {file}")

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
            print(f"응답이 ZIP 또는 XML 형식이 아님. 예상치 못한 응답 (처음 1000자): {response.text[:1000]}")
            return None

    except requests.RequestException as e:
        print(f"다운로드 중 오류 발생: {str(e)}")
        return None

# XBRL 파일 파싱 및 DB 삽입 함수
def parse_xbrl_file(xbrl_path, rcept_no, batch_size=1000):
    try:
        ns = {
            'xbrl': 'http://www.xbrl.org/2003/instance',
            'ifrs': 'http://xbrl.ifrs.org/taxonomy/2010-03-31/ifrs',
            'dart': 'http://www.xbrl.or.kr/2007/taxonomy'
        }
        
        tree = ET.parse(xbrl_path)
        root = tree.getroot()
        print(f"XBRL 파일 {xbrl_path} 파싱 완료")
        print(f"루트 엘리먼트: {root.tag}")


        # 날짜 저장 함수코드
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
                print(f"자산 (Assets): {value}")
                print(f"컨텍스트: {contexts.get(context_ref, '알 수 없음')}")
                print(f"단위: {unit_ref}")

            if elem.tag.endswith('Revenue'):
                context_ref = elem.get('contextRef')
                unit_ref = elem.get('unitRef')
                value = elem.text
                revenues_data.append((rcept_no, value, contexts.get(context_ref, '알 수 없음'), unit_ref))
                print(f"매출 (Revenue): {value}")
                print(f"컨텍스트: {contexts.get(context_ref, '알 수 없음')}")
                print(f"단위: {unit_ref}")

        # DB에 자산 데이터 삽입
        if assets_data:
            insert_to_db('assets', assets_data, batch_size)

        # DB에 매출 데이터 삽입
        if revenues_data:
            insert_to_db('revenues', revenues_data, batch_size)

    except ET.ParseError as e:
        print(f"XBRL 파싱 오류: {str(e)}")

# 일반 XML 파일 파싱 및 DB 삽입 함수
def parse_xml_file(xml_path, rcept_no, batch_size=1000):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        print(f"XML 파일 {xml_path} 파싱 완료")
        print(f"루트 엘리먼트: {root.tag}")

        labels_data = []
        for label in root.findall('.//{http://www.xbrl.org/2003/linkbase}label'):
            label_text = label.text.strip() if label.text else ""
            if not label_text:  # 빈 레이블은 제외
                continue
            labels_data.append((rcept_no, label_text))
            print(f"레이블: {label_text}")

        # DB에 레이블 데이터 삽입
        if labels_data:
            insert_to_db('labels', labels_data, batch_size)

    except ET.ParseError as e:
        print(f"XML 파싱 오류: {str(e)}")

# 데이터베이스에 데이터 삽입
def insert_to_db(table_name, data, batch_size=1000):
    try:
        # DB 연결
        cur, conn = DBconnect()
        if cur is None or conn is None:
            raise Exception("DB 연결 실패")

        # 테이블별 삽입 쿼리
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

        # 배치 삽입
        for start in range(0, len(data), batch_size):
            batch = data[start:start + batch_size]
            print(f"배치 삽입 시작 ({table_name}): {start} ~ {start + len(batch) - 1} 행")

            for row in batch:
                cur.execute(insert_query, row)

            # 배치 커밋
            conn.commit()
            print(f"배치 삽입 완료 ({table_name}): {len(batch)} rows")

        print(f"모든 데이터 삽입 완료 ({table_name})")

    except Exception as err:
        print(f"데이터 삽입 중 오류 ({table_name}): {str(err)}")
        if conn is not None:
            conn.rollback()

    finally:
        DBdisconnect()

# 실행 구간
if __name__ == "__main__":
    # .env 파일에서 API 키 로드
    API_KEY = os.getenv("API_KEY")
    if not API_KEY:
        print("API_KEY가 .env 파일에 설정되지 않았습니다. 종료합니다.")
        exit()

    CORP_CODE = "00126380"  # 삼성전자 기업 코드(병렬코드로 수정예정.)
    BSNS_YEAR = "2020"  # 사업 연도
    REPRT_CODE = "11011"  # 사업보고서 코드(1분기보고서:11013, 반기보고서:11012, 3분기보고서:11014, 사업보고서:11011)

    rcept_no = fetch_rcept_no(API_KEY, CORP_CODE, BSNS_YEAR, REPRT_CODE)
    if not rcept_no:
        print("접수번호를 가져오지 못했습니다. 종료합니다.")
        exit()

    result = download_financial_document(API_KEY, rcept_no, save_dir="output")
    if result:
        print(f"다운로드 완료. 경로: {result}")

        if os.path.isdir(result):
            for root, dirs, files in os.walk(result):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file.endswith(".xbrl"):
                        parse_xbrl_file(file_path, rcept_no, batch_size=1000)
                    elif file.endswith(".xml"):
                        parse_xml_file(file_path, rcept_no, batch_size=1000)
        else:
            parse_xml_file(result, rcept_no, batch_size=1000)
            