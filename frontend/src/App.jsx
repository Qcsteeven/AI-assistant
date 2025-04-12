import React, { useState } from 'react';
import DocumentUpload from './components/DocumentUpload';
import Chat from './components/Chat';
import './styles.css';

function App() {
  const [documentUploaded, setDocumentUploaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleUploadSuccess = () => {
    setDocumentUploaded(true);
    setError(null);
  };

  const handleUploadError = (err) => {
    setError(err.message);
    setDocumentUploaded(false);
  };

  return (
    <div className="app">
      <header>
        <h1>AI Document Chat</h1>
        {error && <div className="error-message">{error}</div>}
      </header>

      <main>
        {!documentUploaded ? (
          <DocumentUpload 
            onUploadSuccess={handleUploadSuccess}
            onError={handleUploadError}
            setLoading={setLoading}
          />
        ) : (
          <Chat />
        )}
      </main>

      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
        </div>
      )}
    </div>
  );
}

export default App;