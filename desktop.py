import threading
import webview
from app import app   # your Flask app

def run_flask():
    app.run(host="127.0.0.1", port=5000, debug=False)

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    webview.create_window("Bank Fraud Detection System", "http://127.0.0.1:5000")
    webview.start()