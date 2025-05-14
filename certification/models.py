from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Test(models.Model):
    DIFFICULTY_LEVELS = (
        ('easy', 'Легкий'),
        ('medium', 'Средний'),
        ('hard', 'Сложный'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tests')
    assigned_users = models.ManyToManyField(User, related_name='assigned_tests')
    max_attempts = models.PositiveIntegerField(default=3, help_text='Максимальное количество попыток для прохождения теста')
    time_limit = models.PositiveIntegerField(default=0, help_text='Время на прохождение теста в минутах (0 - без ограничения)')
    passing_score = models.PositiveIntegerField(default=70, help_text='Проходной балл в процентах')
    difficulty_level = models.CharField(max_length=10, choices=DIFFICULTY_LEVELS, default='medium', help_text='Уровень сложности теста')

    def __str__(self):
        return self.title

class Question(models.Model):
    QUESTION_TYPES = (
        ('multiple', 'Вариационный вопрос'),
        ('text', 'Текстовый ответ'),
    )
    
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    image = models.ImageField(upload_to='questions/', blank=True, null=True)
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES, default='multiple')
    correct_answer = models.TextField(blank=True, null=True)  # Для текстовых ответов
    order = models.IntegerField(default=0)  # Добавляем поле для сортировки
    # Новые поля для улучшенной проверки текстовых ответов
    answer_synonyms = models.JSONField(default=dict, blank=True, help_text='Словарь синонимов в формате JSON')
    answer_abbreviations = models.JSONField(default=dict, blank=True, help_text='Словарь аббревиатур в формате JSON')
    similarity_threshold = models.FloatField(default=0.8, help_text='Порог схожести для текстовых ответов (0.0 - 1.0)')

    class Meta:
        ordering = ['order', 'id']  # Добавляем сортировку по умолчанию

    def __str__(self):
        return f"Вопрос для теста: {self.test.title}"

class AnswerOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.TextField()
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"Вариант ответа: {self.text}"

class TestResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    score = models.FloatField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.started_at:
            self.started_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Результат {self.user.username} для теста {self.test.title}"

class UserAnswer(models.Model):
    test_result = models.ForeignKey(TestResult, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.TextField(blank=True, null=True)
    selected_options = models.ManyToManyField(AnswerOption, blank=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"Ответ пользователя {self.test_result.user.username} на вопрос {self.question.id}"
