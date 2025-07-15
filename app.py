import os
from flask import Flask, render_template, request, session, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()
import mysql.connector
from datetime import datetime

# ---- API Key Setup ----
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.api_key = GEMINI_API_KEY
    model = genai.GenerativeModel('gemini-1.5-pro')
else:
    raise RuntimeError("GEMINI_API_KEY not found in environment variables. Please set it and restart.")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "replace_this_secret")

# ---- System Prompt ----
# SYSTEM_PROMPT removed as per user request

def call_gemini(messages):
    prompt_text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in messages])
    response = model.generate_content(prompt_text)
    return response.text

# MySQL Database Configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '1437',
    'database': 'testing'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

def init_database():
    conn = get_db_connection()
    if conn is None:
        return
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS chats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255),
        created_time DATETIME,
        last_updated DATETIME
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INT AUTO_INCREMENT PRIMARY KEY,
        chat_id INT,
        role VARCHAR(50),
        content TEXT,
        timestamp DATETIME,
        FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
    )''')
    conn.commit()
    cursor.close()
    conn.close()

init_database()

@app.route("/")
def index():
    session.clear()  # Clear session on new visit to ensure fresh chat
    session["chat"] = [
        {"role": "assistant", "content": "Hi! I’m the NAFED Auction Assistant. Please select your role (Bidder / HO-BO / Warehouse) and ask your question."}
    ]
    return render_template("chat.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_msg = data.get("message", "")
    role = data.get("role", "Bidder")

    chat_history = session.get("chat", [])
    chat_history.append({"role": "user", "content": f"[Role: {role}] {user_msg}"})

    assistant_reply = call_gemini(chat_history)
    chat_history.append({"role": "assistant", "content": assistant_reply})
    session["chat"] = chat_history

    return jsonify({"reply": assistant_reply})

@app.route("/api/chats", methods=["GET"])
def list_chats():
    conn = get_db_connection()
    if conn is None:
        return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, title, created_time, last_updated FROM chats ORDER BY last_updated DESC")
    chats = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(chats)

@app.route("/api/chats", methods=["POST"])
def create_chat():
    data = request.get_json() or {}
    title = data.get("title", f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    now = datetime.now()
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chats (title, created_time, last_updated) VALUES (%s, %s, %s)", (title, now, now))
    chat_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"id": chat_id, "title": title, "created_time": now, "last_updated": now})

@app.route("/api/chats/<int:chat_id>/rename", methods=["POST"])
def rename_chat(chat_id):
    data = request.get_json() or {}
    new_title = data.get("title", "Untitled Chat")
    now = datetime.now()
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor()
    cursor.execute("UPDATE chats SET title=%s, last_updated=%s WHERE id=%s", (new_title, now, chat_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"id": chat_id, "title": new_title, "last_updated": now})

@app.route("/api/chats/<int:chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chats WHERE id=%s", (chat_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/chats/<int:chat_id>/messages", methods=["GET"])
def get_chat_messages(chat_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, role, content, timestamp FROM messages WHERE chat_id=%s ORDER BY timestamp ASC", (chat_id,))
    messages = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(messages)

@app.route("/api/chats/<int:chat_id>/messages", methods=["POST"])
def add_chat_message(chat_id):
    data = request.get_json() or {}
    role = data.get("role")
    content = data.get("content")
    now = datetime.now()
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "DB connection failed"}), 500
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (chat_id, role, content, timestamp) VALUES (%s, %s, %s, %s)", (chat_id, role, content, now))
    cursor.execute("UPDATE chats SET last_updated=%s WHERE id=%s", (now, chat_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
