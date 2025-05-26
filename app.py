import os
import json
import base64
import tempfile
from dotenv import load_dotenv
import firebase_admin
from datetime import datetime
from firebase_admin import credentials
from firebase_admin import firestore
from flask import Flask, render_template, request, jsonify

# 載入 .env
load_dotenv()

# 讀取並解碼 Firebase 金鑰
firebase_b64 = os.getenv("FIREBASE_KEY_B64")
if not firebase_b64:
    raise ValueError("未讀到 FIREBASE_KEY_B64 環境變數")

firebase_json = base64.b64decode(firebase_b64).decode("utf-8")

# 寫入暫存檔，然後關閉後再讀取
with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as tmp:
    tmp.write(firebase_json)
    tmp_path = tmp.name  # 暫存檔路徑

# 現在檔案已寫好，初始化 Firebase
cred = credentials.Certificate(tmp_path)
firebase_admin.initialize_app(cred)

db = firestore.client()

app = Flask(__name__)


def index():
    return render_template("index.html")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    data = request.json
    data["timestamp"] = datetime.now()
    db.collection("transactions").add(data)
    return jsonify({"status": "success"})

@app.route("/get_transactions", methods=["GET"])
def get_transactions():
    docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    result = []
    for doc in docs:
        record = doc.to_dict()
        record["id"] = doc.id
        record["timestamp"] = record["timestamp"].strftime("%Y-%m-%d %H:%M")
        result.append(record)
    return jsonify(result)

from flask import send_file
import pandas as pd
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

@app.route("/export_report")
def export_report():
    format = request.args.get("format", "excel")
    docs = db.collection("transactions").order_by("timestamp").stream()
    data = [doc.to_dict() for doc in docs]

    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=["date", "type", "category", "item", "amount"])

    if format == "excel":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="記帳報表")
        output.seek(0)
        return send_file(output, download_name="記帳報表.xlsx", as_attachment=True)

    elif format == "pdf":
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
       # styles['Normal'].fontName = 'Noto'
       # styles['Title'].fontName = 'Noto'

        try:
            # 嘗試載入專案中的字型檔
            font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'NotoSansTC-Regular.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                styles['Normal'].fontName = 'CustomFont'
                styles['Title'].fontName = 'CustomFont'
                font_name = 'CustomFont'
            else:
                # 回退到系統預設字型
                font_name = 'Helvetica'
        except:
            # 如果字型載入失敗，使用預設字型
            font_name = 'Helvetica'
        
        elements = [Paragraph("記帳報表", styles['Title']), Spacer(1, 12)]
        # 建立表格資料
        if not df.empty:
            table_data = [df.columns.tolist()] + df.values.tolist()
        else:
            table_data = [["date", "type", "category", "item", "amount"]]

        table = Table(table_data)

        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),  # 使用動態字型名稱
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))

        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return send_file(buffer, download_name="記帳報表.pdf", as_attachment=True)


   # else:
    #    return jsonify({"error": "Unsupported format"}), 400
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)


