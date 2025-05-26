from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import openai
import os

class ActionStockQnA(Action):
    def __init__(self):
        try:
            print("ChatGPT API 연결 시작...")
            # OpenAI API 키 설정
            openai.api_key = os.getenv("OPENAI_API_KEY")
            print("ChatGPT API 연결 성공")
        except Exception as e:
            print(f"ChatGPT API 연결 실패: {str(e)}")
            print("상세 에러 정보:", e.__class__.__name__)

    def name(self) -> Text:
        return "action_stock_qna"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get('text')

        try:
            # ChatGPT API 호출
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "너는 한국어로 친절한 주식 전문가 챗봇이야."},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            answer = response.choices[0].message.content
            print("✅ 생성된 응답:", answer)

            dispatcher.utter_message(text=answer)

            return [
                SlotSet("chatgpt_available", True),
                SlotSet("last_response", answer)
            ]

        except Exception as e:
            print(f"❌ 응답 생성 실패: {str(e)}")
            print("상세 에러 정보:", e.__class__.__name__)
            dispatcher.utter_message(text="죄송합니다. 답변을 생성하는 데 문제가 발생했습니다.")
            return [SlotSet("chatgpt_available", False)]