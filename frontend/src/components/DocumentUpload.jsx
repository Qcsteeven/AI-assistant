import React from 'react';

const DocumentUpload = ({ onUploadSuccess, onError, setLoading }) => {
  const handleSubmit = async (e) => {
    e.preventDefault();
    const files = e.target.file.files;
    if (!files.length) return;

    setLoading(true);

    try {
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]); // 'files' должен совпадать с параметром в FastAPI
      }

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
      <h2>Загрузите документы</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="file"
          name="file"
          multiple
          accept=".docx,.pdf,.xlsx"
          required
        />
        <button type="submit">Загрузить</button>
      </form>
    </div>
  );
};

export default DocumentUpload;
