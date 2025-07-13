from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('resume/', views.resume_upload, name='resume'),
    path('analysis/', views.skill_analysis, name='analysis'),
    path('recommend/', views.job_recommender, name='recommend'),
    path('feedback/', views.feedback, name='feedback'),
    path('chatbot/', views.chatbot, name='chatbot'),
]