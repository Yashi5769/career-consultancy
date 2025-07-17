from django import forms
from django.core.validators import FileExtensionValidator, MaxValueValidator
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import magic  

class SecureFileField(forms.FileField):
    """Custom file field with MIME type validation"""
    def __init__(self, *args, **kwargs):
        self.allowed_mime_types = kwargs.pop('allowed_mime_types', None)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        file = super().clean(data, initial)
        if file and self.allowed_mime_types:
            # Read only the first 2048 bytes for MIME detection
            mime_type = magic.from_buffer(file.read(2048), mime=True)
            file.seek(0)  # Reset file pointer
            
            if mime_type not in self.allowed_mime_types:
                raise ValidationError(
                    _("Invalid file type. Detected MIME type: %(mime)s"),
                    params={'mime': mime_type},
                    code='invalid_mime_type'
                )
        return file

class ResumeUploadForm(forms.Form):
    MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
    ALLOWED_MIME_TYPES = ['application/pdf']
    
    resume = SecureFileField(
        label=_("Upload Your Resume"),
        help_text=_("PDF files only. Max size: %(max_size)s") % {
            'max_size': filesizeformat(MAX_UPLOAD_SIZE)
        },
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf'],
                message=_('Only PDF files are allowed (extension must be .pdf)')
            ),
            MaxValueValidator(
                limit_value=MAX_UPLOAD_SIZE,
                message=_('File too large. Max size is %(max_size)s') % {
                    'max_size': filesizeformat(MAX_UPLOAD_SIZE)
                }
            )
        ],
        widget=forms.FileInput(attrs={
            'accept': '.pdf',
            'class': 'form-control-file',
            'data-max-size': MAX_UPLOAD_SIZE
        }),
        allowed_mime_types=ALLOWED_MIME_TYPES
    )

    def clean_resume(self):
        data = self.cleaned_data['resume']
        
        # Additional security checks
        if data:
            # Verify PDF content (simple check for PDF header)
            header = data.file.read(4)
            data.file.seek(0)
            
            if header != b'%PDF':
                raise ValidationError(
                    _("Invalid PDF file content"),
                    code='invalid_pdf_content'
                )
        
        return data

class FeedbackForm(forms.Form):
    RATING_CHOICES = [
        ('', _('Select a rating')),
        ('5', _('Excellent')),
        ('4', _('Good')),
        ('3', _('Average')),
        ('2', _('Fair')),
        ('1', _('Poor'))
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
        
        return cleaned_data