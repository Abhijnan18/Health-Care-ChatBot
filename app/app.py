from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import mysql.connector
import google.generativeai as genai
import markdown
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Directory to save medical history files
MEDICAL_HISTORY_DIR = 'medical_histories'
os.makedirs(MEDICAL_HISTORY_DIR, exist_ok=True)

# Database connection


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="189@2003ihba",
        database="Doc",
        auth_plugin='mysql_native_password'
    )

# Fetch user information from the database


def fetch_user_info(username):
    db_connection = get_db_connection()
    cursor = db_connection.cursor()
    cursor.execute(
        'SELECT username, medical_history_path FROM Users WHERE username = %s', (username,))
    user_info = cursor.fetchone()
    cursor.close()
    db_connection.close()

    if user_info:
        username, medical_history_path = user_info
        if os.path.exists(medical_history_path):
            with open(medical_history_path, 'r') as file:
                medical_history = file.read()
        else:
            medical_history = "No medical history available."
        return username, medical_history
    return None

# Fetch doctors from the database


def fetch_doctors():
    db_connection = get_db_connection()
    cursor = db_connection.cursor()
    cursor.execute("SELECT Speciality FROM Doctors;")
    rows = cursor.fetchall()
    cursor.close()
    db_connection.close()
    return rows


# Set up the API key for the generative model
genai.configure(api_key='AIzaSyCc_Mo21um64S5RnouVKUT7MLKfpUfjNZk')
conversation_history = []
message_limit = 50
conversation_count = 0


@app.route('/')
def loading():
    return render_template('loading_page.html')


@app.route('/home')
def home():
    if 'username' in session:
        return redirect(url_for('index'))
    return render_template('home.html')

# Login route


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        next_page = request.form['next']

        db_connection = get_db_connection()
        cursor = db_connection.cursor()
        cursor.execute(
            'SELECT password FROM Users WHERE username = %s', (username,))
        user = cursor.fetchone()
        cursor.close()
        db_connection.close()

        if user and check_password_hash(user[0], password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login', next=next_page))

    next_page = request.args.get('next', 'index')
    return render_template('login_signup.html', next=next_page, login=True)

# Sign-up route


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'username' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        medical_history = request.form['medical_history']
        next_page = request.form['next']

        # Check if the username already exists
        db_connection = get_db_connection()
        cursor = db_connection.cursor()
        cursor.execute(
            'SELECT username FROM Users WHERE username = %s', (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Username already exists. Please choose a different username or login.')
            cursor.close()
            db_connection.close()
            return redirect(url_for('signup', next=next_page))

        hashed_password = generate_password_hash(
            password, method='pbkdf2:sha256')

        # Save medical history to a file
        filename = secure_filename(f"{username}_medical_history.txt")
        filepath = os.path.join(MEDICAL_HISTORY_DIR, filename)
        with open(filepath, 'w') as file:
            file.write(medical_history)

        cursor.execute('INSERT INTO Users (username, password, medical_history_path) VALUES (%s, %s, %s)',
                       (username, hashed_password, filepath))
        db_connection.commit()
        cursor.close()
        db_connection.close()

        session['username'] = username
        return redirect(url_for('index'))

    next_page = request.args.get('next', 'index')
    return render_template('login_signup.html', next=next_page, login=False)

# Logout route


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

# Index route


@app.route('/index')
def index():
    if 'username' not in session:
        return redirect(url_for('login', next='index'))
    return render_template('index.html')

# Protected route for chatbot


@app.route('/chatbot')
def chatbot():
    if 'username' not in session:
        return redirect(url_for('login', next='chatbot'))
    return render_template('chatbot.html')

# Protected route for symptom_checker


@app.route('/symptom_checker')
def symptom_checker():
    if 'username' not in session:
        return redirect(url_for('login', next='symptom_checker'))
    return render_template('symptom_checker.html')


@app.route('/ask', methods=['POST'])
def ask():
    global conversation_count

    user_message = request.form['user_message']
    username = session.get('username')

    if username:
        user_info = fetch_user_info(username)
        if user_info:
            user_name = user_info[0]
            medical_history = user_info[1]
        else:
            user_name = "User"
            medical_history = "No medical history available."
    else:
        user_name = "User"
        medical_history = "No medical history available."

    conversation_history.append(f'You::: {user_message}')

    # Construct the prompt for Lyra
    prompt = f'''
    **Prompt:**

    You are Lyra, a knowledgeable AI healthcare chatbot who acts like a Medical professional. You are free to provide diet and exercise tips. You were developed by Abhijnan. Your primary mission is to provide accurate and concise information solely in response to health-related queries.

    1. **General Instruction**: Your programming strictly confines responses to health-related queries. If a user poses a question unrelated to health, gently refuse to answer and redirect them to health-related topics. Consistency in adhering to this instruction is vital.

    2. **Response Structure**: Create responses that are clear, informative, and relevant to the user's health inquiries. Always refer to the user's medical history provided to give personalized and accurate answers. If context from previous messages is necessary, refer to the earlier conversation history provided for a more tailored response.

    Remember, your expertise lies in the health domain. Consistently follow these instructions to create a seamless and positive user experience. Refer to the conversation history and the user's medical history for context as needed.

    ---
    **User Information:**
    Medical Record: {medical_history}

    **User Message:** {user_message} If this message is not related to health or medicine, refuse to answer it.

    The response you provide must be short and concise. You are strictly prohibited from giving long responses. Refrain from greeting the user every time.
    ---
    This is the chat history for you to maintain context: {conversation_history}
    '''

    response = genai.chat(messages=[prompt])
    md_text = response.last

    # Convert markdown to html using the markdown function
    html = markdown.markdown(md_text)

    # Append user input and Lyra's response to the conversation history
    conversation_history.append(f'Lyra::: {html}')
    conversation_count += 1

    # Return JSON response
    return jsonify({'user_message': f'You::: {user_message}', 'lyra_message': f'Lyra::: {html}'})


@app.route('/doubt', methods=['POST'])
def doubt():
    user_message = request.form['user_message']
    conversation_history.append(f'You::: {user_message}')

    rows = fetch_doctors()
    database_str = "\n".join([f"{row[0]}" for row in rows])
    # Construct the prompt for Lyra
    prompt = f'''
    Respond in one sentence. Based on the user's described problem, identify the possible condition/disease, recommend a medical professional of the suitable speciality from the list below.
    Speciality of Medical Professional List:
    {database_str}
    
    You are strictly prohibited from providing long responses. Your responses must only be in a sentence.
    User's Problem: {user_message}
    '''

    response = genai.chat(messages=[prompt])
    md_text = response.last

    # Convert markdown to html using the markdown function
    html = markdown.markdown(md_text)

    # Append user input and Lyra's response to the conversation history
    conversation_history.append(f'Lyra::: {html}')

    # Return JSON response
    return jsonify({'user_message': f'You::: {user_message}', 'lyra_message': f'Lyra::: {html}'})


if __name__ == '__main__':
    app.run(debug=True)
