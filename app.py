from flask import Flask, render_template, request, flash, redirect, url_for, session
from datetime import datetime
import sqlite3
import random
import google.generativeai as genai
import math
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

app = Flask(__name__)

genai.configure(api_key="AIzaSyDiV_fvHcrlQZ1MswI0MjT9WRcSwGlhwNc")

defaults = {
    'model': 'models/text-bison-001',
    'temperature': 0.7,
    'candidate_count': 1,
    'top_k': 40,
    'top_p': 0.95,
    'max_output_tokens': 1024,
    'stop_sequences': [],
    'safety_settings': [
        {"category": "HARM_CATEGORY_DEROGATORY", "threshold": 1},
        {"category": "HARM_CATEGORY_TOXICITY", "threshold": 1},
        {"category": "HARM_CATEGORY_VIOLENCE", "threshold": 2},
        {"category": "HARM_CATEGORY_SEXUAL", "threshold": 2},
        {"category": "HARM_CATEGORY_MEDICAL", "threshold": 2},
        {"category": "HARM_CATEGORY_DANGEROUS", "threshold": 2},
    ],
}

random_questions = []
random_answers = []
app.secret_key = "123"
num_Random = 1


def init_db():
    with sqlite3.connect("database.db") as con:
        con.execute(
            "CREATE TABLE if not exists users (id INTEGER PRIMARY KEY AUTOINCREMENT,name VARCHAR(255),role VARCHAR(100),password VARCHAR(255))")
        con.execute(
            "CREATE TABLE if not exists exams(id INTEGER PRIMARY KEY AUTOINCREMENT,exam_name VARCHAR(255),doctor_id INTEGER,FOREIGN KEY (doctor_id) REFERENCES users(id))")
        con.execute(
            "CREATE TABLE if not exists questions (id INTEGER PRIMARY KEY AUTOINCREMENT,exam_id INTEGER,question_content TEXT,answer TEXT,FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE)")
        con.execute(
            "CREATE TABLE if not exists degree (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,exam_id INTEGER,degree FLOAT,FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE)")
        # You don't need con.close() since 'with' takes care of it



@app.route('/')
def index():
    return render_template('login.html',bg_class='classy' )


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        name = request.form['username']
        password = request.form['password']  # In production, ensure this is hashed!
        con = sqlite3.connect("database.db")
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE name=? AND password=?", (name, password))

        data = cur.fetchone()

        print("Query Result:", data)

        if data:
            session["user_id"] = data["id"]
            session["name"] = data["name"]
            session["role"] = data["role"]

            if data["role"].lower() == 'student':
                return redirect(url_for("student"))
            elif data["role"].lower() == 'doctor':
                return redirect(url_for("doctor_dashboard"))
            else:
                flash("Unauthorized role", "danger")
                return redirect(url_for("index"))
        else:
            flash("Username and Password mismatch", "danger")

    return redirect(url_for("index"))


@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'role' in session and session['role'].lower() == 'doctor':
        return render_template('doctor_dashboard.html', bg_class='classy')
    else:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('index'))




@app.route('/student')
def student():
    training_inputs = []
    training_outputs = []
    global random_questions
    global random_answers
    if 'user_id' in session:
        user_id = session['user_id']
        try:
            con = sqlite3.connect("database.db")
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            now = datetime.now()
            formatted_now = now.strftime('%Y-%m-%dT%H:%M:%S')
            print(user_id)
            # Query to check exams already taken by the student
            cur.execute("SELECT exam_id FROM degree WHERE user_id=?", (user_id,))
            exams_taken = cur.fetchall()
            print("exams_taken")
            print(exams_taken)
            exams_taken_ids = [exam['exam_id'] for exam in exams_taken]
            print(exams_taken_ids)
            # Query to get the exams that are currently available and not taken by the student
            cur.execute("""
                SELECT * FROM exams 
                WHERE start_time <= ? AND end_time >= ? 
                AND id NOT IN (SELECT exam_id FROM degree WHERE user_id=?) 
                ORDER BY start_time
                """, (formatted_now, formatted_now, user_id))
            available_exams = cur.fetchall()
            print("available_exams")

            print(available_exams)

            if not available_exams:
                flash('No currently available exams or all exams have been taken.', 'info')
                return render_template('index.html', questions=[], exams=[] ,bg_class='classy')

            exam_id = available_exams[0]['id']

            # Get the questions related to the first available exam
            cur.execute("SELECT * FROM questions WHERE exam_id=?", (exam_id,))
            questions = cur.fetchall()
            print("questions")

            print(questions)

            if not questions:
                flash('No questions found for the selected exam.', 'info')
                return render_template('index.html', questions=[], exams=available_exams,bg_class='classy')

            # Convert questions to the format expected by the template
            formatted_questions = {q['question_content']: q['answer'] for q in questions}
            training_inputs = [q['question_content']for q in questions]
            training_outputs =[q['answer'] for q in questions]
            print("training_inputs")
            print(training_inputs)
            print("training_outputs")
            print(training_outputs)

            # Number of random items you want
            num_random_items = num_Random

            # Generate random indices for questions and answers
            random_indices = random.sample(range(len(training_inputs)), num_random_items)

            # Create new lists with random questions and answers
            random_questions = [training_inputs[i] for i in random_indices]
            random_answers = [training_outputs[i] for i in random_indices]

            print("random_questions")
            print(random_questions)
            print("random_answers")
            print(random_answers)




            return render_template('index.html', questions=random_questions, exam_id=exam_id ,bg_class='classy')

        except sqlite3.Error as e:
            flash(f'A database error occurred: {e}', 'danger')
        finally:
            con.close()
    else:
        flash('Please log in to view available exams.', 'danger')
        return redirect(url_for('login'))

    return render_template('index.html', questions=[], exams=[] ,bg_class='classy')


# ... Rest of your code ...


@app.route('/doctor')
def doctor():
    return render_template('add.html',bg_class='classy')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form['username']
            role = 'student'
            password = request.form['password']
            con = sqlite3.connect("database.db")
            cur = con.cursor()
            cur.execute("insert into users(name,role,password)values(?,?,?)", (name, role, password))
            con.commit()
            flash("user Added  Successfully", "success")
        except:
            flash("Error in Insert Operation", "danger")
        finally:
            return redirect(url_for("index"))
            con.close()

    return render_template('register.html' ,bg_class='classy')


@app.route('/add')
def add():
    return render_template('add.html',bg_class='classy')




@app.route('/store', methods=['POST'])
def store():
    global num_Random
    # Initialize lists outside the function scope
    train_outputs = []
    train_inputs = []
    num_examples = int(request.form['num_qa'])
    num_Random = int(request.form['ran_qa'])


    try:
        con = sqlite3.connect("database.db")
        cur = con.cursor()

        exam_name = request.form['exam_name']
        doctor_id = session.get('user_id')
        start_time = request.form['start_time']
        End_time = request.form['End_time']

        print(f"Received from form: Exam Name - {exam_name}, Doctor ID - {doctor_id}, Start Time - {start_time}")

        cur.execute("INSERT INTO exams(exam_name, doctor_id, start_time, End_time) VALUES(?, ?, ?, ?)",
                    (exam_name, doctor_id, start_time, End_time))
        exam_id = cur.lastrowid
        print(f"New exam inserted with id: {exam_id}")

        i = 1
        while True:
            question_key = f'question_{i}'
            answer_key = f'answer_{i}'
            question = request.form.get(question_key)
            answer = request.form.get(answer_key)
            if question is not None and answer is not None:
                train_inputs.append(request.form.get(question_key))
                train_outputs.append(request.form.get(answer_key))


            if not question or not answer:
                break

            i += 1

        for q, a in zip(train_inputs, train_outputs):
            cur.execute("INSERT INTO questions(exam_id, question_content, answer) VALUES(?, ?, ?)",
                        (exam_id, q, a))


        con.commit()
        flash("Exam and questions added successfully!", "success")

    except Exception as e:
        if con:
            con.rollback()
            flash("An error occurred while saving the exam: " + str(e), "danger")
            print("Exception caught: ", e)  # Print the exception to the console


    finally:
        if con :
            con.close()
            print("Database connection closed")

    return redirect(url_for('doctor_dashboard'))


@app.route('/compare/<int:exam_id>', methods=['POST'])
def compare(exam_id):
    user_id = session.get('user_id')  # Retrieve user ID from session

    if not user_id:
        # It should never happen as the user is logged in at this point, but just in case
        flash("User is not logged in.", "danger")
        return redirect(url_for('login'))

    con = sqlite3.connect("database.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("SELECT id, question_content, answer FROM questions WHERE exam_id=?", (exam_id,))
    correct_answers_data = cur.fetchall()

    results = []
    correct_count = 0
    i = 1
    for ran in random_questions:
        for row in correct_answers_data:
            if row['question_content'] == ran:
                question_id = row['id']
                correct_answer = row['answer']
                print(f"question_id: {question_id}")
                print(f"correct_answer: {correct_answer}")
                user_answer = request.form.get(f'answer{i}', '').strip()
                i += 1
                print(f"user_answer: {user_answer}")

                cur.execute(
                    "INSERT INTO answers (student_id, answer_content, question_id, exam_id) VALUES (?, ?, ?, ?)",
                    (user_id, user_answer, question_id, exam_id))
                print(f"User answer for question {question_id}: {user_answer}")

                # Calculate the score for this answer
                # similarity_score = int(user_answer == correct_answer)
                # correct_count += similarity_score
                prompt = f"Does the phrase '{user_answer}' describe the meaning of '{correct_answer}'?"

                response = genai.generate_text(**defaults, prompt=prompt)
                similarity_score = 0  # Default score if no similarity indication is found

                if response.result:
                    similarity_text = response.result.lower()
                    if 'yes' in similarity_text:
                        similarity_score = 1
                    elif 'no' in similarity_text:
                        similarity_score = 0
                else:
                    similarity_score = 0  # Assign 0 score if no answer was provided

                correct_count += similarity_score

                # Store the student's answer in the database

                # Append comparison result to the list
                results.append((row['question_content'], user_answer, correct_answer, similarity_score))
    print(num_Random)

    degree = math.ceil((correct_count / len(random_questions)) * 100) if correct_answers_data else 0


    # Commit answers to the database and handle errors
    try:
        # Now, let's save the degree to the 'degree' table
        cur.execute("INSERT INTO degree (user_id, exam_id, degree) VALUES (?, ?, ?)", (user_id, exam_id, degree))
        con.commit()
    except sqlite3.Error as e:
        con.rollback()
        flash(f"An error occurred while saving the exam results: {e}", 'danger')
    finally:
        con.close()

    return render_template('results.html', results=results, total_score=degree,bg_class='classy')


@app.route('/logout', methods=['POST'])
def logout():
    # Your logout logic here
    session.clear()
    return redirect(url_for("index"))

@app.route('/show_results', methods=['get'])
def show_results():
    try:
        con = sqlite3.connect("database.db")
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # Replace this query with your actual query to fetch exam results
        cur.execute("""
            SELECT exams.id , exams.exam_name as exam, users.name as student, degree.degree 
            FROM degree , exams ,users 
	        WHERE degree.user_id = users.id
		    AND exams.id = degree.exam_id
            ORDER BY exam_id
        """)

        all_results = cur.fetchall()

        if not all_results:
            flash('No exam results found.', 'info')
            return redirect(url_for('doctor_dashboard'))

    except sqlite3.Error as e:
        flash(f'A database error occurred: {e}', 'danger')
    finally:
        con.close()

    return render_template('show_results.html', all_results=all_results,bg_class='classy')

@app.route('/generate_report', methods=['GET'])
def generate_report():
    if 'role' in session and session['role'].lower() == 'doctor':
        try:
            con = sqlite3.connect("database.db")
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            cur.execute("""
                SELECT exams.id , exams.exam_name as exam, users.name as student, degree.degree 
                FROM degree , exams ,users 
                WHERE degree.user_id = users.id
                AND exams.id = degree.exam_id
                ORDER BY exam_id 
            """)

            exam_results = cur.fetchall()

            if not exam_results:
                flash('No exam results found.', 'info')
                return redirect(url_for('doctor_dashboard'))

            # Generate PDF report
            pdf_filename = 'exam_results_report.pdf'
            pdf_path = f'D:/IS_L4/First Term/Enterprise Architecture/Section/Project/exam_pro/reports/{pdf_filename}'

            # Data for each page
            data_per_page = 9  # Number of rows per page
            total_records = len(exam_results)
            total_pages = (total_records // data_per_page) + 1 if (total_records % data_per_page) != 0 else (
                        total_records // data_per_page)

            buffer = BytesIO()
            pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
            pdf_canvas.setFont("Helvetica", 13)

            y_position = 750  # Initial Y position for drawing content

            for page_number in range(total_pages):
                pdf_canvas.drawString(100, y_position, 'Exam Results Report')
                pdf_canvas.drawString(100, y_position - 20, 'Generated on: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                pdf_canvas.drawString(100, y_position - 40, '-' * 80)

                # Table headers
                pdf_canvas.drawString(100, y_position - 53, '#')
                pdf_canvas.drawString(170, y_position - 53, 'Exam')
                pdf_canvas.drawString(300, y_position - 53, 'Student')
                pdf_canvas.drawString(400, y_position - 53, 'Score')

                # Exam results content
                for i in range(data_per_page * page_number, min(data_per_page * (page_number + 1), total_records)):
                    result = exam_results[i]
                    exam_id = result['id']
                    exam = result['exam']
                    student_name = result['student']
                    degree = result['degree']

                    # Draw table content
                    y_position -= 72
                    pdf_canvas.drawString(100, y_position, str(exam_id))
                    pdf_canvas.drawString(170, y_position, exam)
                    pdf_canvas.drawString(300, y_position, student_name)
                    pdf_canvas.drawString(400, y_position, str(degree))

                if page_number < (total_pages - 1):
                    y_position = 750  # Reset Y position for the next page
                    pdf_canvas.showPage()  # Move to the next page

            pdf_canvas.save()

            # Move the buffer position to the beginning
            buffer.seek(0)

            # Save the PDF to a file
            with open(pdf_path, 'wb') as pdf_file:
                pdf_file.write(buffer.read())

            flash(f'PDF report generated successfully. You can download it [here]({pdf_path}).', 'success')

        except sqlite3.Error as e:
            flash(f'A database error occurred: {e}', 'danger')
        finally:
            con.close()

    else:
        flash('Unauthorized access.', 'danger')

    return redirect(url_for('doctor_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
