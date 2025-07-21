from django import forms
from django.core.validators import FileExtensionValidator, MaxValueValidator, EmailValidator
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import magic
import re
import os
from django.conf import settings

class SecureFileField(forms.FileField):
    """Custom file field with MIME type validation and enhanced security checks"""
    def __init__(self, *args, **kwargs):
        self.allowed_mime_types = kwargs.pop('allowed_mime_types', None)
        self.max_upload_size = kwargs.pop('max_upload_size', None)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        file = super().clean(data, initial)
        
        if file:
            # MIME type validation
            if self.allowed_mime_types:
                mime_type = magic.from_buffer(file.read(2048), mime=True)
                file.seek(0)
                
                if mime_type not in self.allowed_mime_types:
                    raise ValidationError(
                        _("Invalid file type. Detected MIME type: %(mime)s"),
                        params={'mime': mime_type},
                        code='invalid_mime_type'
                    )
            
            # Size validation
            if self.max_upload_size and file.size > self.max_upload_size:
                raise ValidationError(
                    _('File too large. Max size is %(max_size)s') % {
                        'max_size': filesizeformat(self.max_upload_size)
                    },
                    code='file_too_large'
                )
            
            # Content validation
            if hasattr(self, 'validate_content'):
                self.validate_content(file)
        
        return file

class ResumeUploadForm(forms.Form):
    MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
    ALLOWED_MIME_TYPES = ['application/pdf']
    MIN_TEXT_LENGTH = 100  # Minimum characters to be considered valid resume
    
    resume = SecureFileField(
        label=_("Upload Your Resume"),
        help_text=_("PDF files only. Max size: %(max_size)s") % {
            'max_size': filesizeformat(MAX_UPLOAD_SIZE)
        },
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf'],
                message=_('Only PDF files are allowed (extension must be .pdf)')
            )
        ],
        widget=forms.FileInput(attrs={
            'accept': '.pdf',
            'class': 'form-control-file',
            'data-max-size': MAX_UPLOAD_SIZE
        }),
        allowed_mime_types=ALLOWED_MIME_TYPES,
        max_upload_size=MAX_UPLOAD_SIZE
    )

    def validate_content(self, file):
        """Additional content validation for resumes"""
        # Verify PDF header
        header = file.read(4)
        file.seek(0)
        
        if header != b'%PDF':
            raise ValidationError(
                _("Invalid PDF file content"),
                code='invalid_pdf_content'
            )
        
        # Extract text and check minimum content length
        try:
            from pdfminer.high_level import extract_text
            text = extract_text(file)
            file.seek(0)
            
            # Clean and count meaningful characters
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if len(clean_text) < self.MIN_TEXT_LENGTH:
                raise ValidationError(
                    _("The document doesn't contain enough text for analysis (minimum %(min_chars)d characters)") % {
                        'min_chars': self.MIN_TEXT_LENGTH
                    },
                    code='insufficient_text_content'
                )
                
            # Check for suspicious patterns
            if re.search(r'<\s*script', text, re.I):
                raise ValidationError(
                    _("Document contains potentially malicious content"),
                    code='suspicious_content'
                )
                
        except Exception as e:
            raise ValidationError(
                _("Could not process the document: %(error)s") % {
                    'error': str(e)
                },
                code='processing_error'
            )


class FeedbackForm(forms.Form):
    RATING_CHOICES = [
        ('', _('Select a rating')),
        ('5', _('Excellent')),
        ('4', _('Good')),
        ('3', _('Average')),
        ('2', _('Fair')),
        ('1', _('Poor'))
    ]
    
    SERVICE_CHOICES = [
        ('', _('Select service')),
        ('skill_analysis', _('Skill Analysis')),
        ('resume_parser', _('Resume Parser')),
        ('job_recommender', _('Job Recommender')),
        ('chatbot', _('Career Bot'))
    ]
    
    name = forms.CharField(
        label=_("Your Name"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': _('Optional'),
            'class': 'form-control'
        })
    )
    
    email = forms.EmailField(
        label=_("Email Address"),
        required=False,
        widget=forms.EmailInput(attrs={
            'placeholder': _('Optional'),
            'class': 'form-control'
        }),
        validators=[
            EmailValidator(message=_("Enter a valid email address"))
        ]
    )
    
    service = forms.ChoiceField(
        label=_("Service"),
        choices=SERVICE_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    rating = forms.ChoiceField(
        label=_("Rating"),
        choices=RATING_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    feedback = forms.CharField(
        label=_("Your Feedback"),
        widget=forms.Textarea(attrs={
            'rows': 5,
            'class': 'form-control',
            'placeholder': _('Please share your experience...')
        }),
        min_length=10,
        error_messages={
            'min_length': _('Please provide at least %(limit_value)d characters (you entered %(show_value)d).')
        }
    )
    
    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        name = cleaned_data.get('name')
        
        # Require either name or email
        if not email and not name:
            raise ValidationError(
                _("Please provide either your name or email address"),
                code='missing_contact_info'
            )
        
        # Validate email if provided
        if email:
            # Simple domain validation
            domain = email.split('@')[-1] if '@' in email else ''
            if domain and not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain):
                self.add_error('email', _("Please enter a valid email domain"))
        
        return cleaned_data

class SkillAnalysisSettingsForm(forms.Form):
    """Form for configuring skill analysis parameters"""
    similarity_threshold = forms.FloatField(
        label=_("Role Matching Threshold"),
        min_value=0.1,
        max_value=1.0,
        initial=0.4,
        widget=forms.NumberInput(attrs={
            'step': "0.1",
            'class': 'form-range',
            'type': 'range'
        }),
        help_text=_("Minimum confidence score for role matching (0.1-1.0)")
    )
    
    skill_match_strictness = forms.ChoiceField(
        label=_("Skill Matching Strictness"),
        choices=[
            ('strict', _("Strict (exact matches only)")),
            ('moderate', _("Moderate (similar terms)")),
            ('flexible', _("Flexible (related concepts)"))
        ],
        initial='moderate',
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        })
    )
    
    include_related_skills = forms.BooleanField(
        label=_("Include Related Skills"),
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text=_("Suggest skills commonly associated with your detected role")
    )
