# actions.py
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import psycopg2
import numpy as np
from transformers import BertTokenizer, BertModel
import torch

class ActionStockQnA(Action):
    def __init__(self):
        # 데이터베이스 연결 설정
        self.db_params = {
            'dbname': 'fivesense',
            'user': 'postgres',
            'password': '1234',
            'host': '192.168.56.1',
            'port': '5432'
        }
        
        # KoBERT 모델 및 토크나이저 초기화
        self.tokenizer = BertTokenizer.from_pretrained("skt/kobert-base-v1")
        self.model = BertModel.from_pretrained("skt/kobert-base-v1")

    def name(self) -> Text:
        return "action_stock_qna"

    def generate_embedding(self, text: Text) -> np.ndarray:
        """텍스트에 대한 임베딩 생성"""
        inputs = self.tokenizer(text, return_tensors='pt', truncation=True, max_length=512)
        with torch.no_grad():
            outputs = self.model(**inputs)
        embedding = outputs.last_hidden_state.mean(dim=1)
        return embedding.detach().numpy()

    def find_similar_questions(self, query_embedding: np.ndarray, limit: int = 5) -> List[Dict]:
        """유사한 질문 찾기"""
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            
            # 벡터 유사도 검색
            cur.execute("""
                SELECT question, answer, 
                       embedding <=> %s as distance
                FROM stock_qa
                ORDER BY distance
                LIMIT %s
            """, (query_embedding.tolist(), limit))
            
            results = []
            for row in cur.fetchall():
                results.append({
                    'question': row[0],
                    'answer': row[1],
                    'distance': float(row[2])
                })
            
            return results
            
        except Exception as e:
            print(f"데이터베이스 검색 중 오류 발생: {e}")
            return []
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # 사용자 메시지 가져오기
        user_message = tracker.latest_message.get('text')
        
        # 사용자 메시지에 대한 임베딩 생성
        query_embedding = self.generate_embedding(user_message)
        
        # 유사한 질문 찾기
        similar_questions = self.find_similar_questions(query_embedding)
        
        if similar_questions:
            # 가장 유사한 질문의 답변 반환
            best_match = similar_questions[0]
            dispatcher.utter_message(text=best_match['answer'])
        else:
            dispatcher.utter_message(text="죄송합니다. 해당 질문에 대한 답변을 찾을 수 없습니다.")
        
        return []
