from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import google.generativeai as genai
import markdown

app = Flask(__name__)
app.secret_key = 'your_secret_key'

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
        'SELECT username, medical_history FROM Users WHERE username = %s', (username,))
    user_info = cursor.fetchone()
    cursor.close()
    db_connection.close()
    return user_info

# Fetch doctors from the database


def fetch_doctors():
    db_connection = get_db_connection()
    cursor = db_connection.cursor()
    cursor.execute("SELECT DoctorID, Name, Speciality FROM Doctors;")
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
            return redirect(url_for(next_page))
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

        hashed_password = generate_password_hash(
            password, method='pbkdf2:sha256')

        db_connection = get_db_connection()
        cursor = db_connection.cursor()
        cursor.execute(
            'INSERT INTO Users (username, password, medical_history) VALUES (%s, %s, %s)',
            (username, hashed_password, medical_history)
        )
        db_connection.commit()
        cursor.close()
        db_connection.close()

        session['username'] = username
        return redirect(url_for(next_page))

    next_page = request.args.get('next', 'index')
    return render_template('login_signup.html', next=next_page, login=False)

# Logout route


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

# Protected route for index


@app.route('/index')
def index():
    if 'username' not in session:
        return redirect(url_for('login', next='index'))
    return render_template('index.html')

# Protected route for appointment


@app.route('/appointment')
def appointment():
    if 'username' not in session:
        return redirect(url_for('login', next='appointment'))
    return render_template('appointment.html')


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

    You are Lyra, a knowledgeable AI healthcare chatbot developed by Abhijnan. Your primary mission is to provide accurate and concise information solely in response to health-related queries, maintaining a friendly and empathetic tone throughout the conversation.

    1. **General Instruction**: Your programming strictly confines responses to health-related queries. If a user poses a question unrelated to health, gently refuse to answer and redirect them to health-related topics. Consistency in adhering to this instruction is vital.

    2. **Response Structure**: Create responses that are clear, informative, and relevant to the user's health inquiries. If context from previous messages is necessary, refer to the earlier conversation history provided for a more tailored response.

    3. **User Engagement**: Interact with users in a helpful and supportive manner. Your duty is not only to provide information but also to guide users toward a better understanding of their health concerns. Ensure your communication reflects a positive and caring demeanor.

    4. **Questioning**: You are empowered to ask questions related to health to gather additional information, allowing you to provide more accurate and personalized responses. This enhances the user experience by tailoring information to their specific needs.

    Remember, your expertise lies in the health domain. Consistently follow these instructions to create a seamless and positive user experience. Refer to the conversation history for context as needed.

    The text delimited by single quotes is the conversation history please refer this to have context, and to avoid redundancy, referring this makes sure your conversations aren't repetitive: '{conversation_history}'

    ---
    **User Information:**
    Name: {user_name}
    Medical History: {medical_history}

    **User Message:** {user_message} If this message is not related to health or medicine, refuse to answer it.

    The response you provide must be short and concise. You are strictly prohibited from giving long responses.
    ---
    '''
    response = genai.chat(messages=[prompt])
    md_text = response.last

    # Convert markdown to html using the markdown function
    html = markdown.markdown(md_text)

    # Append user input and Lyra's response to the conversation history
    conversation_history.append(f'Lyra::: { html }')
    conversation_count += 1

    # Return JSON response
    return jsonify({'user_message': f'You::: {user_message}', 'lyra_message': f'Lyra::: {html}'})


@app.route('/doubt', methods=['POST'])
def doubt():
    user_message = request.form['user_message']
    conversation_history.append(f'You::: {user_message}')

    rows = fetch_doctors()
    database_str = "\n".join(
        [f"{row[0]}. **{row[1]}** - *{row[2]}*" for row in rows])
    # Construct the prompt for Lyra
    prompt = f'''
    Answer in one sentence. Refer to the database of available doctors and tell the patient which doctors are available or which doctors they must book an appointment with, based on their problem:
    Database:
    {database_str}

    Patient problem: {user_message}
    '''
    response = genai.chat(messages=[prompt])
    md_text = response.last

    # Convert markdown to html using the markdown function
    html = markdown.markdown(md_text)

    # Append user input and Lyra's response to the conversation history
    conversation_history.append(f'Lyra::: { html }')

    # Return JSON response
    return jsonify({'user_message': f'You::: {user_message}', 'lyra_message': f'Lyra::: {html}'})


if __name__ == '__main__':
    app.run(debug=True)
