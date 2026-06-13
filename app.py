import matplotlib.pyplot as plt
import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import joblib
from datetime import datetime
from flask_mail import Mail, Message

app = Flask(__name__)

# ---------------- CONFIG ----------------
UPLOAD_FOLDER = 'static/profile_pics'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'noemwizard20@gmail.com'
app.config['MAIL_PASSWORD'] = 'obcgrxsfmtxawbcy'

mail = Mail(app)
app.secret_key = "supersecretkey"

# Load ML model
model = joblib.load("model/fraud_model.pkl")


# ---------------- HOME ----------------
@app.route('/')
def index():
    return render_template('welcome.html')


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def do_login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form['username']
    password = request.form['password']

    conn = sqlite3.connect('fraud_logs.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cursor.fetchone()

    conn.close()

    if user and check_password_hash(user[5], password):
        session['user_id'] = user[0]
        session['email'] = user[1]
        session['username'] = user[2]
        return redirect(url_for('home'))

    return render_template('login.html', error="Invalid credentials")


# ---------------- HOME PAGE ----------------
@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('do_login'))

    return render_template('index.html', username=session['username'])


# ---------------- PREDICTION ----------------
@app.route('/predict', methods=['POST'])
def predict():
    if 'user_id' not in session:
        return redirect(url_for('do_login'))

    amount = float(request.form['amount'])
    time = float(request.form['time'])

    # ----------------------------
    # GET USER ALERT SETTINGS
    # ----------------------------
    conn = sqlite3.connect('fraud_logs.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT min_alert_amount, max_alert_amount, email, username
        FROM users
        WHERE id=?
    """, (session['user_id'],))

    user_data = cursor.fetchone()
    conn.close()

    min_limit = user_data[0]
    max_limit = user_data[1]
    user_email = user_data[2]
    username = user_data[3]

    # ----------------------------
    # ML INPUT
    # ----------------------------
    features = [time] + [0]*28 + [amount]
    columns = ['Time'] + [f'V{i}' for i in range(1, 29)] + ['Amount']
    input_data = pd.DataFrame([features], columns=columns)

    prediction = model.predict(input_data)[0]

    # ----------------------------
    # FRAUD LOGIC
    # ----------------------------
    if amount < min_limit or amount > max_limit or prediction == 1:
        result = "Fraudulent Transaction Detected!"

        # ----------------------------
        # SEND EMAIL ALERT
        # ----------------------------
        msg = Message(
            'Fraud Alert',
            sender=app.config['MAIL_USERNAME'],
            recipients=[user_email]
        )

        msg.body = f"""
Dear {username},
This email is from bank secure 
Suspicious transaction detected.

Time: {time}
Amount: ${amount}

Please check immediately.
Thank you for always using bank secure.
"""

        mail.send(msg)

        # ----------------------------
        # SAVE EMAIL LOG
        # ----------------------------
        conn = sqlite3.connect("fraud_logs.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO email_logs (recipient, message, time)
            VALUES (?, ?, ?)
        """, (user_email, msg.body, str(datetime.now())))
        conn.commit()
        conn.close()

    else:
        result = "Transaction is Legitimate"

    # ----------------------------
    # SAVE FRAUD LOG
    # ----------------------------
    conn = sqlite3.connect("fraud_logs.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO fraud_logs
        (transaction_time, amount, status, user_id)
        VALUES (?, ?, ?, ?)
    """, (time, amount, result, session['user_id']))

    conn.commit()
    conn.close()

    return render_template(
        'index.html',
        prediction_text=result,
        username=session['username']
    )
# ---------------- SIGNUP ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':

        email = request.form['email']
        username = request.form['username']
        bank_name = request.form['bank_name']
        card_number = request.form['card_number']
        password = generate_password_hash(request.form['password'])

        conn = sqlite3.connect('fraud_logs.db')
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO users
            (email, username, bank_name, card_number, password)
            VALUES (?, ?, ?, ?, ?)
        """, (email, username, bank_name, card_number, password))

        conn.commit()
        conn.close()

        return redirect(url_for('do_login'))

    return render_template('signup.html')


# ---------------- PROFILE ----------------
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('do_login'))

    conn = sqlite3.connect('fraud_logs.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user = cursor.fetchone()

    conn.close()

    return render_template('profile.html', user=user)

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('do_login'))

    conn = sqlite3.connect('fraud_logs.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']

        cursor.execute("""
            UPDATE users
            SET username=?, email=?
            WHERE id=?
        """, (username, email, session['user_id']))

        conn.commit()

    cursor.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user = cursor.fetchone()

    conn.close()

    return render_template('edit_profile.html', user=user)

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('do_login'))

    conn = sqlite3.connect("fraud_logs.db")
    cursor = conn.cursor()

    cursor.execute(
    "SELECT * FROM fraud_logs WHERE user_id=?",
    (session['user_id'],)
)
    logs = cursor.fetchall()

    conn.close()

    return render_template('dashboard.html', logs=logs, username=session['username'])


# ---------------- EMAILS ----------------
@app.route('/emails')
def emails():
    if 'user_id' not in session:
        return redirect(url_for('do_login'))

    conn = sqlite3.connect("fraud_logs.db")
    cursor = conn.cursor()

    cursor.execute(
    "SELECT * FROM email_logs WHERE recipient=?",
    (session['email'],)
)
    emails = cursor.fetchall()

    conn.close()

    return render_template('emails.html', emails=emails)


# ---------------- ANALYTICS ----------------
@app.route('/analytics')
def analytics():
    if 'user_id' not in session:
        return redirect(url_for('do_login'))

    conn = sqlite3.connect("fraud_logs.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM fraud_logs WHERE status='Fraudulent Transaction Detected!'")
    fraud_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM fraud_logs WHERE status='Transaction is Legitimate'")
    legit_count = cursor.fetchone()[0]

    conn.close()

    return render_template(
        'analytics.html',
        fraud_count=fraud_count,
        legit_count=legit_count
    )


# ---------------- ALERT SETTINGS ----------------
@app.route('/alert-settings', methods=['GET', 'POST'])
def alert_settings():
    if 'user_id' not in session:
        return redirect(url_for('do_login'))

    conn = sqlite3.connect('fraud_logs.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        min_amount = request.form['min_amount']
        max_amount = request.form['max_amount']

        cursor.execute("""
            UPDATE users
            SET min_alert_amount=?,
                max_alert_amount=?
            WHERE id=?
        """, (min_amount, max_amount, session['user_id']))

        conn.commit()

    cursor.execute("""
        SELECT min_alert_amount, max_alert_amount
        FROM users
        WHERE id=?
    """, (session['user_id'],))

    settings = cursor.fetchone()

    conn.close()

    return render_template('alert_settings.html', settings=settings)


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('do_login'))


# ---------------- RUN ----------------
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)