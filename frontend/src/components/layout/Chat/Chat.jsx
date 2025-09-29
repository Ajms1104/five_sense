//AI와 채팅

import React, { useState, useEffect, useRef } from "react";
import style from './chat.module.css';

const ChatUI = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentRoomId, setCurrentRoomId] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    // 채팅 기록 불러오기
    fetchChatHistory();
  }, []);

  useEffect(() => {
    // 메시지가 추가될 때마다 스크롤
    scrollToBottom();
  }, [messages]);

  const fetchChatHistory = async () => {
    try {
      console.log("채팅 기록 조회 중...");
      const response = await fetch('/api/chat/history');
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '채팅 기록을 불러오는데 실패했습니다.');
      }
      const data = await response.json();
      console.log("조회된 채팅 기록:", data);
      
      // 메시지를 시간순으로 정렬하고 UI에 맞게 변환
      const sortedMessages = data
        .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
        .map(msg => ({
          type: msg.type.toLowerCase(),
          content: msg.content,
          timestamp: msg.timestamp
        }));
      
      setMessages(sortedMessages);
      setError(null);
    } catch (error) {
      console.error('채팅 기록 로딩 오류:', error);
      setError(error.message);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (input.trim() === "") return;

    const userMessage = input.trim();
    setIsLoading(true);
    setError(null);
    
    // 사용자 메시지를 즉시 UI에 추가
    const userMsg = {
      type: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMsg]);
    setInput("");

    try {
      console.log("ChatGPT API 호출 중...");
      const url = currentRoomId 
        ? `/api/chat/${currentRoomId}`
        : '/api/chat';
        
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: userMessage }),
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || '메시지 전송 실패');
      }
      
      console.log("ChatGPT 응답:", data);
      
      // AI 응답을 UI에 추가
      const aiMsg = {
        type: 'ai',
        content: data.aiResponse,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, aiMsg]);
      
      // 새로운 채팅방인 경우 roomId 설정
      if (data.roomId && !currentRoomId) {
        setCurrentRoomId(data.roomId);
      }
      
      // 입력 필드에 다시 포커스
      inputRef.current?.focus();
      
    } catch (error) {
      console.error('메시지 전송 오류:', error);
      setError(error.message);
      
      // 오류 발생 시 사용자 메시지 제거
      setMessages(prev => prev.filter(msg => msg !== userMsg));
    } finally {
      setIsLoading(false);
      // 오류가 없어도 입력 필드에 포커스
      inputRef.current?.focus();
    }
  };

  return (
    <section className={style['chat-container']}>
      <aside className={style['message-container']}>
        <div className={style['chat-messages']} id="chat-messages">
          <p className={style.sub_title}>오늘은 어떤 주식이 궁금하신가요?</p>
          {messages.length === 0 && (
            <div className={style['welcome-message']}>
              안녕하세요! 주식 투자에 대해 궁금한 점이 있으시면 언제든 물어보세요. 
              주식 분석, 투자 전략, 시장 동향 등에 대해 전문적인 답변을 드리겠습니다.
            </div>
          )}
          {messages.map((msg, index) => (
            <div key={index} className={`${style['chat-message']} ${style[msg.type]}`}>
              <div className={style['message-content']}>
                {msg.content}
              </div>
              <div className={style['message-timestamp']}>
                {new Date(msg.timestamp).toLocaleTimeString('ko-KR', {
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className={style['chat-message-ai-loading']}> 
              <div className={style['loading-dots']}>
                <span></span>
                <span></span>
                <span></span>
              </div>
              AI가 응답을 생성하고 있습니다...
            </div>
          )}
          {error && (
            <div className={style['chat-message-error']}>
              <span className={style['error-icon']}>⚠️</span>
              {error}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </aside>

      <form className={style['chat-input-form']} onSubmit={handleSubmit}>
        <input
            ref={inputRef}
            type="text"
            id="chat-input"
            placeholder="메시지를 입력하세요... (Enter 키로 전송)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            disabled={isLoading}
            autoFocus
        />
        <button 
          type="submit" 
          className={style['send-button']}
          disabled={isLoading || input.trim() === ""}
        >
          {isLoading ? '전송 중...' : '전송'}
        </button>
      </form>
      <h3 className={style.danger}> 투자에 대한 모든 결과는 전적으로 개인에게 있으며 손해에 대해 FIVESENSE 에선 책임지지 않습니다</h3>
    </section>
  );
};

export default ChatUI;
