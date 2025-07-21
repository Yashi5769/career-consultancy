from django.urls import path
from . import views

# This app_name is important for the {% url ... %} tags in your templates
app_name = 'career'

urlpatterns = [
    # This will be your home page
    path('', views.home, name='home'),
    
    # The rest of your pages (unchanged)
    path('resume-upload/', views.resume_upload, name='resume_upload'),
    path('skill-analysis/', views.skill_analysis, name='skill_analysis'),
    path('job-recommender/', views.job_recommender, name='job_recommender'),
    path('feedback/', views.feedback, name='feedback'),
    path('chatbot/', views.chatbot, name='chatbot'),

    # --- NEW URL PATTERN ---
    # This path is the new API endpoint for the Question-Answering model.
    # The frontend will send POST requests to this URL.
    path('ask-question/', views.ask_question, name='ask_question'),
]
