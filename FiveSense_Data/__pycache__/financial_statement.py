import requests
import pandas as pd
import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

# 환경 변수 로드
load_dotenv()
api_key = os.getenv("DART_API_KEY")

# 재무제표 관련 설정
fs_div = 'CFS'   # OFS:재무제표, CFS:연결재무제표

# 일단 1년 보고서만
reprt_codes = {
    '': '11011'
    # 1분기 보고서 : 11013
    # 반기 보고서 : 11012
    # 3분기 보고서 : 11014
    # 사업 보고서(1년) : 11011
}

# 가져올 값들
account_map = {
    '매출총이익': 'gross_profit',
    '영업이익': 'operating_income',
    '영업이익(손실)': 'operating_income',
    '자산총계': 'total_assets',
    '부채총계': 'total_liabilities',
    '자본총계': 'total_equity'
}
start_year = 2015
current_year = datetime.now().year


company_name = '삼성전자'

# 기업 코드 조회
def get_corp_code(company_name):
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        import zipfile
        import xml.etree.ElementTree as ET
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(response.content)) as zf:
            xml_data = zf.read(zf.namelist()[0])
            root = ET.fromstring(xml_data)
            for corp in root.iter("list"):
                name = corp.find("corp_name").text
                if name == company_name:
                    return corp.find("corp_code").text
    return None


# 데이터 호출
def fetch_financial_data(company_name):
    
    corp_code = get_corp_code(company_name)
    if not corp_code:
        print(f"'{company_name}'의 고유코드를 찾을 수 없습니다.")
        return pd.DataFrame()
    
    all_rows = []
    for year in range(start_year, current_year + 1):
        for quarter_name, reprt_code in reprt_codes.items():
            print(f"{company_name} | {year}년 {quarter_name} 데이터 요청 중...")
            url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
            params = {
                'crtfc_key': api_key,
                'corp_code': corp_code,
                'bsns_year': year,
                'reprt_code': reprt_code,
                'fs_div': fs_div
            }
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == '000':
                    df = pd.DataFrame(data['list'])
                    
                    # 항목 확인용 출력코드
                    #print(f"{year} {quarter_name} 계정명 목록:", df['account_nm'].unique())
                    
                    df = df[df['account_nm'].isin(account_map.keys())]
                    
                    # 단위가 커서 10000으로 나눔
                    df['thstrm_amount'] = pd.to_numeric(df['thstrm_amount'], errors='coerce') / 10000

                    df = df[['account_nm', 'thstrm_amount']]
                    df['account_nm'] = df['account_nm'].map(account_map)
                    df = df.groupby('account_nm', as_index=False).first()
                    df = df.set_index('account_nm').T
                    df['corp_name'] = company_name
                    df['period'] = f"{year}{quarter_name}"
                    all_rows.append(df)
                else:
                    print(f"실패: {data['message']}")
            else:
                print(f"HTTP 오류: {response.status_code}")
    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()

# DB 연결
def DBconnect():
    global cur, conn
    try:
        conn = psycopg2.connect(host='localhost', user='postgres', password='0000', dbname='financial_data')
        cur = conn.cursor()
        print("Database Connect Success")

        # 기본 키 설정
        try:
            cur.execute("ALTER TABLE public.financial_data DROP CONSTRAINT IF EXISTS financial_data_pkey;")
            cur.execute("""
                ALTER TABLE public.financial_data
                ADD CONSTRAINT financial_data_pkey PRIMARY KEY (corp_name, period);
            """)
            conn.commit()
            print("기본 키 설정 완료: (corp_name, period)")
        except Exception as e:
            print(f"기본 키 설정 중 오류: {str(e)}")
            conn.rollback()

        return cur, conn
    except Exception as err:
        print(str(err))
        return None, None

# DB 연결 해제
def DBdisconnect():
    try:
        cur.close()
        conn.close()
        print("DB Connect Close")
    except:
        print("Error: Database Not Connected.")

# 데이터 삽입
def insert_financial_data(df):
    try:
        cur, conn = DBconnect()
        if cur is None or conn is None:
            raise Exception("DB 연결 실패")

        for index, row in df.iterrows():
            insert_query = """
            INSERT INTO public.financial_data (
                corp_name, period, gross_profit, operating_income,
                total_assets, total_liabilities, total_equity
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (corp_name, period) DO NOTHING;
            """
            cur.execute(insert_query, (
                row.get('corp_name'),
                row.get('period'),
                row.get('gross_profit'),
                row.get('operating_income'),
                row.get('total_assets'),
                row.get('total_liabilities'),
                row.get('total_equity')
            ))

        conn.commit()
        print(f"{len(df)}건의 데이터를 삽입했습니다.")

    except Exception as err:
        print("데이터 삽입 중 오류:", str(err))
        conn.rollback()

    finally:
        DBdisconnect()

# 실행
if __name__ == '__main__':
    df = fetch_financial_data(company_name)
    if not df.empty:
        print("데이터를 성공적으로 불러왔습니다.")
        print("\n불러온 데이터\n", df)
        insert_financial_data(df)
    else:
        print("재무제표 데이터를 불러오지 못했습니다.")