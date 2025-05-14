# actions.py
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

class ActionStockRAG(Action):
    def name(self):
        return "action_stock_rag"

    def run(self, dispatcher, tracker, domain):
        user_question = tracker.latest_message.get('text')
        # RAG 시스템에 요청
        answer = search_rag(user_question)  # 너가 만든 RAG 함수 호출
        dispatcher.utter_message(text=answer)
        return []
