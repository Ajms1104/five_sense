import requests
import json
import pandas as pd
import psycopg2
import main
import time
from requests.exceptions import RequestException

# 1. 데이터베이스 연결 함수
def DBconnect():
    """
    PostgreSQL 데이터베이스에 연결하고 커서와 연결 객체를 반환합니다.
    infolist_data 테이블이 없으면 새로 생성하며, 모든 컬럼을 TEXT로 설정합니다.
    code를 기본 키로 설정하여 중복 데이터를 방지합니다.
    """
    global cur, conn
    try:
        conn = psycopg2.connect(
            host='localhost',
            user='postgres',
            password='1234',
            dbname='kiwoom_data'
        )
        cur = conn.cursor()
        print("데이터베이스 연결 성공")

        # 테이블 존재 여부 확인
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'infolist_data'
            );
        """)
        table_exists = cur.fetchone()[0]

        if not table_exists:
            # 테이블이 없으면 새로 생성
            create_table_query = """
            CREATE TABLE public.infolist_data (
                code TEXT PRIMARY KEY,
                name TEXT,
                listCount TEXT,
                upSizeName TEXT
            );
            """
            cur.execute(create_table_query)
            conn.commit()
            print("infolist_data 테이블 생성 완료")
        else:
            print("infolist_data 테이블이 이미 존재합니다.")

        return cur, conn
    except Exception as err:
        print(f"데이터베이스 연결 실패: {str(err)}")
        return None, None

# 2. 데이터베이스 연결 해제 함수
def DBdisconnect():
    """
    데이터베이스 연결을 안전하게 종료합니다.
    """
    try:
        conn.close()
        cur.close()
        print("데이터베이스 연결 종료")
    except:
        print("오류: 데이터베이스가 연결되어 있지 않습니다.")

# 3. 단일 API 요청 함수
def fn_ka10099(token, data, cont_yn='N', next_key='', max_retries=3):
    host = 'https://mockapi.kiwoom.com'  # 모의투자
    endpoint = '/api/dostk/stkinfo'
    url = host + endpoint

    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'authorization': f'Bearer {token}',
        'cont-yn': cont_yn,
        'next-key': next_key,
        'api-id': 'ka10099',
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data)
            print('응답 코드:', response.status_code)
            print('헤더:', json.dumps({key: response.headers.get(key) for key in ['next-key', 'cont-yn', 'api-id']}, indent=4, ensure_ascii=False))
            print('바디:', json.dumps(response.json(), indent=4, ensure_ascii=False))

            if response.status_code == 429:
                print(f"429 Too Many Requests 에러 발생. {attempt + 1}/{max_retries} 재시도 중...")
                time.sleep(2 ** attempt)  # 지수 백오프
                continue

            if response.status_code == 200:
                res = response.json().get('list', [])
                if not res:
                    print("응답에 데이터가 없습니다.")
                    return None, None, None
                
                df = pd.DataFrame(res)
                print("원본 데이터프레임:\n", df)

                # 필요한 컬럼만 선택
                required_columns = ['code', 'name', 'listCount', 'upSizeName']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    print(f"누락된 컬럼: {missing_columns}")
                    return None, None, None
                
                df = df[required_columns]
                print("전처리된 데이터프레임:\n", df)

                # 요청 간 딜레이 추가
                time.sleep(1)  # API 호출 제한 방지

                return df, response.headers.get('cont-yn'), response.headers.get('next-key')
            else:
                print(f"API 요청 실패: 상태 코드 {response.status_code}")
                return None, None, None

        except RequestException as e:
            print(f"요청 중 오류 발생: {str(e)}. {attempt + 1}/{max_retries} 재시도 중...")
            time.sleep(2 ** attempt)
            continue

    print("최대 재시도 횟수 초과. API 요청 실패")
    return None, None, None

# 4. 모든 데이터 가져오기 (연속 조회 포함)
def fetch_all_data(token, data, max_iterations=10, max_rows=10000):
    all_data = []
    cont_yn = 'N'
    next_key = ''
    iteration = 0
    total_rows = 0

    while True:
        if iteration >= max_iterations:
            print(f"최대 반복 횟수({max_iterations}) 도달. 연속 조회 중단.")
            break

        df, cont_yn, next_key = fn_ka10099(token, data, cont_yn, next_key)
        if df is None:
            print("데이터를 가져오지 못했습니다. 조회 중단.")
            break

        if not df.empty:
            # 최대 행 제한 적용
            rows_to_add = min(len(df), max_rows - total_rows)
            if rows_to_add > 0:
                df = df.iloc[:rows_to_add]
                all_data.append(df)
                total_rows += len(df)
                print(f"가져온 데이터: {len(df)} rows (총 {total_rows} rows)")

        if total_rows >= max_rows:
            print(f"최대 행 수({max_rows}) 도달. 연속 조회 중단.")
            break

        if cont_yn != 'Y':
            print("더 이상 가져올 데이터가 없습니다. 연속 조회 중단.")
            break

        cont_yn = 'Y'
        next_key = next_key or ''
        iteration += 1
        print(f"연속 조회 {iteration}회 완료. 다음 조회를 진행합니다...")

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None

# 5. 데이터베이스에 데이터 삽입
def insert_to_db(df, batch_size=100):
    """
    DataFrame의 데이터를 infolist_data 테이블에 배치 단위로 삽입합니다.
    - 중복 데이터는 삽입되지 않도록 ON CONFLICT DO NOTHING 사용.
    - 배치 처리를 통해 성능 최적화 (배치 크기 100으로 설정).
    """
    try:
        # DB 연결
        cur, conn = DBconnect()
        if cur is None or conn is None:
            raise Exception("DB 연결 실패")

        # 데이터프레임의 각 행을 테이블에 삽입 (배치 처리)
        for start in range(0, len(df), batch_size):
            batch = df[start:start + batch_size]
            print(f"배치 삽입 시작: {start} ~ {start + len(batch) - 1} 행")

            for index, row in batch.iterrows():
                insert_query = """
                INSERT INTO public.infolist_data (code, name, listCount, upSizeName)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (code) DO NOTHING;
                """
                cur.execute(insert_query, (
                    row['code'],
                    row['name'],
                    row['listCount'],
                    row['upSizeName']
                ))
            
            # 배치 커밋
            conn.commit()
            print(f"배치 삽입 완료: {len(batch)} rows")

        print("모든 데이터 삽입 완료")

    except Exception as err:
        print("데이터 삽입 중 오류:", str(err))
        if conn is not None:
            conn.rollback()

    finally:
        DBdisconnect()

# 6. 실행 구간
if __name__ == '__main__':
    # 1. 토큰 설정
    MY_ACCESS_TOKEN = main.fn_au10001()  # 접근 토큰

    # 2. 요청 데이터
    params = {
        'mrkt_tp': '0',  # 시장구분: 코스피
    }

    # 3. 모든 데이터 가져오기 (최대 3000개 행)
    df = fetch_all_data(
        token=MY_ACCESS_TOKEN,
        data=params,
        max_iterations=50,  # 충분한 횟수로 설정
        max_rows=3000       # 최대 3000개 행 제한
    )

    # 4. 데이터베이스에 삽입
    if df is not None:
        print(f"총 {len(df)} rows 데이터를 삽입합니다.")
        insert_to_db(df, batch_size=100)
    else:
        print("삽입할 데이터가 없습니다.")
    