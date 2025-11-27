from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
import re
import time
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = "AIzaSyCdBwR5Nt8LFNKm0dzFrprak3Oh8UM9L6c"

pending_confirm = {}

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="@Jitu9351",
        database="leadmanagement"
    )

def load_live_schema():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = [t[0] for t in cur.fetchall()]
    text = "Database: leadmanagement\n"
    for t in tables:
        cur.execute(f"DESCRIBE {t}")
        rows = cur.fetchall()
        cols = ", ".join([r[0] for r in rows])
        text += f"Table: {t} ({cols})\n"
    cur.close()
    conn.close()
    return text

schema_info = load_live_schema()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key=GEMINI_API_KEY,
    temperature=0.1
)

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an expert MySQL query generator.\n"
     "Always output ONLY valid MySQL queries.\n"
     "Never generate sqlite_master or SQLite syntax.\n"
     "Database name: leadmanagement.\n"
     "Rules:\n"
     "- To list tables use: SHOW TABLES;\n"
     "- To describe tables use: DESCRIBE table_name;\n"
     "- Never use sqlite_master or PRAGMA.\n"
     "LIVE SCHEMA:\n" + schema_info),
    ("user", "{question}")
])

chain = prompt | llm


def handle_special(q):
    q1 = q.lower()
    conn = get_connection()
    cur = conn.cursor()
    if "which database" in q1:
        cur.close()
        conn.close()
        return "leadmanagement"
    if "how many tables" in q1:
        cur.execute("SHOW TABLES")
        count = len(cur.fetchall())
        cur.close()
        conn.close()
        return str(count)
    if "list tables" in q1 or "sabhi table" in q1:
        cur.execute("SHOW TABLES")
        data = cur.fetchall()
        tables = [t[0] for t in data]
        cur.close()
        conn.close()
        return {"tables": tables}
    cur.close()
    conn.close()
    return None


def is_unsafe(sql):
    s = sql.lower().strip()
    if "drop table" in s:
        return True
    if "delete" in s and "where" not in s:
        return True
    if s.startswith("update") and "where" not in s:
        return True
    return False


def clean_sql(raw):
    raw = raw.replace("```sql", "").replace("```", "").strip()
    match = re.search(
        r"(select|insert|update|delete|create|alter|drop|show)[\s\S]+",
        raw,
        re.IGNORECASE
    )
    if not match:
        return None
    return match.group(0).strip()


def execute_sql(sql):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql)
        if sql.lower().startswith(("select", "show")):
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            rows_dict = [dict(zip(cols, r)) for r in rows]
            cur.close()
            conn.close()
            return {"columns": cols, "rows": rows_dict}
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}


@app.route("/")
def index():
    return render_template("chatbot.html")


@app.route("/chat", methods=["POST"])
def chat():
    global schema_info, prompt, chain

    user_text = request.json.get("question", "")
    session_id = request.remote_addr

    special = handle_special(user_text)
    if special:
        return jsonify({"answer": special})

    if user_text.strip().upper() == "YES":
        if session_id in pending_confirm:
            sql_to_run = pending_confirm[session_id]["sql"]
            del pending_confirm[session_id]
            result = execute_sql(sql_to_run)
            return jsonify({"answer": result, "sql": sql_to_run})
        return jsonify({"answer": "No pending confirmation."})

    schema_info = load_live_schema()
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an expert MySQL query generator.\n"
         "Always output ONLY valid MySQL queries.\n"
         "Never generate sqlite_master or SQLite syntax.\n"
         "Database name: leadmanagement.\n"
         "Rules:\n"
         "- To list tables use: SHOW TABLES;\n"
         "- To describe tables use: DESCRIBE table_name;\n"
         "- Never use sqlite_master or PRAGMA.\n"
         "LIVE SCHEMA:\n" + schema_info),
        ("user", "{question}")
    ])
    chain = prompt | llm

    ai_raw = chain.invoke({"question": user_text}).content
    sql = clean_sql(ai_raw)

    if not sql:
        return jsonify({"answer": "No valid SQL generated."})

    if is_unsafe(sql):
        pending_confirm[session_id] = {"sql": sql, "time": time.time()}
        return jsonify({"answer": "This operation is dangerous. Type YES to confirm.", "sql": sql})

    result = execute_sql(sql)
    return jsonify({"answer": result, "sql": sql})


if __name__ == "__main__":
    app.run(debug=True)
