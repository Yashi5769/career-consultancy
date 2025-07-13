from django.shortcuts import render
from .forms import ResumeForm, FeedbackForm

def home(request):
    return render(request, 'home.html')

def resume_upload(request):
    form = ResumeForm()
    return render(request, 'resume_upload.html', {'form': form})

def skill_analysis(request):
    return render(request, 'skill_analysis.html')

def job_recommender(request):
    return render(request, 'job_recommender.html')

def feedback(request):
    form = FeedbackForm()
    return render(request, 'feedback.html', {'form': form})

def chatbot(request):
    return render(request, 'chatbot.html')