from django import forms

class ResumeForm(forms.Form):
    resume = forms.FileField(label="Upload Resume (PDF)", required=True)

class FeedbackForm(forms.Form):
    feedback = forms.CharField(widget=forms.Textarea, label="Your Feedback")