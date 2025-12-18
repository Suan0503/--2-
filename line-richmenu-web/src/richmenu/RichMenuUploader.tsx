import React, { useState, useEffect } from 'react';

interface UploadResult {
  success: boolean;
  message?: string;
}

export const RichMenuUploader: React.FC = () => {
  const [richMenuId, setRichMenuId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] || null;
    setFile(selected);
    setMessage(null);
    setError(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    if (selected) {
      const url = URL.createObjectURL(selected);
      setPreviewUrl(url);
    } else {
      setPreviewUrl(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    setError(null);

    if (!richMenuId.trim()) {
      setError('請先輸入 Rich Menu ID');
      return;
    }
    if (!file) {
      setError('請先選擇一張圖片');
      return;
    }

    const formData = new FormData();
    formData.append('richMenuId', richMenuId.trim());
    formData.append('image', file);

    setLoading(true);
    try {
      const res = await fetch('/api/richmenu/upload-image', {
        method: 'POST',
        body: formData
      });

      const data: UploadResult = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.message || '上傳失敗，請稍後再試');
      }

      setMessage('Rich Menu 圖片更新成功');
    } catch (err: any) {
      setError(err.message || '上傳發生錯誤');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rm-container">
      <header className="rm-header">
        <h1>LINE Rich Menu 圖片上傳</h1>
        <p>輸入 Rich Menu ID，選擇圖片後即可更新，目前所有操作都只在記憶體中進行，不會寫入伺服器磁碟。</p>
      </header>

      <main className="rm-main">
        <form className="rm-form" onSubmit={handleSubmit}>
          <div className="rm-field">
            <label htmlFor="richMenuId">Rich Menu ID</label>
            <input
              id="richMenuId"
              type="text"
              value={richMenuId}
              onChange={(e) => setRichMenuId(e.target.value)}
              placeholder="請貼上從 LINE 後台取得的 Rich Menu ID"
            />
          </div>

          <div className="rm-field">
            <label htmlFor="image">選擇圖片</label>
            <input
              id="image"
              type="file"
              accept="image/*"
              onChange={handleFileChange}
            />
            <p className="rm-hint">建議使用官方建議尺寸的 PNG 或 JPEG 圖片。</p>
          </div>

          {previewUrl && (
            <div className="rm-preview">
              <div className="rm-preview-label">預覽</div>
              <img src={previewUrl} alt="Rich Menu 預覽" />
            </div>
          )}

          <button type="submit" disabled={loading} className="rm-submit">
            {loading ? '上傳中...' : '上傳並更新 Rich Menu 圖片'}
          </button>

          {message && <div className="rm-message success">{message}</div>}
          {error && <div className="rm-message error">{error}</div>}
        </form>
      </main>
    </div>
  );
};
