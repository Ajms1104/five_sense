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
            self.logger.warning(f"번역 실패, 원문 사용: {e}")
            return text  # 실패하면 원문 사용

    def generate_embedding(self, text):
        """텍스트에 대한 임베딩 생성"""
        try:
            if not text or len(text.strip()) == 0:
                self.logger.warning("빈 텍스트로 임베딩을 생성할 수 없습니다.")
                return None
                
            # 텍스트가 너무 짧은 경우 처리
            if len(text.strip()) < 3:
                self.logger.warning("텍스트가 너무 짧습니다.")
                return None
                
            # 디버깅을 위한 로그 추가
            self.logger.info(f"처리 중인 텍스트 길이: {len(text)}")
            
            # 토크나이저 설정 변경
            inputs = self.tokenizer(
                text,
                return_tensors='pt',
                truncation=True,
                max_length=128,
                padding='max_length',  # 고정 길이 패딩 사용
                add_special_tokens=True
            )
            
            # 입력 텐서 크기 확인
            self.logger.info(f"입력 텐서 크기: {inputs['input_ids'].size()}")
            
            # attention_mask 생성
            attention_mask = inputs['attention_mask']
            
            with torch.no_grad():
                outputs = self.model(
                    input_ids=inputs['input_ids'],
                    attention_mask=attention_mask
                )
                
            # [CLS] 토큰의 임베딩을 사용
            cls_embedding = outputs.last_hidden_state[:, 0, :]
            
            # 임베딩 크기 확인
            self.logger.info(f"생성된 임베딩 크기: {cls_embedding.size()}")
            
            return cls_embedding.detach().numpy()
            
        except Exception as e:
            self.logger.error(f"임베딩 생성 실패: {e}, 텍스트: {text[:50]}...")
            return None

    def setup_database(self):
        """PostgreSQL 데이터베이스 설정"""
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            
            # pgvector 확장 활성화
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # 기존 테이블이 있다면 삭제
            cur.execute("DROP TABLE IF EXISTS stock_qa")
            
            # 테이블 생성
            cur.execute("""
                CREATE TABLE stock_qa (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    embedding vector(768) NOT NULL
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
            
            # 첫 번째 레코드 확인
            if len(self.dataset['train']) > 0:
                self.logger.info(f"첫 번째 레코드: {self.dataset['train'][0]}")
            
            for record in self.dataset['train']:
                try:
                    conversations = json.loads(record['conversations'])
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON 파싱 실패: {e}")
                    continue
                    
                question = ""
                answer = ""
                
                for item in conversations:
                    if item['from'] == 'human':
                        question = self.translate_to_korean(item['value'])
                    elif item['from'] == 'gpt':
                        answer = self.translate_to_korean(item['value'])
                
                if not question.strip() or not answer.strip():
                    self.logger.warning("빈 질문/답변이 감지되어 건너뜀")
                    continue
                
                # 임베딩 생성
                embedding = self.generate_embedding(question)
                if embedding is None:
                    continue
                
                # 데이터베이스에 저장
                cur.execute(
                    "INSERT INTO stock_qa (question, answer, embedding) VALUES (%s, %s, %s)",
                    (question, answer, embedding.flatten().tolist())
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