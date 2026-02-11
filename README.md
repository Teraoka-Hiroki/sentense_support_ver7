## 量子アニーリング駆動型 小説執筆支援アプリ

Flask と Gemini API、Fixstars Amplify を用いた **小説執筆支援アプリ** です。  
シーン描写（Scene Craft）とキャラクター・ダイナミクス（Character Dynamics）の候補ブロックを生成し、  
量子アニーリングと Human-in-the-Loop 最適化で、好みに合った場面構成を提案します。

---

### 動作環境

- Python 3.10 以上推奨（3.12 でも動作想定）
- Windows 10 / 11

---

### セットアップ手順

1. このフォルダに移動

   ```powershell
   cd "C:\Users\goodh\Documents\Qquest2025\setensesport7"
   ```

2. 仮想環境（任意だが推奨）

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. 依存ライブラリのインストール

   ```powershell
   pip install -r requirements.txt
   ```

4. `settings.json` に API キーを保存  
   - `gemini_key` に Gemini API Key  
   - `amplify_token` に Fixstars Amplify Token  

   ※ `settings.json` は `.gitignore` に登録済みで、GitHub にはアップロードされません。

---

### アプリの起動方法

```powershell
cd "C:\Users\goodh\Documents\Qquest2025\setensesport7"
python app.py
```

起動後、ブラウザで次の URL を開きます。

- `http://127.0.0.1:5000/`  または  `http://localhost:5000/`

---

### ライセンス

（必要に応じて追記してください）

