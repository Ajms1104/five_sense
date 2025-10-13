"""
LSTM 예측 결과 CSV 파일을 PostgreSQL 데이터베이스에 저장하는 스크립트
"""
import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from tqdm import tqdm

# 환경 변수 로드
load_dotenv()

# 데이터베이스 연결 정보
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "fivesense")

# CSV 파일이 저장된 폴더
PRED_SAVE_FOLDER = "lstm_predictions"

def get_db_engine():
    """PostgreSQL 데이터베이스 엔진 생성"""
    connection_string = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(connection_string)

def import_csv_to_db(engine, csv_file_path):
    """
    CSV 파일을 읽어서 데이터베이스에 저장
    
    Args:
        engine: SQLAlchemy 엔진
        csv_file_path: CSV 파일 경로
    """
    try:
        # CSV 파일 읽기
        df = pd.read_csv(csv_file_path)
        
        # 날짜 컬럼을 datetime으로 변환
        df['date'] = pd.to_datetime(df['date'])
        
        # 컬럼명 확인 (CSV의 컬럼명이 stk_cd, lstm_pred_log, true_target_log_return인지 확인)
        expected_columns = ['date', 'stk_cd', 'lstm_pred_log', 'true_target_log_return']
        if not all(col in df.columns for col in expected_columns):
            print(f"경고: {csv_file_path}의 컬럼명이 예상과 다릅니다.")
            print(f"기대하는 컬럼: {expected_columns}")
            print(f"실제 컬럼: {list(df.columns)}")
            return False
        
        # 데이터베이스에 저장 (중복 시 무시)
        # if_exists='append': 기존 데이터에 추가
        # method='multi': 한 번에 여러 행 삽입 (성능 향상)
        df.to_sql(
            name='lstm_predictions',
            con=engine,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=1000
        )
        
        return True
        
    except Exception as e:
        print(f"오류 발생 - {csv_file_path}: {str(e)}")
        return False

def main():
    """메인 함수"""
    print("LSTM 예측 결과를 데이터베이스에 저장합니다...")
    print(f"데이터베이스: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"CSV 폴더: {PRED_SAVE_FOLDER}")
    print()
    
    # 데이터베이스 엔진 생성
    try:
        engine = get_db_engine()
        print("✓ 데이터베이스 연결 성공")
    except Exception as e:
        print(f"✗ 데이터베이스 연결 실패: {str(e)}")
        return
    
    # CSV 파일 목록 가져오기
    if not os.path.exists(PRED_SAVE_FOLDER):
        print(f"✗ 폴더가 존재하지 않습니다: {PRED_SAVE_FOLDER}")
        return
    
    csv_files = [f for f in os.listdir(PRED_SAVE_FOLDER) if f.endswith('.csv')]
    
    if not csv_files:
        print(f"✗ CSV 파일이 없습니다: {PRED_SAVE_FOLDER}")
        return
    
    print(f"찾은 CSV 파일 개수: {len(csv_files)}")
    print()
    
    # 각 CSV 파일을 데이터베이스에 저장
    success_count = 0
    fail_count = 0
    
    for csv_file in tqdm(csv_files, desc="파일 처리 중"):
        csv_path = os.path.join(PRED_SAVE_FOLDER, csv_file)
        
        if import_csv_to_db(engine, csv_path):
            success_count += 1
        else:
            fail_count += 1
    
    print()
    print("=" * 50)
    print(f"완료! 성공: {success_count}개, 실패: {fail_count}개")
    print("=" * 50)
    
    # 데이터베이스에 저장된 레코드 수 확인
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT COUNT(*) FROM lstm_predictions")
            count = result.scalar()
            print(f"데이터베이스에 저장된 총 레코드 수: {count:,}개")
            
            result = conn.execute("SELECT COUNT(DISTINCT stk_cd) FROM lstm_predictions")
            stock_count = result.scalar()
            print(f"저장된 종목 수: {stock_count}개")
            
            result = conn.execute("SELECT MIN(date), MAX(date) FROM lstm_predictions")
            date_range = result.fetchone()
            print(f"날짜 범위: {date_range[0]} ~ {date_range[1]}")
    except Exception as e:
        print(f"통계 조회 실패: {str(e)}")

if __name__ == "__main__":
    main()


