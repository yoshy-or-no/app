from django.contrib import admin
from .models import Test, Question, TestResult, UserAnswer, AnswerOption

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1

class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 1

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by', 'created_at', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description')
    inlines = [QuestionInline]

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'test', 'question_type')
    list_filter = ('question_type',)
    search_fields = ('text',)
    inlines = [AnswerOptionInline]

@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_correct')
    list_filter = ('is_correct',)
    search_fields = ('text',)

@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'test', 'score', 'completed_at')
    list_filter = ('test', 'completed_at')
    search_fields = ('user__username',)

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('test_result', 'question', 'is_correct')
    list_filter = ('is_correct',)
    search_fields = ('test_result__user__username',)
