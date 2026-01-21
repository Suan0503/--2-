# 🗑️ 系統清理報告 - 移除舊版 MN System

## 📅 執行日期
2026年1月21日

## 🎯 清理目的
移除已不再使用的舊版 MN System（`web-production-9351.up.railway.app`），統一使用新的後台管理系統 `mingteaai.up.railway.app/admin/home`。

---

## ✅ 已完成的變更

### 1. **停用 Blueprint 註冊**
**檔案**: `app.py`

已註釋掉舊系統的路由註冊：
```python
# from routes.external import external_bp  # 已停用舊的 MN System
# app.register_blueprint(external_bp)  # 已停用
```

### 2. **移動檔案到備份目錄**
建立 `_deprecated_mn_system/` 目錄，並移動以下檔案：

#### 路由檔案
- ✅ `routes/external.py` → `_deprecated_mn_system/external.py`

#### 模板檔案
- ✅ `templates/base_modern.html` → `_deprecated_mn_system/base_modern.html`
- ✅ `templates/home_modern.html` → `_deprecated_mn_system/home_modern.html`
- ✅ `templates/external_login.html` → `_deprecated_mn_system/external_login.html`
- ✅ `templates/external_register.html` → `_deprecated_mn_system/external_register.html`
- ✅ `templates/external_features.html` → `_deprecated_mn_system/external_features.html`
- ✅ `templates/external_admin.html` → `_deprecated_mn_system/external_admin.html`
- ✅ `templates/external_company.html` → `_deprecated_mn_system/external_company.html`
- ✅ `templates/external_customer.html` → `_deprecated_mn_system/external_customer.html`
- ✅ `templates/external_embed.html` → `_deprecated_mn_system/external_embed.html`

### 3. **更新連結**
已將以下檔案中的舊 URL 更新為新 URL：

- ✅ `templates/manual_verify.html` - 「回主頁」連結
  - 舊: `https://web-production-9351.up.railway.app/admin/`
  - 新: `https://mingteaai.up.railway.app/admin/home`

- ✅ `templates/admin_dashboard.html` - 「回首頁」連結
  - 舊: `https://web-production-9351.up.railway.app/admin/home`
  - 新: `https://mingteaai.up.railway.app/admin/home`

---

## 📊 當前系統狀態

### 保留的 Blueprint
✅ `message_bp` - LINE Bot 訊息處理  
✅ `pending_bp` - 待驗證管理  
✅ `admin_bp` - 後台管理系統（主要使用）  
❌ `external_bp` - 舊版 MN System（已停用）

### 保留的模板目錄
```
templates/
├── admin/                    # 新版後台管理模板
├── site/                     # 網站前台模板（如有使用）
├── admin_home.html          # 新版後台首頁
├── admin_dashboard.html     # 新版儀表板
├── admin_richmenu.html      # 圖文選單管理
├── manual_verify.html       # 手動驗證
├── pending_verify.html      # 待驗證列表
├── wallet*.html             # 錢包相關頁面
├── wage_reconcile.html      # 薪資對帳
├── schedule.html            # 預約系統
└── ...其他功能頁面
```

---

## 🗄️ 資料庫狀態

### 保留的資料表
以下與舊 MN System 相關的資料表仍保留在資料庫中：
- `external_user` - 外部用戶表
- `company` - 公司表
- `company_user` - 公司用戶關聯表
- `feature_flag` - 功能開關表

**建議**: 如確認不再需要，可考慮在確保資料備份後移除這些表。

---

## 🔄 回復步驟（如需要）

如需恢復舊系統，請執行以下步驟：

1. **還原檔案**
   ```powershell
   cd d:\GUTHUB\--2-
   Move-Item -Path "_deprecated_mn_system\external.py" -Destination "routes\external.py" -Force
   Move-Item -Path "_deprecated_mn_system\*.html" -Destination "templates\" -Force
   ```

2. **取消註釋 app.py**
   ```python
   from routes.external import external_bp
   app.register_blueprint(external_bp)
   ```

3. **重新啟動應用**
   ```powershell
   python app.py
   ```

---

## ⚠️ 注意事項

1. **舊 URL 重定向**: 如有外部連結指向 `web-production-9351.up.railway.app`，建議設定 301 重定向到新 URL
2. **資料庫清理**: 建議在確認系統穩定運作 1-2 個月後，再考慮清理舊資料表
3. **備份**: `_deprecated_mn_system/` 目錄建議保留至少 3 個月，以備不時之需

---

## 📈 效益

✅ 簡化系統架構  
✅ 減少維護成本  
✅ 統一用戶體驗  
✅ 降低混淆風險  
✅ 提升系統清晰度  

---

**執行人員**: AI Assistant  
**確認人員**: _____________  
**備註**: 所有變更已完成並測試通過
