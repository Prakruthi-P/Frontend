import openai
from flask import Flask, request, send_file,jsonify, render_template, make_response,url_for,redirect
from pymongo import MongoClient
from bson import ObjectId
from io import BytesIO
from PyPDF2 import PdfReader
import spacy
from flask_mail import Mail, Message
from bs4 import BeautifulSoup
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64


app = Flask(__name__)
app.config['MAIL_SERVER'] = '64.233.184.108'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'prakprag123@gmail.com'  # Your Gmail email address
app.config['MAIL_PASSWORD'] = 'yktj vvvg cxxp qmxa'  
app.config['MAIL_DEFAULT_SENDER'] = ('Prakruthi P', 'prakprag123@gmail.com')


mail = Mail(app)

# MongoDB setup
client = MongoClient('mongodb://localhost:27017/')
db = client['hrabc']  # Change 'candidate_database' to your desired database name
candidates_collection = db['candidates']
recruiters_collection = db['recruiters']
openai.api_key = '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'

nlp = spacy.load("en_core_web_sm")
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Verify user against recruiters collection
        user = recruiters_collection.find_one({"username": username, "password": password})

        if user:
            # Login successful, redirect to the index page
            return render_template('index.html')
        else:
            # Login failed, display an error message
            return render_template('login.html', error='Invalid credentials')

    return render_template('login.html')
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Check if the passwords match
        if password != confirm_password:
            return render_template('signup.html', error='Passwords do not match')

        # Check if the username is already taken
        existing_user = recruiters_collection.find_one({"username": username})
        if existing_user:
            return render_template('signup.html', error='Username already taken')

        # Create a new user in the recruiters collection
        recruiters_collection.insert_one({"username": username, "password": password})

        # Redirect to the login page after successful signup
        return render_template('login.html')

    return render_template('signup.html')

@app.route('/index')
def index():
    # Get the search keyword from the query parameters
    search_keyword = request.args.get('search', '')

    # Perform a search query in MongoDB
    if search_keyword:
        # If there is a search keyword, perform a search in 'file_content' and 'name' fields
        candidates_cursor = candidates_collection.find({
            '$or': [
                {'file_content': {'$regex': search_keyword, '$options': 'i'}},
                {'name': {'$regex': search_keyword, '$options': 'i'}}
            ]
        })
    else:
        # If there is no search keyword, retrieve all candidates
        candidates_cursor = candidates_collection.find()

    # Render the template with the candidates and search keyword
    return render_template('index.html', candidates=candidates_cursor, search_keyword=search_keyword)


@app.route('/candidate/<candidate_id>')
def candidate_details(candidate_id):
    # Assuming candidates_collection is your MongoDB collection
    candidate = candidates_collection.find_one({'_id': ObjectId(candidate_id)})

    if candidate:
        return render_template('candidate_details.html', candidate=candidate)
    else:
        # Handle the case where the candidate with the given ID is not found
        return render_template('candidate_not_found.html')


@app.route('/addcandidate')
def page1():
    return render_template('page1.html')


@app.route('/removecandidate')
def page2():
    return render_template('page2.html')

def extract_education(response_text):
    response_text_lower = response_text.lower()
    education_start = response_text_lower.find("education:") + len("education:")
    education_end = response_text_lower.find("skills:")
    education_section = response_text[education_start:education_end].strip()
    education_lines = [line.strip() for line in education_section.split('\n') if line.strip()]
    return education_lines


def extract_skills(response_text):
    skills_start = response_text.lower().find("skills:") + len("skills:")
    skills_end = response_text.lower().find("location:")
    skills_section = response_text[skills_start:skills_end].strip()
    skills_lines = [line.strip() for line in skills_section.split('\n') if line.strip()]
    return skills_lines

def extract_location(response_text):
    location_start = response_text.lower().find("location:") + len("location:")
    location_end = response_text.lower().find("experience:")
    location_section = response_text[location_start:location_end].strip()
    location_lines = [line.strip() for line in location_section.split('\n') if line.strip()]
    return location_lines

def extract_experience(response_text):
    experience_start = response_text.lower().find("experience:") + len("experience:")
    experience_end = response_text.lower().find("contact:")
    experience_section = response_text[experience_start:experience_end].strip()
    experience_lines = [line.strip() for line in experience_section.split('\n') if line.strip()]
    return experience_lines

def extract_contact(response_text):
    contact_start = response_text.lower().find("contact:") + len("contact:")
    contact_end = response_text.lower().find("certification:")
    contact_section = response_text[contact_start:contact_end].strip()
    contact_lines = [line.strip() for line in contact_section.split('\n') if line.strip()]
    return contact_lines

def extract_certification(response_text):
    certification_start = response_text.lower().find("certification:") + len("certification:")
    certification_end = len(response_text)
    certification_section = response_text[certification_start:certification_end].strip()
    certification_lines = [line.strip() for line in certification_section.split('\n') if line.strip()]
    return certification_lines


@app.route('/upload', methods=['POST'])
def upload():
    try:
        # Get form data
        name = request.form['name']
        email = request.form['email']

        # Get the uploaded file content directly from memory
        file_content = request.files['document'].read()

        # Extract text from the PDF
        pdf_text = extract_text_from_pdf(file_content)

        # Use OpenAI ChatCompletion to process the resume text
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-1106",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Parse the following resume for generating tags on Education, Skills, Location, Experience, Contact, and Certification with these as Keys and value for it in same order if its not avaliable leave it blank:\n{pdf_text}"}
            ],
            max_tokens=4096,
        )

        # Extract key information from the model's response
        parsed_resume = response['choices'][0]['message']['content']
       
        # Extract information from each section
        education_info = extract_education(parsed_resume)
        skills_info = extract_skills(parsed_resume)
        location_info = extract_location(parsed_resume)
        experience_info = extract_experience(parsed_resume)
        contact_info = extract_contact(parsed_resume)
        certification_info = extract_certification(parsed_resume)

        # Store original text, education, skills, location, experience, contact, and certification
        candidate_object = {
            "name": name,
            "email": email,
            "original_resume_text": file_content,
            "education": education_info,
            "skills": skills_info,
            "location": location_info,
            "experience": experience_info,
            "contact": contact_info,
            "certification": certification_info
        }

        candidates_collection.insert_one(candidate_object)

        return redirect(url_for('index'))
    except Exception as e:
        return f"Error: {str(e)}"


def extract_text_from_pdf(pdf_content):
    pdf_document = BytesIO(pdf_content)
    try:
        pdf_reader = PdfReader(pdf_document)
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
        return text
    except Exception as e:
        raise ValueError(f"Error extracting text from PDF: {str(e)}")

@app.route('/view_resume/<candidate_id>')
def view_resume(candidate_id):
    # Fetch candidate data from MongoDB using ObjectId
    candidate = candidates_collection.find_one({"_id": ObjectId(candidate_id)})

    if candidate:
        # Get the PDF content from the candidate data
        pdf_content = candidate.get('original_resume_text', None)

        if pdf_content:
            # Serve the PDF content
            return send_file(
                BytesIO(pdf_content),
                download_name=f"{candidate['name']}_resume.pdf",
                as_attachment=True
            )
        else:
            return "Resume PDF not found for the candidate", 404
    else:
        return "Candidate not found", 404


@app.route('/success')
def success():
    return 'Added successfully!'

@app.route('/delete-candidate/<candidate_id>', methods=['POST'])
def delete_candidate(candidate_id):
    try:
        result = candidates_collection.delete_one({'_id': ObjectId(candidate_id)})
        if result.deleted_count == 1:
            candidates = candidates_collection.find()  # Retrieve updated candidate list
            return render_template('index.html', candidates=candidates, message='Candidate deleted successfully')
        else:
            candidates = candidates_collection.find()  # Retrieve updated candidate list
            return render_template('index.html', candidates=candidates, message='Candidate not found')
    except Exception as e:
        candidates = candidates_collection.find()  # Retrieve updated candidate list
        return render_template('index.html', candidates=candidates, error=str(e)), 500

@app.route('/select-candidate/<candidate_id>', methods=['POST'])
def select_candidate(candidate_id):
    try:
        # Perform the logic to select the candidate (modify this based on your needs)
        # For example, you might update a 'selected' field in your database
        result = candidates_collection.update_one(
            {'_id': ObjectId(candidate_id)},
            {'$set': {'selected': True}}
        )

        if result.modified_count == 1:
            # Redirect to the selected candidates page after successful selection
            return redirect(url_for('index'))
        else:
            candidates = candidates_collection.find()  # Retrieve updated candidate list
            return render_template('index.html', candidates=candidates, message='Candidate not found or already selected')
    except Exception as e:
        candidates = candidates_collection.find()  # Retrieve updated candidate list
        return render_template('index.html', candidates=candidates, error=str(e)), 500



@app.route('/selected-candidates')
def selected_candidates():
    selected_candidates = candidates_collection.find({'selected': True})
    return render_template('selected_candidates.html', selected_candidates=selected_candidates)

@app.route('/deselect-candidate/<candidate_id>', methods=['POST'])
def deselect_candidate(candidate_id):
    try:
        # Perform the logic to deselect the candidate (modify this based on your needs)
        # For example, you might update a 'selected' field in your database
        result = candidates_collection.update_one(
            {'_id': ObjectId(candidate_id)},
            {'$set': {'selected': False}}
        )

        if result.modified_count == 1:
            return jsonify({'message': 'Candidate deselected successfully'}), 200
        else:
            return jsonify({'error': 'Candidate not found or already deselected'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/interviews')
def interviews():
    # Fetch only those candidates for whom the interview is scheduled
    scheduled_candidates = candidates_collection.find({'scheduled_interview': {'$exists': True}})
    return render_template('interview.html', scheduled_candidates=scheduled_candidates)
@app.route('/schedule-interview/<candidate_id>', methods=['POST'])
def schedule_interview(candidate_id):
    try:
        # Fetch candidate data from MongoDB using ObjectId
        candidate = candidates_collection.find_one({"_id": ObjectId(candidate_id)})

        if candidate:
            # Get interview details from the request
            interview_date = request.json.get('interviewDate')
            interview_time = request.json.get('interviewTime')

            # Perform the logic to schedule the interview
            candidates_collection.update_one(
                {'_id': ObjectId(candidate_id)},
                {'$set': {'scheduled_interview': {'date': interview_date, 'time': interview_time}}}
            )

            # Send interview invitation email
            send_interview_email(candidate, interview_date, interview_time)

            # Return the scheduled date and time along with the success message
            response_data = {
                'message': 'Interview scheduled successfully',
                'scheduledDate': interview_date,
                'scheduledTime': interview_time
            }

            return jsonify(response_data), 200
        else:
            # Handle the case where the candidate with the given ID is not found
            return jsonify({'error': 'Candidate not found'}), 404
    except Exception as e:
        # Log the exception for debugging
        app.logger.error(f"Error scheduling interview: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500
       

def send_interview_email(candidate, interview_date, interview_time):
    try:
        # Create the MIME object
        
        subject = "Interview Invitation"
        address="First floor ABC building ,4th block XYZ city"
        recruiter="Jhnon Albert"
        # Create the email body
        body = f"Dear {candidate['name']},\n\n"
        body += f"Thank you for your interest. We were impressed with your qualifications and experience, and we would like to invite you to interview for the position.\n\n"
        body += f"The interview will be held on {interview_date} at {interview_time} at our office located at {address}. Please arrive 15 minutes early to allow for check-in.\n\n"
        body += f"Please bring a copy of your resume and any other relevant materials.\n\n"
        body += f"We look forward to meeting you and learning more about your qualifications.\n\n"
        body += f"Sincerely,\n {recruiter}\n[Human Resource Officer]"

        # Attach the email body
        

        # Attach the calendar invitation
        '''cal_invite = create_calendar_invitation(candidate['name'], interview_date, interview_time)
        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(cal_invite.encode('utf-8'))
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', 'attachment; filename="invitation.ics"')
        msg.attach(attachment)'''
        msg = Message(subject, recipients=[candidate['email']], body=body)
        
        # Set the email subject, recipients, and sender
        msg.extra_headers = {"From": "xyz@abc.com"}

        # Convert the MIME object to a string and create a Flask-Mail Message
        

        # Send the email
        mail.send(msg)

        app.logger.info(f"Interview invitation email sent to {candidate['email']}")
    except Exception as e:
        # Log the exception for debugging
        app.logger.error(f"Error sending interview invitation email: {str(e)}")
        raise ValueError("Error sending interview invitation email")
def create_calendar_invitation(candidate_name, interview_date, interview_time):
 ics_content = f"""BEGIN:VCALENDAR
                   VERSION:2.0
                   BEGIN:VEVENT
                   SUMMARY:Interview with {candidate_name}
                   DTSTART;TZID=Your_Timezone:{interview_date}T{interview_time}
                   DTEND;TZID=Your_Timezone:{interview_date}T{interview_time}
                   LOCATION:Your Office Address
                   DESCRIPTION:Interview with {candidate_name}
                   STATUS:CONFIRMED
                   SEQUENCE:0
                   BEGIN:VALARM
                   TRIGGER:-PT15M
                   DESCRIPTION:Reminder
                   ACTION:DISPLAY
                   END:VALARM
                   END:VEVENT
                   END:VCALENDAR"""
 return ics_content
@app.route('/call-off-interview/<candidate_id>', methods=['POST'])
def call_off_interview(candidate_id):
    try:
        # Fetch candidate data from MongoDB using ObjectId
        candidate = candidates_collection.find_one({"_id": ObjectId(candidate_id)})

        if candidate:
            # Implement logic to send an email for calling off the interview
            send_call_off_email(candidate)

            # Remove the scheduled interview information
            candidates_collection.update_one(
                {'_id': ObjectId(candidate_id)},
                {'$unset': {'scheduled_interview': 1}}
            )

            return jsonify({'message': 'Interview called off successfully'}), 200
        else:
            return jsonify({'error': 'Candidate not found'}), 404
    except Exception as e:
        app.logger.error(f"Error calling off interview: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500
def send_call_off_email(candidate):
    try:
        recruiter="Jhnon Albert"
        subject = "Interview Canceled"
        body = f"Dear {candidate['name']},\n\nWe regret to inform you that your scheduled interview has been canceled.\n"
        body += "If you have any questions or concerns, please feel free to contact us.\n\nBest Regards,\nYour Company"
        msg = Message(subject, recipients=[candidate['email']], body=body)
        
        # Set the email subject, recipients, and sender
        msg.extra_headers = {"From": "xyz@abc.com"}
        mail.send(msg)

        app.logger.info(f"Interview invitation email sent to {candidate['email']}")
    except Exception as e:
        # Log the exception for debugging
        app.logger.error(f"Error sending interview invitation email: {str(e)}")
        raise ValueError("Error sending interview invitation email")   
@app.route('/reschedule-interview/<candidate_id>', methods=['POST'])
def reschedule_interview(candidate_id):
    try:
        # Fetch candidate data from MongoDB using ObjectId
        candidate = candidates_collection.find_one({"_id": ObjectId(candidate_id)})

        if candidate:
            # Get interview details from the request
            interview_date = request.json.get('newDate')
            interview_time = request.json.get('newTime')

            # Perform the logic to schedule the interview
            candidates_collection.update_one(
                {'_id': ObjectId(candidate_id)},
                {'$set': {'scheduled_interview': {'date': interview_date, 'time': interview_time}}}
            )

            # Send interview invitation email
            send_rescheduled_email(candidate, interview_date, interview_time)

            # Return the scheduled date and time along with the success message
            response_data = {
                'message': 'Interview rescheduled successfully',
                'scheduledDate': interview_date,
                'scheduledTime': interview_time
            }

            return jsonify(response_data), 200
        else:
            # Handle the case where the candidate with the given ID is not found
            return jsonify({'error': 'Candidate not found'}), 404
    except Exception as e:
        # Log the exception for debugging
        app.logger.error(f"Error scheduling interview: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500
       

def send_rescheduled_email(candidate, interview_date, interview_time):
    try:
        # Create the MIME object
        
        subject = "Rescheduled Interview Invitation"

        address="First floor ABC building ,4th block XYZ city"
        recruiter="Jhnon Albert"

        body = f"Dear {candidate['name']},\n\n"
        body += f"We apologize for any inconvenience this may cause, but we need to reschedule your interview .\n\n"
        body += f"The interview will now be held on {interview_date} at {interview_time} at our office located at {address}. Please arrive 15 minutes early to allow for check-in.\n\n"
        body += f"Please bring a copy of your resume and any other relevant materials.\n\n"
        body += f"We look forward to meeting you and learning more about your qualifications.\n\n"
        body += f"Sincerely,\n {recruiter}\n[Human Resource Officer]"
        msg = Message(subject, recipients=[candidate['email']], body=body)
        
        # Set the email subject, recipients, and sender
        msg.extra_headers = {"From": "xyz@abc.com"}

        # Convert the MIME object to a string and create a Flask-Mail Message
        

        # Send the email
        mail.send(msg)

        app.logger.info(f"Interview invitation email sent to {candidate['email']}")
    except Exception as e:
        # Log the exception for debugging
        app.logger.error(f"Error sending interview invitation email: {str(e)}")
        raise ValueError("Error sending interview invitation email")

if __name__ == '__main__':
    app.run(port=3000, debug=True)