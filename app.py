from flask import Flask, render_template, request, flash, redirect, session, url_for
import sqlite3
import pickle
import numpy as np
import requests
import telepot

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Needed for sessions

# Load ML model
knn = pickle.load(open("model/model.pkl", "rb"))

# Telegram Bot
bot = telepot.Bot("7995281110:AAFIRdf0n7QLCtT9IKqPPsASOcELUG3graM")
ch_id = "2069255228"


# ---------------- HOME ----------------
@app.route('/')
def home():
    return render_template('home.html')


# ---------------- LOGIN/REGISTER PAGES ----------------
@app.route('/index')
def index():
    return render_template('index.html')


@app.route('/userlog', methods=['POST'])
def userlog():
    name = request.form['name']
    password = request.form['password']

    connection = sqlite3.connect('user_data.db')
    cursor = connection.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS user(
        name TEXT, password TEXT, mobile TEXT, email TEXT
    )""")

    cursor.execute("SELECT name, password FROM user WHERE name=? AND password=?", (name, password))
    result = cursor.fetchone()

    if result:
        session['user'] = name  # Save user in session
        # Fetch ECG data
        data = requests.get("https://api.thingspeak.com/channels/2777003/feeds.json?results=2").json()['feeds'][-1]
        hb = data['field1']
        temp = data['field2']
        ecg = data['field3']
        return render_template('fetal.html', hb=hb, temp=temp, ecg=ecg, name=name)
    else:
        flash('Incorrect Credentials, Try Again')
        return redirect(url_for('index'))


@app.route('/userreg', methods=['POST'])
def userreg():
    name = request.form['name']
    password = request.form['password']
    mobile = request.form['phone']
    email = request.form['email']

    connection = sqlite3.connect('user_data.db')
    cursor = connection.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS user(
        name TEXT, password TEXT, mobile TEXT, email TEXT
    )""")
    cursor.execute("INSERT INTO user VALUES (?, ?, ?, ?)", (name, password, mobile, email))
    connection.commit()

    flash('Successfully Registered! Please login.')
    return redirect(url_for('index'))


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out successfully!')
    return redirect(url_for('index'))


# ---------------- DASHBOARD ----------------
@app.route("/fetalPage", methods=['GET'])
def fetalPage():
    if not session.get('user'):
        flash("Please login first!")
        return redirect(url_for('index'))

    data = requests.get("https://api.thingspeak.com/channels/2777003/feeds.json?results=2").json()['feeds'][-1]
    hb = data['field1']
    temp = data['field2']
    ecg = data['field3']
    return render_template('fetal.html', hb=hb, temp=temp, ecg=ecg, name=session['user'])


# ---------------- PREDICTION ----------------
@app.route("/predict", methods=['POST'])
def predictPage():
    if not session.get('user'):
        flash("Please login first!")
        return redirect(url_for('index'))

    name = request.form['name']
    age = int(request.form['age'])
    Gender = int(request.form['Gender'])
    height = float(request.form['height'])
    Weight = float(request.form['Weight'])
    ECG = float(request.form['ECG'])
    his = int(request.form['his'])
    Heart_Rate = float(request.form['Heart_Rate'])
    Temperature = float(request.form['Temperature'])

    history = "Cardiac Arrest Happened" if his else "No Previous Cardiac Arrest"

    data = np.array([[age, Gender, height, Weight, ECG, Heart_Rate, Temperature]])
    prediction = knn.predict(data)[0]

    avg_ecg = 367.2
    deviation = abs(ECG - avg_ecg) / avg_ecg * 100
    deviation = f"{deviation:.2f}"

    # Risk Classification
    def classify_risk(pred):
        if pred in [5,6,7,8,9,10]:
            return ["LOW",
                    "Regular Checkups: Continue periodic monitoring.",
                    "Avoid Excessive Stimulants.",
                    "Regular Exercise: Moderate activity.",
                    "Balanced Diet: Heart-healthy foods."]
        elif pred in [2,3,4,14]:
            return ["High",
                    "Monitor Symptoms Closely.",
                    "Follow Medication Plans.",
                    "Stress Management: Yoga/Meditation.",
                    "Quit Smoking."]
        elif pred in [15,16]:
            return ["Moderate",
                    "Immediate Medical Attention.",
                    "Restrict Strenuous Activities.",
                    "Low-Sodium Diet.",
                    "Weight Management."]
        else:
            return ['Unknown']

    risk = classify_risk(prediction)

    # Result mapping
    result_map = {
        1: 'Normal', 2: 'Ischemic changes (Coronary Artery)', 3: 'Old Anterior Myocardial Infarction',
        4: 'Old Inferior Myocardial Infarction', 5: 'Sinus tachycardia', 6: 'Ventricular Premature Contraction (PVC)',
        7: 'Supraventricular Premature Contraction', 8: 'Left bundle branch block', 9: 'Right bundle branch block',
        10: 'Left ventricle hypertrophy', 14: 'Atrial Fibrillation or Flutter', 15: 'Others1', 16: 'Others2'
    }
    status = result_map.get(prediction, "Unknown")

    # Send Telegram alert if not normal
    if prediction != 1:
        bot.sendMessage(ch_id,f" Name : {name} \n Age : {age} \n Gender : {Gender} \n ECG : {ECG} \n Heart Rate : {Heart_Rate} \n Temperature : {Temperature} \n Risk Level : {risk[0]} \n Deviation percentage : {deviation} % \n History : {history}")
    else:
        bot.sendMessage(ch_id,f" Name : {name} \n Risk Level : No Risk, You are Healthy ")

    return render_template('predict.html', name=name, pred=prediction, status=status, risk=risk, cent=deviation)


if __name__ == "__main__":
    app.run(debug=True)
