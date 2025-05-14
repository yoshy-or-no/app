from django import forms
from .models import Test, Question, AnswerOption
import json

class TestForm(forms.ModelForm):
    class Meta:
        model = Test
        fields = ['title', 'description', 'assigned_users', 'is_active', 'max_attempts', 'time_limit', 'passing_score', 'difficulty_level']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите название теста'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Опишите, что проверяет этот тест'}),
            'assigned_users': forms.SelectMultiple(attrs={
                'class': 'user-select',
                'data-placeholder': 'Выберите пользователей'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_attempts': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'time_limit': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Время в минутах (0 - без ограничения)'}),
            'passing_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'placeholder': 'Проходной балл в процентах'}),
            'difficulty_level': forms.Select(attrs={'class': 'form-select'})
        }
        error_messages = {
            'title': {
                'required': 'Пожалуйста, введите название теста',
            },
            'description': {
                'required': 'Пожалуйста, введите описание теста',
            },
            'max_attempts': {
                'required': 'Пожалуйста, укажите количество попыток',
            },
            'time_limit': {
                'required': 'Пожалуйста, укажите время на прохождение',
            },
            'passing_score': {
                'required': 'Пожалуйста, укажите проходной балл',
            },
            'assigned_users': {
                'required': 'Пожалуйста, выберите хотя бы одного пользователя',
            },
            'difficulty_level': {
                'required': 'Пожалуйста, выберите уровень сложности теста',
            },
        }

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if not self.instance.pk or self.instance.title != title:
            if Test.objects.filter(title=title).exists():
                raise forms.ValidationError('Тест с таким названием уже существует')
        return title

class AnswerOptionForm(forms.ModelForm):
    class Meta:
        model = AnswerOption
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите вариант ответа'}),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_text(self):
        text = self.cleaned_data.get('text', '').strip()
        if not text:
            raise forms.ValidationError('Текст варианта ответа не может быть пустым')
        return text

class BaseAnswerOptionFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        super().clean()
        # Проверяем, что есть хотя бы один правильный ответ
        has_correct = False
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                if form.cleaned_data.get('is_correct'):
                    has_correct = True
                    break
        if not has_correct:
            raise forms.ValidationError('Должен быть хотя бы один правильный ответ')

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['empty_permitted'] = False
        return kwargs

    def add_fields(self, form, index):
        super().add_fields(form, index)
        # Добавляем скрытое поле для отслеживания удаленных форм
        form.fields['DELETE'] = forms.BooleanField(required=False, widget=forms.HiddenInput())

AnswerOptionFormSet = forms.inlineformset_factory(
    Question, AnswerOption, form=AnswerOptionForm,
    formset=BaseAnswerOptionFormSet,
    extra=1,  # Начальное количество пустых форм
    can_delete=True,
    min_num=1,
    validate_min=True,
    validate_max=True,
    max_num=10,
    absolute_max=10,
    fk_name='question',
    can_order=False
)

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'image', 'question_type', 'correct_answer', 
                 'answer_synonyms', 'answer_abbreviations', 'similarity_threshold']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Введите текст вопроса'}),
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'correct_answer': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите правильный ответ'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'answer_synonyms': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '{"синоним1": "основное_слово", "синоним2": "основное_слово"}'
            }),
            'answer_abbreviations': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '{"аббр1": "полное_название", "аббр2": "полное_название"}'
            }),
            'similarity_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.0',
                'max': '1.0',
                'step': '0.1'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['question_type'].choices = [
            ('multiple', 'Вариационный вопрос'),
            ('text', 'Текстовый ответ')
        ]
        
        # Скрываем поле correct_answer, если тип вопроса не text
        if 'question_type' in self.data and self.data['question_type'] != 'text':
            self.fields['correct_answer'].widget = forms.HiddenInput()
        elif 'question_type' in self.initial and self.initial['question_type'] != 'text':
            self.fields['correct_answer'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get('question_type')
        correct_answer = cleaned_data.get('correct_answer')

        if question_type == 'text' and not correct_answer:
            self.add_error('correct_answer', 'Для текстового вопроса необходимо указать правильный ответ')

        return cleaned_data

    def clean_answer_synonyms(self):
        data = self.cleaned_data.get('answer_synonyms')
        if not data:
            return {}
        try:
            if isinstance(data, str):
                return json.loads(data)
            return data
        except json.JSONDecodeError:
            raise forms.ValidationError('Неверный формат JSON для синонимов')

    def clean_answer_abbreviations(self):
        data = self.cleaned_data.get('answer_abbreviations')
        if not data:
            return {}
        try:
            if isinstance(data, str):
                return json.loads(data)
            return data
        except json.JSONDecodeError:
            raise forms.ValidationError('Неверный формат JSON для аббревиатур')

class AnswerForm(forms.Form):
    def __init__(self, question, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if question.question_type == 'text':
            self.fields['answer'] = forms.CharField(
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                required=True
            )
        else:  # variants
            options = question.options.all()
            self.fields['answer'] = forms.ModelMultipleChoiceField(
                queryset=options,
                widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
                required=True
            ) 