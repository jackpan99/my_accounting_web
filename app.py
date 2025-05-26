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
        styles['Normal'].fontName = 'Noto'
        styles['Title'].fontName = 'Noto'

        elements = [Paragraph("記帳報表", styles['Title']), Spacer(1, 12)]

        # 表格資料標題列
        table_data = [["日期", "類型", "類別", "項目", "金額"]]

        if data:
            for row in data:
                table_data.append([
                    row.get("date", ""),
                    row.get("type", ""),
                    row.get("category", ""),
                    row.get("item", ""),
                    f"{row.get('amount', 0):,.2f}"
                ])
        else:
            # 無資料時補上提示列
            table_data.append(["無資料", "", "", "", ""])

        table = Table(table_data, colWidths=[80, 50, 80, 150, 60])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Noto'),
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

