import os
import json
import base64
import tempfile
from dotenv import load_dotenv
import firebase_admin
from datetime import datetime
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, jsonify, send_file, redirect
import pandas as pd
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 載入 .env
load_dotenv()

# 讀取並解碼 Firebase 金鑰
firebase_b64 = os.getenv("FIREBASE_KEY_B64")
if not firebase_b64:
    raise ValueError("未讀到 FIREBASE_KEY_B64 環境變數")
firebase_json = base64.b64decode(firebase_b64).decode("utf-8")
with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as tmp:
    tmp.write(firebase_json)
    tmp_path = tmp.name

cred = credentials.Certificate(tmp_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

app = Flask(__name__)

@app.route("/add", methods=["POST"])
def add():
    uid = request.form.get("uid")
    if not uid:
        return "請先登入", 401

    # 收集表單資料
    category = request.form["category"]
    amount = float(request.form["amount"])
    note = request.form.get("note", "")
    ttype = request.form.get("type", "支出")
    timestamp = datetime.datetime.now()

    # 存入 Firestore，使用者的 UID 為根節點
    db.collection("users").document(uid).collection("transactions").add({
        "category": category,
        "amount": amount,
        "note": note,
        "type": ttype,
        "timestamp": timestamp
    })
    return redirect("/")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/reset")
def reset():
    return render_template("reset.html")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    try:
        data = request.get_json()
        if not data or "uid" not in data:
            return jsonify({"error": "缺少 uid"}), 400

        data["timestamp"] = datetime.now()
        db.collection("users").document(data["uid"]).collection("transactions").add(data)
        return jsonify({"status": "success"})
    except Exception as e:
        print("❌ 新增失敗：", e)
        return jsonify({"error": str(e)}), 500



@app.route("/get_transactions", methods=["GET", "POST"])
def get_transactions():
    uid = None
    if request.method == "POST":
        data = request.get_json()
        uid = data.get("uid")
    elif request.method == "GET":
        uid = request.args.get("uid")

    if not uid:
        return jsonify([])

    docs = db.collection("users").document(uid).collection("transactions") \
        .order_by("timestamp", direction=firestore.Query.DESCENDING).stream()

    result = []
    for doc in docs:
        record = doc.to_dict()
        record["id"] = doc.id
        record["date"] = record["timestamp"].strftime("%Y-%m-%d")
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
        # PDF 字型修正：預設用 Helvetica，避免 Render 502
        styles['Normal'].fontName = 'Helvetica'
        styles['Title'].fontName = 'Helvetica'
        font_name = 'Helvetica'
        # 若你有自訂字型檔，可用下列方式註冊
        # try:
        #     font_path = os.path.join(app.root_path, 'fonts', 'NotoSansTC-Regular.ttf')
        #     pdfmetrics.registerFont(TTFont('Noto', font_path))
        #     styles['Normal'].fontName = 'Noto'
        #     styles['Title'].fontName = 'Noto'
        #     font_name = 'Noto'
        # except Exception as e:
        #     font_name = 'Helvetica'

        elements = [Paragraph("記帳報表", styles['Title']), Spacer(1, 12)]
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
            table_data.append(["無資料", "", "", "", ""])
        table = Table(table_data, colWidths=[80, 50, 80, 150, 60])
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

# favicon 路由（避免 404）
@app.route('/favicon.ico')
def favicon():
    return '', 204

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)




