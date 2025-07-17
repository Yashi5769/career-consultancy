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

# --- FIX: Define skill lists here to pass to the template ---
TECHNICAL_SKILLS_LIST = "python,java,c++,javascript,sql,html,css,ruby,php,swift,kotlin,go,rust,typescript".split(',')
SOFT_SKILLS_LIST = "communication,leadership,teamwork,problem solving,time management,adaptability,creativity,critical thinking,emotional intelligence,negotiation".split(',')


def load_skill_data():
    data_dir = os.path.join(settings.BASE_DIR, 'career_consulting', 'career', 'skill_analysis')
    
    with open(os.path.join(data_dir, 'label_role.json')) as f:
        label_role = json.load(f)
    
    with open(os.path.join(data_dir, 'skills.json')) as f:
        skills_dict = json.load(f)
    
    all_skills = set(skill for skills in skills_dict.values() for skill in skills)
    
    return label_role, skills_dict, all_skills

label_role, skills_dict, all_skills = load_skill_data()
roles = list(label_role.keys())

from sentence_transformers import SentenceTransformer, util
model = SentenceTransformer("all-MiniLM-L6-v2")
role_embeddings = model.encode(roles, convert_to_tensor=True)

def home(request):
    return render(request, 'home.html')

def resume_upload(request):
    form = ResumeUploadForm()
    return render(request, 'resume_upload.html', {'form': form})

def skill_analysis(request):
    context = {
        'technical_skills_list': TECHNICAL_SKILLS_LIST,
        'soft_skills_list': SOFT_SKILLS_LIST,
    }
    
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
                if not text or str(text).strip() == "":
                    return "unknown", "unknown", 0.0
                resume_embedding = model.encode(str(text), convert_to_tensor=True)
                scores = util.cos_sim(resume_embedding, role_embeddings)[0]
                best_idx = scores.argmax().item()
                best_score = scores[best_idx].item()
                matched_role = roles[best_idx]
                matched_domain = label_role.get(matched_role, "unknown").lower()
                if best_score < 0.4:
                    return "unknown", "unknown", round(best_score, 3)
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
            
            analysis_results = {
                'matched_role': matched_role,
                'matched_domain': matched_domain,
                'similarity_percentage': sim_score * 100,
                'matched_skills': matched_skills
            }
            
            accuracy = "High" if sim_score >= 0.7 else "Medium" if sim_score >= 0.4 else "Low"
            
            # Add results to the context
            context['analysis_results'] = analysis_results
            context['accuracy'] = accuracy
            context['success'] = True
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'analysis_results': analysis_results,
                    'accuracy': accuracy
                })
            
            return render(request, 'skill_analysis.html', context)
        
        except Exception as e:
            context['error'] = str(e)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
            return render(request, 'skill_analysis.html', context)
    
    return render(request, 'skill_analysis.html', context)

def job_recommender(request):
    return render(request, 'job_recommender.html')

def feedback(request):
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            return render(request, 'feedback.html', {'form': FeedbackForm(), 'success': True})
    else:
        form = FeedbackForm()
    return render(request, 'feedback.html', {'form': form})

def chatbot(request):
    return render(request, 'chatbot.html')
