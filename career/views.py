from django.shortcuts import render
from .forms import ResumeUploadForm, FeedbackForm
from django.http import JsonResponse
import pandas as pd
import json
import os
from django.conf import settings
from io import StringIO
import tempfile
from pdfminer.high_level import extract_text
import re
from sentence_transformers import SentenceTransformer, util
import requests
import PyPDF2
import uuid
from googlesearch import search

# --- NEW IMPORTS FOR THE QA MODEL ---
from transformers import pipeline, AutoTokenizer, AutoModelForQuestionAnswering
import torch

# --- QA MODEL LOADING ---
QA_MODEL_PATH = os.path.join(settings.BASE_DIR, '/Users/yashi/Desktop/career_consulting/career_consulting/career/qa_model' )
qa_pipeline = None
try:
    if os.path.exists(QA_MODEL_PATH):
        print("--- Loading fine-tuned QA model... ---")
        tokenizer = AutoTokenizer.from_pretrained(QA_MODEL_PATH)
        model = AutoModelForQuestionAnswering.from_pretrained(QA_MODEL_PATH)
        qa_pipeline = pipeline("question-answering", model=model, tokenizer=tokenizer)
        print("--- Fine-tuned QA model loaded successfully. ---")
    else:
        # This warning will now correctly appear in the runserver output
        print(f"--- QA MODEL WARNING: The directory '{QA_MODEL_PATH}' was not found. The QA feature will not work. ---")
except Exception as e:
    print(f"--- An error occurred loading the QA model: {e} ---")
    qa_pipeline = None


# --- CHATBOT DATA LOADING ---
df_sorted = None
try:
    # --- FIX: Corrected and simplified path construction ---
    csv_path = os.path.join(settings.BASE_DIR, '/Users/yashi/Desktop/career_consulting/career_consulting/career/skill_analysis/resume_skill_role_analysis.csv')
    if not os.path.exists(csv_path):
        print(f"--- CHATBOT WARNING: The file '{csv_path}' was not found. Chatbot will not work. ---")
        df_sorted = pd.DataFrame()
    else:
        df = pd.read_csv(csv_path)
        if "Similarity Score" not in df.columns:
            print(f"--- CHATBOT WARNING: 'Similarity Score' column not found in {csv_path}. Chatbot will not work. ---")
            df_sorted = pd.DataFrame()
        else:
            df_sorted = df.sort_values(by="Similarity Score", ascending=False).reset_index(drop=True)
            print("--- Chatbot CSV data loaded successfully. ---")
except Exception as e:
    print(f"--- An error occurred loading chatbot CSV data: {e} ---")
    df_sorted = pd.DataFrame()


# --- SKILL ANALYSIS CODE ---
TECHNICAL_SKILLS_LIST = "python,java,c++,javascript,sql,html,css,ruby,php,swift,kotlin,go,rust,typescript".split(',')
SOFT_SKILLS_LIST = "communication,leadership,teamwork,problem solving,time management,adaptability,creativity,critical thinking,emotional intelligence,negotiation".split(',')

def load_skill_data():
    # --- FIX: Corrected path construction. ---
    data_dir = os.path.join(settings.BASE_DIR, '/Users/yashi/Desktop/career_consulting/career_consulting/career/skill_analysis')
    
    # Check if the directory exists before proceeding
    if not os.path.isdir(data_dir):
        # Raise an error that is easier to understand
        raise FileNotFoundError(f"The skill analysis data directory was not found at '{data_dir}'. Please ensure it exists and contains the required JSON files.")

    with open(os.path.join(data_dir, 'label_role.json')) as f:
        label_role = json.load(f)
    with open(os.path.join(data_dir, 'skills.json')) as f:
        skills_dict = json.load(f)
    
    all_skills = set(skill for skills in skills_dict.values() for skill in skills)
    return label_role, skills_dict, all_skills

# This block now has better error handling if files are missing
try:
    label_role, skills_dict, all_skills = load_skill_data()
    roles = list(label_role.keys())
    st_model = SentenceTransformer("all-MiniLM-L6-v2")
    role_embeddings = st_model.encode(roles, convert_to_tensor=True)
except FileNotFoundError as e:
    # If the files don't exist, we can't run the server. Print a clear error.
    print("\n" + "="*80)
    print(f"FATAL ERROR: {e}")
    print("The server cannot start without the skill analysis data files.")
    print("="*80 + "\n")
    # To prevent a crash on import, we set these to empty values.
    label_role, skills_dict, all_skills, roles, st_model, role_embeddings = {}, {}, set(), [], None, None


def home(request):
    return render(request, 'home.html')

# --- RESUME PARSER LOGIC (UNCHANGED) ---
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Error extracting text with PyPDF2: {e}")
        return None

def parse_resume_with_gemini(resume_text, api_key):
    if not resume_text:
        return {"error": "No resume text provided for parsing."}
    prompt = f"""
    You are a highly accurate resume parsing AI. From the following resume text, extract the 'skills', 'job_title', and 'experience'.
    'skills' should be a list of key technical and soft skills. 'job_title' should be the most recent or prominent job title.
    'experience' should be a concise summary of the work experience section. Provide the output in a JSON format.
    Resume Text: --- {resume_text} ---
    """
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
    try:
        response = requests.post(api_url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        if result.get("candidates") and result["candidates"][0].get("content", {}).get("parts"):
            json_string = result["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(json_string)
        else:
            return {"error": "Unexpected API response structure from Gemini."}
    except requests.exceptions.RequestException as e:
        return {"error": f"API call failed: {e}"}
    except json.JSONDecodeError:
        return {"error": f"Failed to parse JSON from Gemini response: {response.text}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred during parsing: {e}"}

# --- resume_upload VIEW (UNCHANGED) ---
def resume_upload(request):
    if request.method == 'POST':
        resume_file = request.FILES.get('resume_file')
        if not resume_file:
            return JsonResponse({'error': 'No file was uploaded.'}, status=400)
        if not os.path.exists(settings.MEDIA_ROOT):
            os.makedirs(settings.MEDIA_ROOT)
        unique_filename = str(uuid.uuid4()) + '.pdf'
        temp_file_path = os.path.join(settings.MEDIA_ROOT, unique_filename)
        try:
            with open(temp_file_path, 'wb+') as destination:
                for chunk in resume_file.chunks():
                    destination.write(chunk)
            resume_text = extract_text_from_pdf(temp_file_path)
            if resume_text is None:
                return JsonResponse({'error': 'Could not extract text from the PDF.'}, status=400)
            api_key = getattr(settings, 'GEMINI_API_KEY', None)
            if not api_key:
                return JsonResponse({'error': 'GEMINI_API_KEY not configured in settings.'}, status=500)
            parsed_data = parse_resume_with_gemini(resume_text, api_key)
            if 'error' in parsed_data:
                return JsonResponse({'error': parsed_data['error']}, status=500)
            else:
                return JsonResponse({'parsed_data': parsed_data})
        except Exception as e:
            return JsonResponse({'error': f'An unexpected server error occurred: {str(e)}'}, status=500)
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    return render(request, 'resume_upload.html')


# --- skill_analysis VIEW (UNCHANGED) ---
def skill_analysis(request):
    # Check if the model loaded correctly
    if not st_model:
        return JsonResponse({'status': 'error', 'message': 'Skill analysis model is not available.'}, status=503)
        
    context = {'technical_skills_list': TECHNICAL_SKILLS_LIST, 'soft_skills_list': SOFT_SKILLS_LIST}
    if request.method == 'POST' and request.FILES.get('resume'):
        try:
            uploaded_file = request.FILES['resume']
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            resume_text = extract_text(tmp_path)
            os.unlink(tmp_path)
            def match_role(text):
                if not text or str(text).strip() == "": return "unknown", "unknown", 0.0
                resume_embedding = st_model.encode(str(text), convert_to_tensor=True)
                scores = util.cos_sim(resume_embedding, role_embeddings)[0]
                best_idx = scores.argmax().item()
                best_score = scores[best_idx].item()
                matched_role = roles[best_idx]
                matched_domain = label_role.get(matched_role, "unknown").lower()
                if best_score < 0.4: return "unknown", "unknown", round(best_score, 3)
                return matched_role, matched_domain, round(best_score, 3)
            def extract_skills(text):
                found_skills = []
                if isinstance(text, str):
                    text_lower = text.lower()
                    for skill in all_skills:
                        if re.search(r'\b' + re.escape(skill.lower()) + r'\b', text_lower):
                            found_skills.append(skill)
                return found_skills
            matched_role, matched_domain, sim_score = match_role(resume_text)
            matched_skills = extract_skills(resume_text)
            analysis_results = {'matched_role': matched_role, 'matched_domain': matched_domain, 'similarity_percentage': sim_score * 100, 'matched_skills': matched_skills}
            accuracy = "High" if sim_score >= 0.7 else "Medium" if sim_score >= 0.4 else "Low"
            context.update({'analysis_results': analysis_results, 'accuracy': accuracy, 'success': True})
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'analysis_results': analysis_results, 'accuracy': accuracy})
            return render(request, 'skill_analysis.html', context)
        except Exception as e:
            context['error'] = str(e)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            return render(request, 'skill_analysis.html', context)
    return render(request, 'skill_analysis.html', context)


# --- JOB RECOMMENDER / QA VIEW (UNCHANGED) ---
QA_CONTEXT = """
Job Title: Software Engineer. Company: Google. Category: Engineering. Location: Mountain View, CA. Responsibilities: Design, develop, test, deploy, maintain and improve software. Manage individual project priorities, deadlines and deliverables.
Job Title: Data Analyst. Company: Meta. Category: Data Science. Location: New York, NY. Responsibilities: Perform analysis of large data sets. Develop and implement data analyses, data collection systems and other strategies that optimize statistical efficiency and quality. Identify, analyze, and interpret trends or patterns in complex data sets.
Job Title: Product Manager. Company: Amazon. Category: Product Management. Location: Seattle, WA. Minimum Qualifications: Bachelor's degree or equivalent practical experience. 5 years of experience in product management. Preferred Qualifications: Experience in a fast-paced, entrepreneurial environment. Experience with machine learning products.
Course Title: Introduction to Python. Organization: University of Michigan. Certificate Type: Course. Rating: 4.8. Difficulty: Beginner. Students Enrolled: 2.5m.
Course Title: Machine Learning. Organization: Stanford University. Certificate Type: Specialization. Rating: 4.9. Difficulty: Intermediate. Students Enrolled: 4.4m.
"""

def job_recommender(request):
    return render(request, 'job_recommender.html')

def ask_question(request):
    if request.method == 'POST':
        if qa_pipeline is None:
            return JsonResponse({'error': 'The Question-Answering model is not available.'}, status=503)
        try:
            data = json.loads(request.body)
            question = data.get('question')
            if not question:
                return JsonResponse({'error': 'No question was provided.'}, status=400)
            result = qa_pipeline(question=question, context=QA_CONTEXT)
            return JsonResponse({'answer': result['answer']})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON in request body.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'This endpoint only supports POST requests.'}, status=405)


# --- FEEDBACK VIEW (UNCHANGED) ---
def feedback(request):
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            return render(request, 'feedback.html', {'form': FeedbackForm(), 'success': True})
    else:
        form = FeedbackForm()
    return render(request, 'feedback.html', {'form': form})


# --- CHATBOT VIEW (UNCHANGED) ---
def chatbot(request):
    if request.method == 'POST':
        try:
            if df_sorted is None or df_sorted.empty:
                return JsonResponse({"response": "Sorry, the chatbot data is not available."})
            data = json.loads(request.body)
            user_message = data.get("message", "").strip().lower()
            current_index = request.session.get('current_index', 0)
            rejected_indices = request.session.get('rejected_indices', [])
            if not (0 <= current_index < len(df_sorted)):
                 return JsonResponse({"response": "No more recommendations available."})
            row = df_sorted.iloc[current_index]
            def format_recommendation(row_data):
                return (f"<strong>Job Title:</strong> {row_data.get('job_title', 'N/A')}<br>"
                        f"<strong>Matched Role:</strong> {row_data.get('Matched Role', 'N/A')}<br>"
                        f"<strong>Domain:</strong> {row_data.get('Matched Domain', 'N/A')}<br>"
                        f"<strong>Similarity Score:</strong> {row_data.get('Similarity Score', 0):.2f}<br><br>"
                        "You can ask: 'Why was I recommended this?', 'Show me courses', or 'Next'.")
            if user_message in ["start", "hi", "hello", "hey"]:
                request.session['current_index'] = 0
                request.session['rejected_indices'] = []
                row = df_sorted.iloc[0]
                response_text = f"Hi! Here is your first recommended role:<br><br>{format_recommendation(row)}"
                return JsonResponse({"response": response_text})
            if "why" in user_message:
                experience = row.get("experience", "Not specified")
                matched_skills = row.get("Matched Skills", "")
                skills_list = [s.strip() for s in matched_skills.split(",") if s.strip()]
                skills_text = "<br>".join(f"- {skill}" for skill in skills_list) if skills_list else "Not specified"
                response_text = (
                    "You were recommended this role because:<br><br>"
                    f"<strong>Similarity Score:</strong> {row['Similarity Score']:.2f}<br>"
                    f"<strong>Experience:</strong> {experience}<br>"
                    f"<strong>Key Skills:</strong><br>{skills_text}"
                )
                return JsonResponse({"response": response_text})
            if any(word in user_message for word in ["next", "another", "not satisfied"]):
                rejected_indices.append(current_index)
                next_index = current_index + 1
                while next_index < len(df_sorted) and next_index in rejected_indices:
                    next_index += 1
                if next_index >= len(df_sorted):
                    return JsonResponse({"response": "Sorry, there are no more recommendations available."})
                request.session['current_index'] = next_index
                request.session['rejected_indices'] = rejected_indices
                new_row = df_sorted.iloc[next_index]
                return JsonResponse({"response": f"Understood. Here is your next recommendation:<br><br>{format_recommendation(new_row)}"})
            if "courses" in user_message or "improve" in user_message:
                try:
                    query = f"online courses to become {row['Matched Role']}"
                    course_links = list(search(query, num_results=3))
                    links_text = "<br>".join([f"- <a href='{link}' target='_blank' rel='noopener noreferrer'>{link}</a>" for link in course_links])
                    return JsonResponse({"response": f"Here are some courses that might help:<br><br>{links_text}"})
                except Exception as e:
                    return JsonResponse({"response": "Sorry, I had trouble finding courses right now."})
            return JsonResponse({"response": "I didn't quite understand. You can ask 'Why?', 'Show me courses', or say 'Next'."})
        except Exception as e:
            return JsonResponse({"response": f"An error occurred: {str(e)}"}, status=500)
    return render(request, 'chatbot.html')
