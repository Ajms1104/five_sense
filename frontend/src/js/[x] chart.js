import { useState } from 'react';

const useChat = () => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim()) return;

    const newMessage = {
      text: inputMessage,
      sender: 'user',
      timestamp: new Date().toISOString()
    };

    setMessages((prev) => [...prev, newMessage]);
    setInputMessage('');

    // API 호출 예시
    // try {
    //   const response = await fetch('/api/chat', {
    //     method: 'POST',
    //     headers: { 'Content-Type': 'application/json' },
    //     body: JSON.stringify({ message: inputMessage })
    //   });
    //   const data = await response.json();
    //   setMessages((prev) => [
    //     ...prev,
    //     {
    //       text: data.response,
    //       sender: 'bot',
    //       timestamp: new Date().toISOString()
    //     }
    //   ]);
    // } catch (error) {
    //   console.error('Error sending message:', error);
    // }

  };

  return {
    messages,
    inputMessage,
    setInputMessage,
    handleSendMessage
  };
};

export default useChat;
