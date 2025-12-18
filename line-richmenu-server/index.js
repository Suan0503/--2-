require('dotenv').config();

const express = require('express');
const cors = require('cors');
const multer = require('multer');
const axios = require('axios');

const app = express();
const port = process.env.PORT || 3000;

// CORS: 允許前端（例如 Vite / React dev server）呼叫本 API
app.use(cors());

// 不解析 multipart，由 multer 處理

// multer 設定為純記憶體，不可寫入磁碟
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 10 * 1024 * 1024 // 最多 10MB
  }
});

/**
 * 呼叫 LINE Messaging API 更新 Rich Menu 圖片
 * @param {string} richMenuId
 * @param {Buffer} imageBuffer
 * @param {string} mimeType
 * @returns {Promise<void>}
 */
async function uploadRichMenuImageToLine(richMenuId, imageBuffer, mimeType) {
  const accessToken = process.env.LINE_CHANNEL_ACCESS_TOKEN;
  if (!accessToken) {
    throw new Error('LINE_CHANNEL_ACCESS_TOKEN is not set in environment');
  }

  // 上傳 Rich Menu 圖片需使用 api-data.line.me
  const url = `https://api-data.line.me/v2/bot/richmenu/${encodeURIComponent(richMenuId)}/content`;

  await axios.post(url, imageBuffer, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': mimeType,
      'Content-Length': imageBuffer.length
    },
    // 避免過長等待，給一個合理 timeout
    timeout: 15000
  });
}

// POST /api/richmenu/upload-image
app.post(
  '/api/richmenu/upload-image',
  upload.single('image'),
  async (req, res) => {
    try {
      const richMenuId = (req.body.richMenuId || '').trim();
      const file = req.file;

      if (!richMenuId || !file) {
        return res.status(400).json({
          success: false,
          message: 'richMenuId 與 image 檔案為必填'
        });
      }

      if (!file.mimetype.startsWith('image/')) {
        return res.status(400).json({
          success: false,
          message: '上傳檔案必須為圖片格式'
        });
      }

      await uploadRichMenuImageToLine(richMenuId, file.buffer, file.mimetype);

      return res.json({ success: true });
    } catch (err) {
      console.error('[LINE RichMenu Upload] error:', err.response?.data || err.message || err);

      const status = err.response?.status || 500;
      const messageFromLine = err.response?.data?.message || err.response?.data?.error || err.message || 'LINE API error';

      return res.status(status).json({
        success: false,
        message: messageFromLine
      });
    }
  }
);

// 簡單前端頁面：專門給 Rich Menu 圖片更新使用
app.get('/', (req, res) => {
  res.send(`<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>LINE Rich Menu 圖片更新</title>
    <style>
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        background: #f4f6fb;
        color: #1f2933;
      }
      .wrap {
        max-width: 960px;
        margin: 0 auto;
        padding: 32px 16px 40px;
      }
      .card {
        background: #ffffff;
        border-radius: 16px;
        padding: 24px 20px 28px;
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12);
      }
      h1 {
        margin: 0 0 8px;
        font-size: 22px;
        color: #1c4e80;
      }
      p.desc {
        margin: 0 0 16px;
        font-size: 14px;
        color: #52606d;
      }
      label {
        display: block;
        margin-bottom: 4px;
        font-size: 14px;
        font-weight: 600;
        color: #243b53;
      }
      input[type="text"], input[type="file"] {
        width: 100%;
        font-size: 14px;
      }
      input[type="text"] {
        padding: 9px 11px;
        border-radius: 8px;
        border: 1px solid #cbd2d9;
        margin-bottom: 10px;
      }
      input[type="text"]:focus {
        outline: none;
        border-color: #2680c2;
        box-shadow: 0 0 0 1px rgba(38, 128, 194, 0.4);
      }
      .hint {
        font-size: 12px;
        color: #829ab1;
        margin-top: 4px;
        margin-bottom: 12px;
      }
      .preview {
        margin-top: 10px;
        padding: 10px;
        border-radius: 12px;
        border: 1px dashed #c1c7cd;
        background: #f8fafc;
        display: none;
      }
      .preview img {
        max-width: 100%;
        border-radius: 8px;
        display: block;
      }
      button {
        margin-top: 14px;
        padding: 10px 14px;
        border-radius: 999px;
        border: none;
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: #ffffff;
        font-weight: 600;
        font-size: 14px;
        cursor: pointer;
        box-shadow: 0 8px 18px rgba(37, 99, 235, 0.35);
      }
      button:disabled {
        opacity: 0.6;
        cursor: default;
        box-shadow: none;
      }
      .msg {
        margin-top: 10px;
        padding: 10px 12px;
        border-radius: 8px;
        font-size: 13px;
      }
      .msg.ok {
        background: #e3f9e5;
        color: #1a7f37;
        border: 1px solid #8ee89a;
      }
      .msg.err {
        background: #ffefef;
        color: #b42318;
        border: 1px solid #f5b5b5;
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <h1>LINE Rich Menu 圖片更新</h1>
        <p class="desc">此頁面僅提供 Rich Menu 圖片上傳與預覽功能，所有檔案都只會暫存在記憶體中，不會寫入伺服器磁碟。</p>

        <form id="form">
          <div>
            <label for="richMenuId">Rich Menu ID</label>
            <input id="richMenuId" name="richMenuId" type="text" placeholder="請貼上 Rich Menu ID" required />
          </div>

          <div style="margin-top: 10px;">
            <label for="image">選擇圖片</label>
            <input id="image" name="image" type="file" accept="image/*" required />
            <div class="hint">建議使用 LINE 官方建議尺寸的 PNG 或 JPEG 圖片，檔案大小請控制在 10MB 以內。</div>
          </div>

          <div class="preview" id="previewBox">
            <div style="font-size: 13px; font-weight: 600; color: #52606d; margin-bottom: 6px;">預覽</div>
            <img id="previewImage" src="" alt="Rich Menu 預覽" />
          </div>

          <button type="submit" id="submitBtn">上傳並更新 Rich Menu 圖片</button>

          <div id="msgBox" class="msg" style="display:none;"></div>
        </form>
      </div>
    </div>

    <script>
      (function() {
        const form = document.getElementById('form');
        const richMenuIdInput = document.getElementById('richMenuId');
        const imageInput = document.getElementById('image');
        const previewBox = document.getElementById('previewBox');
        const previewImage = document.getElementById('previewImage');
        const submitBtn = document.getElementById('submitBtn');
        const msgBox = document.getElementById('msgBox');

        let previewUrl = null;

        imageInput.addEventListener('change', function () {
          const file = this.files && this.files[0];
          if (!file) {
            previewBox.style.display = 'none';
            previewImage.src = '';
            if (previewUrl) {
              URL.revokeObjectURL(previewUrl);
              previewUrl = null;
            }
            return;
          }
          if (!file.type || file.type.indexOf('image/') !== 0) {
            alert('請選擇圖片檔案');
            this.value = '';
            previewBox.style.display = 'none';
            previewImage.src = '';
            if (previewUrl) {
              URL.revokeObjectURL(previewUrl);
              previewUrl = null;
            }
            return;
          }
          if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
          }
          previewUrl = URL.createObjectURL(file);
          previewImage.src = previewUrl;
          previewBox.style.display = 'block';
        });

        form.addEventListener('submit', async function (e) {
          e.preventDefault();
          msgBox.style.display = 'none';
          msgBox.className = 'msg';
          msgBox.textContent = '';

          const richMenuId = (richMenuIdInput.value || '').trim();
          const file = imageInput.files && imageInput.files[0];
          if (!richMenuId) {
            msgBox.textContent = '請先輸入 Rich Menu ID';
            msgBox.classList.add('err');
            msgBox.style.display = 'block';
            return;
          }
          if (!file) {
            msgBox.textContent = '請先選擇一張圖片';
            msgBox.classList.add('err');
            msgBox.style.display = 'block';
            return;
          }

          const fd = new FormData();
          fd.append('richMenuId', richMenuId);
          fd.append('image', file);

          submitBtn.disabled = true;
          submitBtn.textContent = '上傳中...';

          try {
            const resp = await fetch('/api/richmenu/upload-image', {
              method: 'POST',
              body: fd
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok || !data.success) {
              throw new Error(data.message || '上傳失敗，請稍後再試');
            }
            msgBox.textContent = 'Rich Menu 圖片更新成功';
            msgBox.classList.add('ok');
            msgBox.style.display = 'block';
          } catch (err) {
            msgBox.textContent = err && err.message ? err.message : '上傳發生錯誤';
            msgBox.classList.add('err');
            msgBox.style.display = 'block';
          } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = '上傳並更新 Rich Menu 圖片';
          }
        });
      })();
    </script>
  </body>
</html>`);
});

app.get('/health', (req, res) => {
  res.json({ ok: true, env: 'line-richmenu-server' });
});

app.listen(port, () => {
  console.log(`LINE RichMenu server listening on port ${port}`);
});
