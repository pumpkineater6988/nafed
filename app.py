import os
from flask import Flask, render_template, request, session, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()

# ---- API Key Setup ----
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
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
    reply = response.text.strip()
    if reply.lower().startswith('assistant:'):
        reply = reply[len('assistant:'):].lstrip()
    return reply

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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
