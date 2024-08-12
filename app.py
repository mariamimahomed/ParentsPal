from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify,send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room, leave_room
import openai
import json
import numpy as np
import joblib

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your actual secret key

# Initialize Flask-SocketIO
socketio = SocketIO(app)

# Set your OpenAI API key here
openai.api_key = '################'
# Load Q&A data from file
with open(r'/Users/mariammahomed/Desktop/ParentsPal/qa_pairs.json', 'r', encoding='utf-8') as file:
    qa_data = json.load(file)

# Load the pre-trained model
# model = joblib.load('SGDClassifier.joblib')
model = joblib.load(r'/Users/mariammahomed/Desktop/ParentsPal/SGDClassifier.joblib')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='parentpals',
            user='root',
            password='12345678'
        )
        return connection
    except Error as err:
        print(f"Error: {err}")
        return None

class User(UserMixin):
    def __init__(self, user):
        self.id = user['id']
        self.username = user['username']
        self.email = user['email']
        self.language = None
        self.parent_age = None
        self.gender = None
        self.child_age = None
        self.diagnosis = None
        self.region = None
        self.load_profile()

    def load_profile(self):
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM profiles WHERE username = %s", (self.username,))
        profile = cursor.fetchone()
        connection.close()

        if profile:
            self.language = profile.get('language')
            self.parent_age = profile.get('parent_age')
            self.gender = profile.get('gender')
            self.child_age = profile.get('child_age')
            self.diagnosis = profile.get('diagnosis')
            self.region = profile.get('region')

@login_manager.user_loader
def load_user(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    connection.close()
    if user:
        return User(user)
    return None

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('home.html')

@app.route('/conditions')
def conditions():
    return render_template('conditions.html')

@app.route('/index')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login_or_signup():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'login':
            username = request.form['username']
            password = request.form['password']
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            connection.close()

            if user and check_password_hash(user['password'], password):
                user_obj = User(user)
                login_user(user_obj)
                return redirect(url_for('index'))
            flash('Invalid credentials')

        elif action == 'signup':
            email = request.form['email']
            username = request.form['username']
            password = generate_password_hash(request.form['password'])

            connection = get_db_connection()
            cursor = connection.cursor()
            try:
                cursor.execute('''INSERT INTO users (email, username, password) 
                                  VALUES (%s, %s, %s)''',
                               (email, username, password))
                connection.commit()
                flash('Signup successful! You can now log in.')
                return redirect(url_for('login_or_signup'))
            except mysql.connector.IntegrityError:
                flash('Username or Email already exists.')
            connection.close()

    return render_template('login.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        parent_age = request.form.get('parent_age')
        child_age = request.form.get('child_age')
        gender = request.form.get('gender')
        diagnosis = request.form.get('diagnosis')
        region = request.form.get('region')

        try:
            cursor.execute("SELECT * FROM profiles WHERE user_id = %s", (current_user.id,))
            profile = cursor.fetchone()

            if profile:
                cursor.execute('''
                    UPDATE profiles 
                    SET parent_age = %s, child_age = %s, gender = %s, diagnosis = %s, region = %s
                    WHERE user_id = %s
                ''', (parent_age, child_age, gender, diagnosis, region, current_user.id))
            else:
                cursor.execute('''
                    INSERT INTO profiles (user_id, parent_age, child_age, gender, diagnosis, region)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (current_user.id, parent_age, child_age, gender, diagnosis, region))

            connection.commit()
            flash('Profile updated successfully!')
        except Error as e:
            connection.rollback()
            flash(f'Error updating profile: {str(e)}')
        finally:
            connection.close()
            return redirect(url_for('profile'))

    else:
        cursor.execute("SELECT * FROM profiles WHERE user_id = %s", (current_user.id,))
        profile = cursor.fetchone()
        connection.close()
        return render_template('profile.html', user=current_user, profile=profile)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/match', methods=['GET', 'POST'])
@login_required
def match():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        child_age = request.form['child_age']
        diagnosis = request.form['diagnosis']
        region = request.form['region']

        cursor.execute('''
            SELECT profiles.user_id AS id, users.username, profiles.child_age, profiles.diagnosis 
            FROM profiles 
            JOIN users ON profiles.user_id = users.id 
            WHERE profiles.child_age = %s AND profiles.diagnosis = %s AND profiles.region = %s
        ''', (child_age, diagnosis, region))
        matches = cursor.fetchall()

        connection.close()
        return render_template('match.html', matches=matches)

    return render_template('match.html')

@app.route('/mentor')
@login_required
def mentor():
    return render_template('mentor.html')

@app.route('/chatbot')
@login_required
def chatbot():
    return render_template('chatbot.html')

@app.route('/mentorconnection')
@login_required
def mentconnect():
    return render_template('mentorconnection.html')

@app.route('/api/mentors')
@login_required
def get_mentors():
    return send_from_directory('static/data', 'mentors.json')

@app.route('/chat/<int:match_id>')
@login_required
def chat(match_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE id = %s', (match_id,))
    match = cursor.fetchone()

    cursor.execute('''
        SELECT DISTINCT users.id, users.username 
        FROM chats 
        JOIN users ON (chats.sender_id = users.id OR chats.receiver_id = users.id) 
        WHERE chats.sender_id = %s OR chats.receiver_id = %s
        ''', (current_user.id, current_user.id))
    chats = cursor.fetchall()

    cursor.execute('''
        SELECT users.username AS sender, chats.message AS content 
        FROM chats 
        JOIN users ON chats.sender_id = users.id 
        WHERE (chats.sender_id = %s AND chats.receiver_id = %s)
        OR (chats.sender_id = %s AND chats.receiver_id = %s)
        ORDER BY chats.sent_at ASC
        ''', (current_user.id, match_id, match_id, current_user.id))
    messages = cursor.fetchall()

    connection.close()
    return render_template('chat.html', match=match, chats=chats, messages=messages)

@app.route('/community')
@login_required
def community():
    return render_template('community.html')

@app.route('/netflix')
@login_required
def netflix():
    return render_template('netflix.html')

# SocketIO event handlers

@socketio.on('send_message')
def handle_send_message_event(data):
    emit('receive_message', data, room=data['room'])

@socketio.on('join_room')
def handle_join_room_event(data):
    join_room(data['room'])
    emit('join_room_announcement', data, room=data['room'])

@socketio.on('leave_room')
def handle_leave_room_event(data):
    leave_room(data['room'])
    emit('leave_room_announcement', data, room=data['room'])

# API endpoints for chat (using MySQL)

@app.route('/api/chat/<int:receiver_id>', methods=['POST'])
@login_required
def send_message_api(receiver_id):
    try:
        data = request.get_json()
        message = data['message']

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute('INSERT INTO chats (sender_id, receiver_id, message) VALUES (%s, %s, %s)',
                       (current_user.id, receiver_id, message))
        connection.commit()
        connection.close()

        return jsonify({'status': 'Message sent'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/<int:receiver_id>', methods=['GET'])
@login_required
def get_messages_api(receiver_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('''
            SELECT * FROM chats WHERE 
            (sender_id = %s AND receiver_id = %s) OR 
            (sender_id = %s AND receiver_id = %s)
            ORDER BY sent_at ASC
            ''', (current_user.id, receiver_id, receiver_id, current_user.id))
        messages = cursor.fetchall()
        connection.close()

        return jsonify(messages)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API to get chat history

@app.route('/chat/history')
@login_required
def chat_history():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('''
        SELECT DISTINCT users.id, users.username 
        FROM chats 
        JOIN users ON (chats.sender_id = users.id OR chats.receiver_id = users.id) 
        WHERE chats.sender_id = %s OR chats.receiver_id = %s
        ''', (current_user.id, current_user.id))
    chats = cursor.fetchall()
    connection.close()
    return jsonify(chats)

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    prediction = None
    if request.method == 'POST':
        try:
            # Retrieve and convert input values from form
            A1 = int(request.form['A1'])
            A2 = int(request.form['A2'])
            A3 = int(request.form['A3'])
            A4 = int(request.form['A4'])
            A5 = int(request.form['A5'])
            A6 = int(request.form['A6'])
            A7 = int(request.form['A7'])
            A8 = int(request.form['A8'])
            A9 = int(request.form['A9'])
            A10 = int(request.form['A10'])
            Age_Mons = float(request.form['Age_Mons'])
            Sex = float(request.form['Sex'])
            Ethnicity = float(request.form['Ethnicity'])
            Jaundice = float(request.form['Jaundice'])
            Family_mem_with_ASD = float(request.form['Family_mem_with_ASD'])
            Who_completed_the_test = float(request.form['Who_completed_the_test'])

            # Prepare input data for prediction
            input_data = np.array([[A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, Age_Mons, Sex, Ethnicity, Jaundice, Family_mem_with_ASD, Who_completed_the_test]])
            
            # Make prediction
            prediction = model.predict(input_data)[0]
        except Exception as e:
            print(f"Error: {e}")
            prediction = "Error in prediction. Please check the input values."

    return render_template('test.html', prediction=prediction)

def get_answer_from_openai(question):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question}
        ]
    )
    return response['choices'][0]['message']['content']

@app.route('/welcome_message')
def welcome_message():
    return jsonify({
        "messages": [
            {
                "english": "Welcome to Autism Assist. This chatbot supports both Arabic and English and is dedicated to assisting individuals with autism.",
                "arabic": "مرحبًا بك في مساعد التوحد. هذه الدردشة تدعم كل من العربية والإنجليزية وتهدف إلى مساعدة الأفراد المصابين بالتوحد."
            },
            {
                "english": "Feel free to ask any questions. We are here to help!",
                "arabic": "لا تتردد في طرح أي أسئلة. نحن هنا للمساعدة!"
            }
        ]
    })

def get_answer(question):
    for qa in qa_data:
        if qa['Question'].lower() == question.lower():
            return qa['Answer']
    return get_answer_from_openai(question)

@socketio.on('message')
def handle_message(data):
    question = data['question']
    answer = get_answer(question)
    emit('response', {'answer': answer})

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')  

if __name__ == '__main__':
    socketio.run(app, debug=True, host='127.0.0.1', port=5000)
