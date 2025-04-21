from datasets import load_dataset
from googletrans import Translator
from transformers import AutoTokenizer, AutoModel
import torch
import psycopg2
import numpy as np
import logging
import json

class StockOptionsDataProcessor:
    def __init__(self):
        self.dataset_name = "smoh/stock_options_trading"
        self.tokenizer = AutoTokenizer.from_pretrained("skt/kobert-base-v1")
        self.model = AutoModel.from_pretrained("skt/kobert-base-v1")
        self.translator = Translator()
        
        # 데이터베이스 연결 설정
        self.db_params = {
            'dbname': 'fivesense',
            'user': 'postgres',
            'password': '1234',
            'host': '192.168.56.1',
            'port': '5432'
        }
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def load_dataset(self):
        """Hugging Face에서 데이터셋 로드"""
        try:
            self.dataset = load_dataset(self.dataset_name)
            self.logger.info("데이터셋 로드 완료")
            return True
        except Exception as e:
            self.logger.error(f"데이터셋 로드 실패: {e}")
            return False

    def translate_to_korean(self, text):
        """영어 텍스트를 한국어로 번역"""
        try:
            translated = self.translator.translate(text, dest='ko').text
            return translated
        except Exception as e:
            self.logger.error(f"번역 실패: {e}")
            return text

    def generate_embedding(self, text):
        """텍스트에 대한 임베딩 생성"""
        try:
            inputs = self.tokenizer(text, return_tensors='pt', truncation=True, max_length=512)
            with torch.no_grad():
                outputs = self.model(**inputs)
            embedding = outputs.last_hidden_state.mean(dim=1)
            return embedding.detach().numpy()
        except Exception as e:
            self.logger.error(f"임베딩 생성 실패: {e}")
            return None

    def setup_database(self):
        """PostgreSQL 데이터베이스 설정"""
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            
            # pgvector 확장 활성화
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # 테이블 생성
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stock_qa (
                    id SERIAL PRIMARY KEY,
                    question TEXT,
                    answer TEXT,
                    embedding vector(768)
                )
            """)
            
            conn.commit()
            self.logger.info("데이터베이스 설정 완료")
            return True
        except Exception as e:
            self.logger.error(f"데이터베이스 설정 실패: {e}")
            return False
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()

    def process_and_store_data(self):
        """데이터 처리 및 저장"""
        if not self.load_dataset():
            return False
            
        if not self.setup_database():
            return False
            
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            for record in self.dataset['train']:
                conversations=json.loads(record['conversation'])
                question=""
                answer=""
                for item in conversations:
                    # 질문과 답변 번역
                    if item['from'] == 'human':
                        translated_question = self.translate_to_korean(item['value'])
                    elif item['from'] == 'gpt':
                        translated_answer=self.translate_tokorean(item['value'])
                    
                if question == "" or answer =="":
                    continue
                    # 임베딩 생성
                    
                embedding = self.generate_embedding(translated_question)
                if embedding is None:
                    continue
                    
                    # 데이터베이스에 저장
                cur.execute(
                        "INSERT INTO stock_qa (question, answer, embedding) VALUES (%s, %s, %s)",
                        (translated_question, translated_answer, embedding.tolist())
                    )
            
            conn.commit()
            self.logger.info("데이터 처리 및 저장 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"데이터 처리 실패: {e}")
            return False
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()

if __name__ == "__main__":
    processor = StockOptionsDataProcessor()
    processor.process_and_store_data() 