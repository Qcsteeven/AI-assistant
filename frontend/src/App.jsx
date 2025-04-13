import React, { useState, useEffect } from 'react';
import DocumentUpload from './components/DocumentUpload';
import Chat from './components/Chat';
import './styles.css';

function App() {
  const [chatId, setChatId] = useState(null);
  const [documentUploaded, setDocumentUploaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [chats, setChats] = useState([]);

  const createNewChat = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/chat/new', {
        method: 'POST',
      });
      const data = await response.json();
      const newChat = {
        id: data.chat_id,
        name: `Чат ${chats.length + 1}`,
        createdAt: new Date().toLocaleString()
      };

      setChats([...chats, newChat]);
      setChatId(data.chat_id);
      setDocumentUploaded(false);
      setError(null);
    } catch (err) {
      setError("Не удалось создать новый чат");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    createNewChat();
  }, []);

  const handleUploadSuccess = () => {
    setDocumentUploaded(true);
    setError(null);
  };

  const handleUploadError = (err) => {
    setError(err.message);
    setDocumentUploaded(false);
  };

  const switchChat = (chat) => {
    setChatId(chat.id);
    setDocumentUploaded(true);
  };

  return (
    <div className="app">
      {/* Шапка */}
      <header className="header">
        <button onClick={createNewChat} className="new-chat-btn">
          + Новый чат
        </button>
        <h1 className="header-title">AI Document Chat</h1>
        <div style={{ width: '100px' }}></div> {/* Для выравнивания */}
      </header>

      {/* Боковая панель */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h3 className="sidebar-title">Мои чаты</h3>
        </div>
        <ul className="chat-list">
          {chats.map(chat => (
            <li
              key={chat.id}
              className={`chat-item ${chat.id === chatId ? 'active' : ''}`}
              onClick={() => switchChat(chat)}
            >
              <div className="chat-name">{chat.name}</div>
              <div className="chat-date">{chat.createdAt}</div>
            </li>
          ))}
        </ul>
      </div>

      {/* Основное содержимое */}
      <main className="main-content">
        {error && <div className="error-message">{error}</div>}

        {!chatId ? (
          <p>Создание сессии...</p>
        ) : !documentUploaded ? (
          <DocumentUpload
            chatId={chatId}
            onUploadSuccess={handleUploadSuccess}
            onError={handleUploadError}
            setLoading={setLoading}
          />
        ) : (
          <Chat chatId={chatId} />
        )}
      </main>
    </div>
  );
}

export default App;