import React, { useState, useEffect, useRef } from 'react';

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { text: input, sender: 'user' };
    setMessages(prev => [...prev, userMessage]);
    setInput('');

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: input })
      });

      const data = await response.json();
      const botMessage = {
        text: data.answer,
        sender: 'bot'
      };

      // Разделяем ответ на абзацы, если в нем есть символы новой строки
      const formattedMessage = botMessage.text.split('\n').map((line, index) => (
        <p key={index}>{line}</p>
      ));

      setMessages(prev => [
        ...prev,
        { ...botMessage, text: formattedMessage }
      ]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        { text: 'Ошибка соединения с сервером', sender: 'bot', error: true }
      ]);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.sender}`}>
            {/* Отображаем разделенные абзацы для ответа бота */}
            {Array.isArray(msg.text) ? msg.text : msg.text.split('\n').map((line, index) => (
              <p key={index}>{line}</p>
            ))}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <form onSubmit={handleSubmit} className="input-form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Задайте вопрос о документе..."
        />
        <button type="submit">Отправить</button>
      </form>
    </div>
  );
};

export default Chat;
