from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

class ActionStockQnA(Action):
    def __init__(self):
        try:
            print("BitNet 모델 로딩 시작...")
            model_id = "microsoft/bitnet-b1.58-2B-4T"
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"사용 가능한 디바이스: {device}")

            # 토크나이저와 모델 로드
            print("토크나이저 로드 중...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                use_fast=True,  # 빠른 토크나이저 사용
                padding_side="left"  # 패딩 위치 설정
            )
            
            # 패딩 토큰 설정
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            print("모델 로드 중...")
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.bfloat16,
                device_map="auto",
                low_cpu_mem_usage=True,  # CPU 메모리 사용량 최적화
                use_cache=True  # KV 캐시 사용
            )
            
            # 모델의 패딩 토큰 ID 설정
            self.model.config.pad_token_id = self.tokenizer.pad_token_id
            
            # 모델을 평가 모드로 설정
            self.model.eval()
            
            # JIT 컴파일 활성화
            if hasattr(torch, 'compile'):
                self.model = torch.compile(self.model)
            
            print("BitNet 모델 연결 성공")

        except Exception as e:
            print(f"BitNet 모델 연결 실패: {str(e)}")
            print("상세 에러 정보:", e.__class__.__name__)
            self.model = None
            self.tokenizer = None

    def name(self) -> Text:
        return "action_stock_qna"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get('text')

        try:
            if self.model is None or self.tokenizer is None:
                dispatcher.utter_message(text="❌ BitNet 모델이 연결되지 않았습니다.")
                return [SlotSet("bitnet_available", False)]

            # 채팅 메시지 구성
            messages = [
                {"role": "system", "content": "너는 한국어로 친절한 주식 전문가 챗봇이야."},
                {"role": "user", "content": user_message}
            ]
            
            # 채팅 템플릿 적용
            prompt = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            
            # 입력 토큰화
            chat_input = self.tokenizer(
                prompt, 
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512  # 최대 길이 제한
            ).to(self.model.device)
            
            print("⏳ BitNet 응답 생성 중...")
            
            # torch.no_grad() 컨텍스트 사용
            with torch.no_grad():
                # 응답 생성
                chat_outputs = self.model.generate(
                    **chat_input,
                    max_new_tokens=50,  # 토큰 수 감소
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,  # top-p 샘플링 추가
                    num_beams=1,  # 빔 서치 비활성화
                    pad_token_id=self.tokenizer.pad_token_id
                )
            
            # 응답 디코딩 (새로 생성된 부분만)
            answer = self.tokenizer.decode(
                chat_outputs[0][chat_input['input_ids'].shape[-1]:],
                skip_special_tokens=True
            )
            
            print("✅ 생성된 응답:", answer)

            dispatcher.utter_message(text=answer)

            return [
                SlotSet("bitnet_available", True),
                SlotSet("last_response", answer)
            ]

        except Exception as e:
            print(f"❌ 응답 생성 실패: {str(e)}")
            print("상세 에러 정보:", e.__class__.__name__)
            dispatcher.utter_message(text="죄송합니다. 답변을 생성하는 데 문제가 발생했습니다.")
            return [SlotSet("bitnet_available", False)]