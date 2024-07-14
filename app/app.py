# Flask app
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from IPython.display import Markdown
import markdown
import mysql.connector


app = Flask(__name__)


def fetch_doctors():
    # Establish connection to the database
    db_connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="189@2003ihba",
        database="Doc",
        auth_plugin='mysql_native_password'
    )

    # Create a cursor object to execute queries
    cursor = db_connection.cursor()

    # Define the SQL query
    sql_query = "SELECT DoctorID, Name, Speciality FROM Doctors;"

    # Execute the query
    cursor.execute(sql_query)

    # Fetch all rows
    rows = cursor.fetchall()

    # Close cursor and database connection
    cursor.close()
    db_connection.close()

    return rows


# Set up the API key
genai.configure(api_key='AIzaSyCc_Mo21um64S5RnouVKUT7MLKfpUfjNZk')
conversation_history = []
message_limit = 50
conversation_count = 0


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/appointment')
def index2():
    return render_template('appointment.html')


@app.route('/ask', methods=['POST'])
def ask():
    global conversation_count

    user_message = request.form['user_message']
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

    This is the current user message you are supposed to reply by referring to the conversation history if needed.

    ---
    **User Message:** {user_message+" If this message is not related to health or medicince refuse to answer it."}

    The response you provide must be short and concise, You are sticly prohibited from giving long responses.
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
    GOOGLE_API_KEY = 'AIzaSyCc_Mo21um64S5RnouVKUT7MLKfpUfjNZk'
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-pro')

    user_message = request.form['user_message']
    conversation_history.append(f'You::: {user_message}')

    rows = fetch_doctors()
    database_str = "\n".join(
        [f"{row[0]}. **{row[1]}** - *{row[2]}*" for row in rows])
    # Construct the prompt for Lyra
    response = model.generate_content(f'''
    Answer in One sentence,Refer the database of doctors availabel and tell the patient which Doctors are available or which Doctors they must book an appointment with, based on theor problem:
    Database:
    {database_str}

    Patient problem: {user_message}
    ''')

    md_text = response.text

    # Convert markdown to html using the markdown function
    html = markdown.markdown(md_text)

    # Append user input and Lyra's response to the conversation history
    conversation_history.append(f'Lyra::: { html }')

    # Return JSON response
    return jsonify({'user_message': f'You::: {user_message}', 'lyra_message': f'Lyra::: {html}'})


if __name__ == '__main__':
    app.run(debug=True)
