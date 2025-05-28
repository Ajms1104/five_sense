import React, { useState } from "react";
import '../styles/chat.css';

import input_btn from '../assets/Vector.svg'

const ChatUI = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() === "") return;

    setMessages([...messages, input]);
    setInput("");
  };

  return (
    <section className="chat-container">
      <aside className="message-container">
        <div className="chat-messages" id="chat-messages">
          <p className="sub_title">오늘은 어떤 주식이 궁금하신가요?</p>
          {messages.map((msg, index) => (
            <div key={index} className="chat-message">
              {msg}
            </div>
           ))}
        </div>
      </aside>

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <input
            type="text"
            id="chat-input"
            placeholder="메시지를 입력하세요..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
        />
          <button type="submit">
            <img src={input_btn} className="input_btn"/>
          </button>
      </form>
      <h3 className='danger'> 투자에 대한 모든 결과는 전적으로 개인에게 있으며 손해에 대해 FIVESENSE 에선 책임지지 않습니다</h3>
    </section>
  );
};

export default ChatUI;
