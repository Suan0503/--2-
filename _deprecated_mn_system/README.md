# 已停用 - 舊版 MN System

## 停用日期
2026年1月21日

## 原因
此目錄包含已停用的舊版 MN System（原 `web-production-9351.up.railway.app`）相關檔案。

目前系統已全面改用新的後台管理系統：
- **新系統網址**: https://mingteaai.up.railway.app/admin/home
- **主要功能**: 白名單管理、黑名單管理、錢包管理、預約系統、統計報表等

## 已移除的檔案

### 路由檔案
- `external.py` - 舊版 MN System 所有路由

### 模板檔案
- `base_modern.html` - 舊版基礎模板
- `home_modern.html` - 舊版首頁
- `external_login.html` - 舊版登入頁
- `external_register.html` - 舊版註冊頁
- `external_features.html` - 舊版功能頁
- `external_admin.html` - 舊版管理頁
- `external_company.html` - 舊版公司管理頁
- `external_customer.html` - 舊版客戶頁
- `external_embed.html` - 舊版嵌入頁

## 相關變更

### app.py
已註釋掉以下內容：
```python
# from routes.external import external_bp  # 已停用
# app.register_blueprint(external_bp)  # 已停用
```

### 資料庫
相關資料表（如 ExternalUser, Company 等）仍保留在資料庫中，以備不時之需。
如需完全移除，請參考以下 SQL：
```sql
-- 謹慎操作！執行前請先備份資料庫
DROP TABLE IF EXISTS company_user;
DROP TABLE IF EXISTS feature_flag;
DROP TABLE IF EXISTS company;
DROP TABLE IF EXISTS external_user;
```

## 如需恢復
如需恢復舊系統，請執行以下步驟：
1. 將此目錄中的檔案復原到原位置
2. 在 `app.py` 中取消註釋 external_bp 相關程式碼
3. 重新啟動應用程式

---

**備註**: 此備份僅供緊急恢復使用，建議在確認新系統穩定運作後，定期清理此目錄。
