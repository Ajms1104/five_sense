//AI와 채팅

import React, { useState, useEffect } from "react";
import style from './chat.module.css';

import input_btn from '../../../assets/Vector.svg';

const ChatUI = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // 채팅 기록 불러오기
    fetchChatHistory();
  }, []);

  const fetchChatHistory = async () => {
    try {
      const response = await fetch('http://localhost:8080/api/chat/history');
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '채팅 기록을 불러오는데 실패했습니다.');
      }
      const data = await response.json();
      setMessages(data.map(msg => ({
        type: msg.type.toLowerCase(),
        content: msg.content
      })));
      setError(null);
    } catch (error) {
      console.error('채팅 기록 로딩 오류:', error);
      setError(error.message);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (input.trim() === "") return;

    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8080/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: input }),
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || '메시지 전송 실패');
      }
      
      // 새로운 채팅 기록 불러오기
      await fetchChatHistory();
      setInput("");
    } catch (error) {
      console.error('메시지 전송 오류:', error);
      setError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className={style['chat-container']}>
      <aside className={style['message-container']}>
        <div className={style['chat-messages']} id="chat-messages">
          <p className={style.sub_title}>오늘은 어떤 주식이 궁금하신가요?</p>
          {messages.map((msg, index) => (
            <div key={index} className={`${style['chat-message']} ${style[msg.type]}`}>
              {msg.content}
            </div>
          ))}
          {isLoading && (
            <div className={style['chat-message-ai-loading']}> 
              응답을 생성하고 있습니다...
            </div>
          )}
          {error && (
            <div className={style['chat-message-error']}>
              {error}
            </div>
          )}
        </div>
      </aside>

      <form className={style['chat-input-form']} onSubmit={handleSubmit}>
        <input
            type="text"
            id="chat-input"
            placeholder="메시지를 입력하세요..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isLoading}
        />
          <button type="submit" disabled={isLoading}>
            <img src={input_btn} className={style.input_btn}/>
          </button>
      </form>
      <h3 className={style.danger}> 투자에 대한 모든 결과는 전적으로 개인에게 있으며 손해에 대해 FIVESENSE 에선 책임지지 않습니다</h3>
    </section>
  );
};

export default ChatUI;
