import React from 'react';

const DocumentUpload = ({ onUploadSuccess, onError, setLoading }) => {
  const handleSubmit = async (e) => {
    e.preventDefault();
    const file = e.target.file.files[0];
    if (!file) return;

    setLoading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      onUploadSuccess();
    } catch (err) {
      onError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="upload-container">
      <h2>Загрузите документ</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="file"
          name="file"
          accept=".docx"
          required
        />
        <button type="submit">Загрузить</button>
      </form>
    </div>
  );
};

export default DocumentUpload;