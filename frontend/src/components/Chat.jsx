import React, { useState, useEffect, useRef } from 'react';

const Chat = ({ chatId }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isDeepThink, setIsDeepThink] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = { text: input, sender: 'user' };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: chatId,
          question: input,
          deep_think: isDeepThink
        })
      });

      const data = await response.json();

      let botMessages = [];
      if (isDeepThink && data.initial_answer) {
        botMessages.push(
          {
            text: `[Первоначальный ответ]:\n${data.initial_answer}`,
            sender: 'bot',
            type: 'initial'
          },
          {
            text: `[Анализ и улучшение]:\n${data.critique}`,
            sender: 'bot',
            type: 'critique'
          },
          {
            text: `[Итоговый ответ]:\n${data.answer}`,
            sender: 'bot',
            type: 'final'
          }
        );
      } else {
        botMessages.push({
          text: data.answer,
          sender: 'bot'
        });
      }

      const formattedMessages = botMessages.map(msg => ({
        ...msg,
        text: msg.text.split('\n').map((line, index) => (
          <p key={index}>{line}</p>
        ))
      }));

      setMessages(prev => [...prev, ...formattedMessages]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        { text: 'Ошибка соединения с сервером', sender: 'bot', error: true }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div className="chat-title">Чат с документом</div>
        <div className="deepthink-toggle">
          <span className="deepthink-label">DeepThink</span>
          <label className="deepthink-switch">
            <input
              type="checkbox"
              checked={isDeepThink}
              onChange={() => setIsDeepThink(!isDeepThink)}
            />
            <span className="deepthink-slider"></span>
          </label>
        </div>
      </div>

      <div className="messages">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`message ${msg.sender} ${msg.type || ''}`}
          >
            {Array.isArray(msg.text) ? msg.text : msg.text.split('\n').map((line, index) => (
              <p key={index}>{line}</p>
            ))}
          </div>
        ))}
        {isLoading && (
          <div className="message bot loading">
            <p>Думаю...</p>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="input-form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Задайте вопрос о документе..."
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Отправка...' : 'Отправить'}
        </button>
      </form>
    </div>
  );
};

export default Chat;