import os
from dotenv import load_dotenv

load_dotenv()  # 載入 .env 檔案

# 讀取變數
firebase_b64 = os.getenv("FIREBASE_KEY_B64")

# 顯示有沒有成功
print("FIREBASE_KEY_B64 是否讀到？", firebase_b64 is not None)
print("前100字：", firebase_b64[:100] if firebase_b64 else "沒讀到！")
