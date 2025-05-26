import os
import json
import base64
import tempfile
from datetime import datetime
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 載入環境變數
load_dotenv()

# Firebase 初始化
firebase_b64 = os.getenv("FIREBASE_KEY_B64")
if not firebase_b64:
    raise ValueError("未讀到 FIREBASE_KEY_B64 環境變數")

firebase_json = base64.b64decode(firebase_b64).decode("utf-8")

# 使用暫存檔案初始化 Firebase
with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
    tmp.write(firebase_json)
    tmp_path = tmp.name

cred = credentials.Certificate(tmp_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

app = Flask(__name__)

# 路由定義
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

        # 字型處理（兼容 Render 環境）
        font_name = 'Helvetica'  # 預設使用系統字型
        try:
            font_path = os.path.join(app.root_path, 'static/fonts/NotoSansTC-Regular.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                styles['Normal'].fontName = 'CustomFont'
                styles['Title'].fontName = 'CustomFont'
                font_name = 'CustomFont'
        except Exception as e:
            print(f"字型載入失敗，使用預設字型: {str(e)}")

        # 建立 PDF 內容
        elements = [Paragraph("記帳報表", styles['Title']), Spacer(1, 12)]
        table_data = [df.columns.tolist()] + df.values.tolist() if not df.empty else [["無資料"]]
        table = Table(table_data)
        
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))

        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return send_file(buffer, download_name="記帳報表.pdf", as_attachment=True)

import os
from flask import send_from_directory

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)  # Render 需關閉 debug 模式



