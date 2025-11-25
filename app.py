from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

app = Flask(__name__)
CORS(app)


GEMINI_API_KEY = "AIzaSyAcVqoZv6VjhcS6WTXOueHKnKMqQ6Ulo64"


db_conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="@Jitu9351",
    database="leadmanagement",
    autocommit=True
)
cursor = db_conn.cursor()


def load_live_schema():
    cursor.execute("SHOW TABLES ")
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
    temperature=0.2
)

prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Tum ek human-style MySQL expert ho. Tum sirf VALID SQL query output karoge.\n"
     "Koi explanation nahi. Sirf SQL.\n\n"
     "LIVE Database schema:\n" + schema_info),
    ("user", "{question}")
])

chain = prompt | llm


def handle_special(q):
    q1 = q.lower()

    
    if "kaunsa database" in q1 or "database name" in q1:
        return "Database ka naam: leadmanagement"

  
    if "kitni table" in q1 or "how many tables" in q1:
        cursor.execute("SHOW TABLES")
        count = len(cursor.fetchall())
        return f"Total {count} tables present hain."

    
    if "tables ke naam" in q1 or "list tables" in q1:
        cursor.execute("SHOW TABLES")
        data = cursor.fetchall()

        output = "Yeh rahi sabhi tables ki list:\n\n"
        for i, t in enumerate(data, start=1):
            output += f"{i}. {t[0]}\n"

        return output

    return None



def clean_sql(raw):
    sql = raw.replace("```sql", "").replace("```", "").strip()
    allowed = ["select", "insert", "update", "delete", "create", "alter", "drop", "show"]
    if not any(sql.lower().startswith(x) for x in allowed):
        return None
    return sql



def execute_sql(sql):
    try:
        cursor.execute(sql)

        if sql.lower().startswith("show"):
            rows = cursor.fetchall()
            return "\n".join([x[0] for x in rows])

        if sql.lower().startswith("select"):
            rows = cursor.fetchall()
            if not rows:
                return "No data found."
            return "\n".join(", ".join(str(i) for i in r) for r in rows)

        return "Query successfully executed."

    except Exception as e:
        return f"SQL Error: {e}"



@app.route("/")
def index():
    return render_template("chatbot.html")


@app.route("/chat", methods=["POST"])
def chat():
    global schema_info, prompt, chain

   
    schema_info = load_live_schema()

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Tum ek MySQL specialist ho. Sirf SQL output karoge.\n\n"
         "LIVE schema:\n" + schema_info),
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
        return jsonify({"answer": "AI ne valid SQL generate nahi kiya."})

    result = execute_sql(sql)
    return jsonify({"answer": result, "sql": sql})


if __name__ == "__main__":
    app.run(debug=True)
