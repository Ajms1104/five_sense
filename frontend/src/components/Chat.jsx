import React, { useEffect, useRef, useState } from 'react';

const Chat = () => {
  const chatContainerRef = useRef(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');

  useEffect(() => {
    if (!chatContainerRef.current) return;

    const handleSendMessage = (e) => {
      e.preventDefault();
      if (!inputMessage.trim()) return;

      const newMessage = {
        text: inputMessage,
        sender: 'user',
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, newMessage]);
      setInputMessage('');

      // 여기에 API 호출 로직 추가
      // fetch('/api/chat', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ message: inputMessage })
      // })
      // .then(response => response.json())
      // .then(data => {
      //   setMessages(prev => [...prev, {
      //     text: data.response,
      //     sender: 'bot',
      //     timestamp: new Date().toISOString()
      //   }]);
      // });
    };

    const form = chatContainerRef.current.querySelector('form');
    if (form) {
      form.addEventListener('submit', handleSendMessage);
    }

    return () => {
      if (form) {
        form.removeEventListener('submit', handleSendMessage);
      }
    };
  }, [inputMessage]);

  return (
    <div ref={chatContainerRef} className="chat-container">
      <div className="chat-messages">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.sender}`}>
            <div className="message-content">{message.text}</div>
            <div className="message-timestamp">
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          </div>
        ))}
      </div>
      <form className="chat-input-form">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          placeholder="메시지를 입력하세요..."
        />
        <button type="submit">전송</button>
      </form>
    </div>
  );
};

export default Chat; 