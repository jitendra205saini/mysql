from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = "AIzaSyD_SKzx_rUxC4sr8935wgTntyRb0zKO8Nc"

db_conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="@Jitu9351",
    database="leadmanagement",
    autocommit=True
)

cursor = db_conn.cursor()


def load_live_schema():
    cursor.execute("SHOW TABLES")
    tables = [t[0] for t in cursor.fetchall()]
    schema_text = "Database: leadmanagement\n"
    for table in tables:
        cursor.execute(f"DESCRIBE {table}")
        rows = cursor.fetchall()
        columns = ", ".join([r[0] for r in rows])
        schema_text += f"Table: {table} ({columns})\n"
    return schema_text


schema_info = load_live_schema()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key=GEMINI_API_KEY,
    temperature=0.1
)

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a MySQL specialist. Output only VALID SQL queries.\n"
     "No explanation. Only SQL.\n\n"
     "LIVE Database Schema:\n" + schema_info),
    ("user", "{question}")
])

chain = prompt | llm


def handle_special(q):
    q1 = q.lower()

    if "which database" in q1 or "database name" in q1:
        return "The database name is: leadmanagement"

    if "how many tables" in q1 or "number of tables" in q1:
        cursor.execute("SHOW TABLES")
        return f"Total {len(cursor.fetchall())} tables are present."

    if "list tables" in q1 or "table names" in q1:
        cursor.execute("SHOW TABLES")
        data = cursor.fetchall()
        output = "Tables List:\n\n"
        for i, t in enumerate(data, start=1):
            output += f"{i}. {t[0]}\n"
        return output

    return None


def clean_sql(raw):
    raw = raw.replace("```sql", "").replace("```", "")
    match = re.search(
        r"(select|insert|update|delete|create|alter|drop|show)[\s\S]+",
        raw,
        re.IGNORECASE
    )
    if not match:
        return None
    sql = match.group(0).strip()
    return sql


def execute_sql(sql):
    try:
        cursor.execute(sql)
        if sql.lower().startswith(("select", "show")):
            rows = cursor.fetchall()
            if not rows:
                return "No data found."
            return "\n".join(", ".join(str(c) for c in r) for r in rows)
        return "Query executed successfully."
    except Exception as e:
        return f"SQL Error: {str(e)}"


@app.route("/")
def index():
    return render_template("chatbot.html")


@app.route("/chat", methods=["POST"])
def chat():
    global schema_info, prompt, chain

    schema_info = load_live_schema()

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a MySQL specialist. Output only VALID SQL.\n"
         "No explanation. Only SQL.\n\n"
         "LIVE Database Schema:\n" + schema_info),
        ("user", "{question}")
    ])

    chain = prompt | llm

    question = request.json.get("question", "")

    special = handle_special(question)
    if special:
        return jsonify({"answer": special})

    raw = chain.invoke({"question": question}).content
    sql = clean_sql(raw)

    if sql is None:
        return jsonify({"answer": "The AI did not generate a valid SQL query."})

    result = execute_sql(sql)
    return jsonify({"answer": result, "sql": sql})


if __name__ == "__main__":
    app.run(debug=True)
