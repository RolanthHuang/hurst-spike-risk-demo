# 公開版資料字典

本專案只接受已經在內部環境完成欄位挑選、去識別化與正規化的事件 CSV。附件中的實際資料列、真實 IP、UID、device ID、時間戳與內部資料表名稱都沒有放入此 repository。

## 正規化輸入欄位

| 欄位 | 型態 | 用途 | 公開 demo 值 |
|---|---|---|---|
| `event_time` | ISO 8601 timestamp | 切日與時間分桶 | UTC、帶 `Z` |
| `user_id` | string | spike 時窗中的使用者集合 | `demo_user_*` |
| `ip` | string | 可選分析特徵 | RFC 文件專用網段 |
| `device_id` | string | 可選分析特徵 | `demo_device_*` |
| `device_type` | string | 可選分析特徵 | `Browser`、`Mobile`、`Emulator` |

## 私有來源欄位對應

三類來源都可在私有 ETL 中轉成相同 schema：

| 私有來源類型 | 使用者欄位 | 特徵欄位 | 時間欄位 |
|---|---|---|---|
| device information | `uid` | `ip` / `device_id` / `device_type` | `created_at` |
| device trajectory | `uid` | `ip` / `device_id` / `device_type` | `created_at` |
| login log | `user_id` | `ip` / `device_id` / `device` | `created_at` |

建議在匯出前將 `device` 改名為 `device_type`，並將所有時間轉成含 timezone 的 ISO 8601。不同來源若代表不同事件語義，不應直接混在一起；可先各自分析，再在私有環境交叉比對候選 UID。

## 公開前檢查

- 不要上傳原始匯出檔、截圖、notebook output 或本機圖表中的真實值。
- UID 應使用不可逆、帶 salt 的 HMAC；不要只做流水號替換或未加 salt 的 hash。
- IP 可在內部轉為風險特徵或網段分類；公開版本不要保留真實 IP。
- `event_time` 可能具再識別風險，公開資料應模擬生成，而不是只做日期位移。
- 模型輸出、人工標註與風控規則也可能洩漏商業邏輯，發布前需再審查。

