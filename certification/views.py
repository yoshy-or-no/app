from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.forms import formset_factory
from .models import Test, Question, TestResult, UserAnswer, AnswerOption
from .forms import TestForm, QuestionForm, AnswerForm, AnswerOptionFormSet
from django.db import models
from django.http import JsonResponse, HttpResponse
import json
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.views.decorators.http import require_POST, require_http_methods
from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string
from django.utils import timezone
import random
from django.db.models import Avg, Max
import base64
from io import BytesIO
import matplotlib
matplotlib.use('Agg')  # Используем неинтерактивный бэкенд
import matplotlib.pyplot as plt
import seaborn as sns
from weasyprint import HTML
from django.template.loader import get_template
from django.conf import settings
import os
from .text_checker import TextAnswerChecker

def is_admin(user):
    return user.is_staff

@login_required
def home(request):
    # Получаем параметры фильтрации и поиска
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Базовый запрос
    if request.user.is_staff:
        tests = Test.objects.filter(created_by=request.user)
    else:
        tests = Test.objects.filter(assigned_users=request.user, is_active=True)
    
    # Применяем поиск
    if search_query:
        tests = tests.filter(title__icontains=search_query)
    
    # Применяем фильтр по статусу
    if status_filter == 'active':
        tests = tests.filter(is_active=True)
    elif status_filter == 'inactive':
        tests = tests.filter(is_active=False)
    elif status_filter == 'passed':
        # Получаем ID тестов, которые пользователь успешно прошел
        passed_test_ids = TestResult.objects.filter(
            user=request.user,
            score__gte=models.F('test__passing_score')
        ).values_list('test_id', flat=True)
        tests = tests.filter(id__in=passed_test_ids)
    elif status_filter == 'not_passed':
        # Получаем ID тестов, которые пользователь не прошел или не начинал
        attempted_test_ids = TestResult.objects.filter(
            user=request.user
        ).values_list('test_id', flat=True)
        not_passed_test_ids = TestResult.objects.filter(
            user=request.user,
            score__lt=models.F('test__passing_score')
        ).values_list('test_id', flat=True)
        tests = tests.exclude(id__in=attempted_test_ids) | tests.filter(id__in=not_passed_test_ids)
    
    # Применяем сортировку
    tests = tests.order_by(sort_by)
    
    # Добавляем статистику и последний результат для каждого теста
    for test in tests:
        test.total_attempts = TestResult.objects.filter(test=test).count()
        if test.total_attempts > 0:
            test.average_score = TestResult.objects.filter(test=test).aggregate(
                avg_score=models.Avg('score')
            )['avg_score']
        else:
            test.average_score = 0
            
        # Получаем последний результат теста для текущего пользователя
        if not request.user.is_staff:
            test.last_result = TestResult.objects.filter(
                test=test,
                user=request.user
            ).order_by('-created_at').first()
    
    return render(request, 'certification/home.html', {
        'tests': tests,
        'search_query': search_query,
        'status_filter': status_filter,
        'sort_by': sort_by
    })

@login_required
@user_passes_test(is_admin)
def create_test(request):
    if request.method == 'POST':
        form = TestForm(request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            test.created_by = request.user
            test.save()
            form.save_m2m()  # Сохраняем связи many-to-many для assigned_users
            messages.success(request, 'Тест успешно создан!')
            return redirect('add_question', test_id=test.id)
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = TestForm()
    
    return render(request, 'certification/test_form.html', {
        'form': form
    })

@login_required
@user_passes_test(is_admin)
def add_question(request, test_id):
    test = get_object_or_404(Test, id=test_id, created_by=request.user)
    
    if request.method == 'POST':
        form = QuestionForm(request.POST, request.FILES)
        formset = AnswerOptionFormSet(request.POST, prefix='form')
        
        if form.is_valid():
            try:
                question = form.save(commit=False)
                question.test = test
                
                # Если тип вопроса - текстовый, сохраняем правильный ответ
                if question.question_type == 'text':
                    question.correct_answer = form.cleaned_data['correct_answer']
                    # Добавляем отладочную информацию
                    print("Сохранение текстового вопроса:")
                    print(f"Правильный ответ: {question.correct_answer}")
                    print(f"Синонимы: {form.cleaned_data.get('answer_synonyms')}")
                    print(f"Аббревиатуры: {form.cleaned_data.get('answer_abbreviations')}")
                    print(f"Порог схожести: {form.cleaned_data.get('similarity_threshold')}")
                    
                    question.save()
                else:  # multiple
                    # Сначала сохраняем вопрос
                    question.save()
                    
                    # Проверяем валидность формысета
                    if formset.is_valid():
                        # Удаляем все существующие варианты ответов
                        question.options.all().delete()
                        
                        # Сохраняем только непустые варианты ответов
                        for answer_form in formset:
                            if answer_form.cleaned_data and not answer_form.cleaned_data.get('DELETE', False):
                                text = answer_form.cleaned_data.get('text', '').strip()
                                if text:  # Проверяем, что текст не пустой
                                    answer = answer_form.save(commit=False)
                                    answer.question = question
                                    answer.save()
                    else:
                        # Если формасет невалиден, удаляем вопрос и показываем ошибки
                        question.delete()
                        messages.error(request, 'Пожалуйста, исправьте ошибки в вариантах ответов')
                        return render(request, 'certification/add_question.html', {
                            'test': test,
                            'form': form,
                            'formset': formset,
                            'questions': Question.objects.filter(test=test).order_by('id')
                        })
                
                messages.success(request, 'Вопрос успешно добавлен')
                return redirect('add_question', test_id=test_id)
            except Exception as e:
                messages.error(request, f'Ошибка при сохранении вопроса: {str(e)}')
                print(f"Ошибка при сохранении вопроса: {str(e)}")
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
            print("Ошибки формы:", form.errors)
    else:
        form = QuestionForm()
        # Создаем новый вопрос для формысета
        question = Question(test=test)
        # Инициализируем формосет с одной пустой формой
        formset = AnswerOptionFormSet(instance=question, prefix='form')
        # Устанавливаем количество форм в 1
        formset.extra = 1
        formset.initial = [{}]  # Добавляем один пустой словарь для инициализации
    
    # Получаем все вопросы для текущего теста
    questions = Question.objects.filter(test=test).order_by('id')
    
    return render(request, 'certification/add_question.html', {
        'test': test,
        'questions': questions,
        'form': form,
        'formset': formset
    })

@login_required
def test_detail(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    if not request.user.is_staff and request.user not in test.assigned_users.all():
        messages.error(request, 'У вас нет доступа к этому тесту')
        return redirect('home')
    
    # Получаем вопросы с предварительной загрузкой вариантов ответов
    questions = test.questions.all().prefetch_related('options')
    
    # Проверяем количество попыток
    if not request.user.is_staff:
        # Считаем только завершенные попытки
        attempts = TestResult.objects.filter(
            test=test,
            user=request.user,
            completed_at__isnull=False
        ).count()
        
        if attempts >= test.max_attempts:
            messages.error(request, f'Вы исчерпали все попытки ({test.max_attempts}) для прохождения этого теста')
            return redirect('home')
    
    if request.method == 'POST':
        total_questions = questions.count()
        text_questions_count = questions.filter(question_type='text').count()
        multiple_questions_count = total_questions - text_questions_count
        
        # Начинаем с 100%
        final_score = 100
        
        # Создаем результат теста
        test_result = TestResult.objects.create(
            user=request.user,
            test=test,
            score=0,
            started_at=timezone.now(),
            completed_at=None
        )
        
        for question in questions:
            user_answer = UserAnswer.objects.create(
                test_result=test_result,
                question=question
            )
            
            if question.question_type == 'text':
                answer_text = request.POST.get(f'question_{question.id}')
                user_answer.answer_text = answer_text
                
                # Используем новый проверщик ответов с дополнительными параметрами
                checker = TextAnswerChecker(
                    question.correct_answer,
                    similarity_threshold=question.similarity_threshold,
                    synonyms=question.answer_synonyms,
                    abbreviations=question.answer_abbreviations
                )
                user_answer.is_correct = checker.check_answer(answer_text)
                
                if not user_answer.is_correct:
                    # За неправильный текстовый ответ отнимаем 5%
                    final_score -= 5
                    print(f"Текстовый вопрос {question.id}: неправильный ответ (-5%)")
                else:
                    print(f"Текстовый вопрос {question.id}: правильный ответ")
            else:  # multiple
                selected_options = request.POST.getlist(f'question_{question.id}')
                if selected_options:
                    options = AnswerOption.objects.filter(id__in=selected_options)
                    user_answer.selected_options.set(options)
                    
                    correct_options = question.options.filter(is_correct=True)
                    selected_correct = set(options) & set(correct_options)
                    selected_incorrect = set(options) - set(correct_options)
                    
                    if len(selected_incorrect) > 0:
                        # За каждый неправильный вариант ответа отнимаем 2%
                        final_score -= len(selected_incorrect) * 2
                        print(f"Вопрос с выбором {question.id}: {len(selected_incorrect)} неправильных вариантов (-{len(selected_incorrect) * 2}%)")
                    
                    user_answer.is_correct = len(selected_incorrect) == 0
                else:
                    user_answer.is_correct = False
                    # За отсутствие ответа отнимаем 3%
                    final_score -= 3
                    print(f"Вопрос с выбором {question.id}: нет ответа (-3%)")
            
            user_answer.save()
        
        # Ограничиваем минимальный балл 0%
        final_score = max(0, final_score)
        
        print(f"Финальный результат: {final_score:.1f}%")
        
        test_result.score = final_score
        test_result.completed_at = timezone.now()
        test_result.save()
        
        return redirect('test_result', test_id=test.id, result_id=test_result.id)
    
    # Получаем количество оставшихся попыток
    attempts = TestResult.objects.filter(test=test, user=request.user).count()
    remaining_attempts = test.max_attempts - attempts
    
    # Проверяем, есть ли незавершенная попытка
    unfinished_attempt = TestResult.objects.filter(
        test=test,
        user=request.user,
        completed_at__isnull=True
    ).first()
    
    if unfinished_attempt:
        messages.warning(request, 'У вас есть незавершенная попытка прохождения теста')
    
    return render(request, 'certification/test_detail.html', {
        'test': test,
        'questions': questions,
        'remaining_attempts': remaining_attempts,
        'total_attempts': test.max_attempts,
        'unfinished_attempt': unfinished_attempt
    })

@login_required
@user_passes_test(is_admin)
def test_statistics(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    attempts = TestResult.objects.filter(test=test).order_by('-completed_at')
    
    # Получаем уникальных пользователей, которые проходили тест
    users = User.objects.filter(testresult__test=test).distinct()
    users_data = [{
        'id': user.id,
        'name': user.get_full_name() or user.username
    } for user in users]

    # Получаем пользователей, которые не прошли тест
    failed_users = []
    for user in users:
        # Проверяем, есть ли у пользователя хотя бы одна успешная попытка
        has_passed = attempts.filter(
            user=user,
            score__gte=test.passing_score
        ).exists()
        
        if not has_passed:
            # Получаем последнюю попытку пользователя
            last_attempt = attempts.filter(user=user).order_by('-completed_at').first()
            if last_attempt:
                failed_users.append({
                    'id': user.id,
                    'name': user.get_full_name() or user.username,
                    'last_attempt_date': last_attempt.completed_at,
                    'last_attempt_score': last_attempt.score,
                    'total_attempts': attempts.filter(user=user).count()
                })

    # Подготавливаем данные о попытках для JavaScript
    attempts_data = []
    for attempt in attempts:
        correct_answers = attempt.answers.filter(is_correct=True).count()
        total_questions = test.questions.count()
        attempts_data.append({
            'user_id': attempt.user.id,
            'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None,
            'score': attempt.score,
            'correct_answers': correct_answers,
            'total_questions': total_questions
        })
        
        # Добавляем данные для отображения в шаблоне
        attempt.correct_answers = correct_answers
        attempt.total_questions = total_questions

    # Подготавливаем данные для круговой диаграммы лучших результатов
    pie_chart_data = {
        'labels': [],
        'data': [],
        'colors': []
    }

    # Получаем лучшие результаты для каждого пользователя
    for user in users:
        best_attempt = attempts.filter(user=user).order_by('-score').first()
        if best_attempt:
            pie_chart_data['labels'].append(user.get_full_name() or user.username)
            pie_chart_data['data'].append(float(best_attempt.score))  # Преобразуем в float
            # Генерируем случайный цвет для каждого пользователя
            color = f'rgba({random.randint(0, 255)}, {random.randint(0, 255)}, {random.randint(0, 255)}, 0.7)'
            pie_chart_data['colors'].append(color)

    # Подготавливаем данные для тепловой карты
    heatmap_data = {
        'data': [[0 for _ in range(52)] for _ in range(7)],  # 7 дней недели x 52 недели
        'max_value': 0
    }

    # Получаем дату 52 недели назад
    end_date = timezone.now()
    start_date = end_date - timezone.timedelta(weeks=52)

    # Заполняем матрицу данными о попытках
    for attempt in attempts.filter(completed_at__gte=start_date):
        # Получаем день недели (0-6, где 0 - понедельник)
        day_of_week = attempt.completed_at.weekday()
        
        # Вычисляем номер недели (0-51)
        week_number = (end_date - attempt.completed_at).days // 7
        
        if 0 <= week_number < 52:  # Проверяем, что неделя в пределах последних 52 недель
            heatmap_data['data'][day_of_week][week_number] += 1
            heatmap_data['max_value'] = max(heatmap_data['max_value'], heatmap_data['data'][day_of_week][week_number])

    # Подготавливаем данные для распределения результатов
    distribution_ranges = [
        (0, 20, '0-20%'),
        (20, 40, '20-40%'),
        (40, 60, '40-60%'),
        (60, 80, '60-80%'),
        (80, 101, '80-100%')
    ]

    distribution_data = []
    for start, end, label in distribution_ranges:
        count = attempts.filter(score__gte=start, score__lt=end).count()
        distribution_data.append({
            'range': label,
            'count': count
        })

    context = {
        'test': test,
        'attempts': attempts,
        'attempts_data': attempts_data,
        'average_score': attempts.aggregate(Avg('score'))['score__avg'] or 0,
        'best_score': attempts.aggregate(Max('score'))['score__max'] or 0,
        'total_attempts': attempts.count(),
        'pie_chart_data': pie_chart_data,
        'distribution_data': distribution_data,
        'heatmap_data': heatmap_data,
        'users': users_data,
        'failed_users': failed_users,
    }
    
    return render(request, 'certification/test_statistics.html', context)

@login_required
@user_passes_test(is_admin)
def toggle_test_status(request, test_id):
    test = get_object_or_404(Test, id=test_id, created_by=request.user)
    
    if request.method == 'POST':
        test.is_active = not test.is_active
        test.save()
        return JsonResponse({
            'success': True,
            'is_active': test.is_active
        })
    
    return JsonResponse({
        'success': False,
        'error': 'Method not allowed'
    }, status=405)

@login_required
@user_passes_test(is_admin)
@require_POST
def delete_test(request, test_id):
    try:
        test = get_object_or_404(Test, id=test_id, created_by=request.user)
        test.delete()
        messages.success(request, 'Тест успешно удален!')
    except Exception as e:
        messages.error(request, f'Ошибка при удалении теста: {str(e)}')
    return redirect('home')

@login_required
def test_result(request, test_id, result_id):
    test = get_object_or_404(Test, id=test_id)
    test_result = get_object_or_404(TestResult, id=result_id, user=request.user, test=test)
    
    # Подсчитываем количество правильных ответов
    correct_answers = test_result.answers.filter(is_correct=True).count()
    total_questions = test.questions.count()
    incorrect_answers = total_questions - correct_answers
    
    return render(request, 'certification/test_result.html', {
        'test': test,
        'test_result': test_result,
        'correct_answers': correct_answers,
        'total_questions': total_questions,
        'incorrect_answers': incorrect_answers
    })

@login_required
@user_passes_test(is_admin)
def attempt_details(request, test_id, attempt_id):
    test = get_object_or_404(Test, id=test_id, created_by=request.user)
    attempt = get_object_or_404(TestResult, id=attempt_id, test=test)
    
    questions_data = []
    for answer in attempt.answers.all():
        question_data = {
            'text': answer.question.text,
            'question_type': answer.question.question_type,
            'options': []
        }
        
        # Для вопросов с вариантами ответа
        if answer.question.question_type == 'multiple':
            for option in answer.question.options.all():
                question_data['options'].append({
                    'text': option.text,
                    'is_correct': option.is_correct,
                    'selected': option in answer.selected_options.all()
                })
        # Для текстовых вопросов
        else:
            question_data['options'].append({
                'text': f'Ответ пользователя: {answer.answer_text}',
                'is_correct': answer.is_correct,
                'selected': True
            })
            # Добавляем правильный ответ для текстовых вопросов
            question_data['options'].append({
                'text': f'Правильный ответ: {answer.question.correct_answer}',
                'is_correct': True,
                'selected': False
            })
        
        questions_data.append(question_data)
    
    return JsonResponse({
        'questions': questions_data,
        'user': attempt.user.get_full_name() or attempt.user.username,
        'score': attempt.score,
        'completed_at': attempt.completed_at.strftime('%d.%m.%Y %H:%M') if attempt.completed_at else None
    })

@login_required
@user_passes_test(is_admin)
def manage_users(request):
    if request.method == 'POST':
        if 'delete_user' in request.POST:
            user_id = request.POST.get('delete_user')
            try:
                user = User.objects.get(id=user_id)
                username = user.username
                user.delete()
                messages.success(request, f'Пользователь {username} успешно удален!')
            except User.DoesNotExist:
                messages.error(request, 'Пользователь не найден')
            return redirect('manage_users')
        
        if 'change_password' in request.POST:
            user_id = request.POST.get('user_id')
            try:
                user = User.objects.get(id=user_id)
                form = SetPasswordForm(user, request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, f'Пароль пользователя {user.username} успешно изменен!')
                else:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f'Ошибка при изменении пароля: {error}')
            except User.DoesNotExist:
                messages.error(request, 'Пользователь не найден')
            return redirect('manage_users')
        
        if 'toggle_staff' in request.POST:
            user_id = request.POST.get('user_id')
            try:
                user = User.objects.get(id=user_id)
                user.is_staff = not user.is_staff
                user.save()
                status = 'назначены' if user.is_staff else 'сняты'
                messages.success(request, f'Права администратора для пользователя {user.username} успешно {status}!')
            except User.DoesNotExist:
                messages.error(request, 'Пользователь не найден')
            return redirect('manage_users')
        
        form = UserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                messages.success(request, f'Пользователь {user.username} успешно создан!')
                return redirect('manage_users')
            except Exception as e:
                messages.error(request, f'Ошибка при создании пользователя: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Ошибка в поле {field}: {error}')
    else:
        form = UserCreationForm()
    
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'certification/manage_users.html', {
        'form': form,
        'users': users
    })

@login_required
@user_passes_test(is_admin)
def copy_test(request, test_id):
    test = get_object_or_404(Test, id=test_id, created_by=request.user)
    
    if request.method == 'POST':
        try:
            # Создаем копию теста
            new_test = Test.objects.create(
                title=f"{test.title} (копия)",
                description=test.description,
                created_by=request.user,
                is_active=False
            )
            
            # Копируем вопросы
            for question in test.questions.all():
                new_question = Question.objects.create(
                    test=new_test,
                    text=question.text,
                    question_type=question.question_type,
                    correct_answer=question.correct_answer
                )
                
                # Копируем варианты ответов
                for option in question.options.all():
                    AnswerOption.objects.create(
                        question=new_question,
                        text=option.text,
                        is_correct=option.is_correct
                    )
            
            messages.success(request, 'Тест успешно скопирован!')
            return redirect('test_detail', test_id=new_test.id)
        except Exception as e:
            messages.error(request, f'Ошибка при копировании теста: {str(e)}')
    
    return render(request, 'certification/copy_test.html', {'test': test})

@login_required
@user_passes_test(is_admin)
def export_test(request, test_id):
    test = get_object_or_404(Test, id=test_id, created_by=request.user)
    
    # Создаем JSON-структуру теста
    test_data = {
        'title': test.title,
        'description': test.description,
        'questions': []
    }
    
    for question in test.questions.all():
        question_data = {
            'text': question.text,
            'question_type': question.question_type,
            'correct_answer': question.correct_answer,
            'options': []
        }
        
        for option in question.options.all():
            question_data['options'].append({
                'text': option.text,
                'is_correct': option.is_correct
            })
        
        test_data['questions'].append(question_data)
    
    # Создаем ответ с JSON-файлом
    response = HttpResponse(
        json.dumps(test_data, ensure_ascii=False, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename=test_{test.id}.json'
    
    return response

@login_required
@user_passes_test(is_admin)
def import_test(request):
    if request.method == 'POST':
        try:
            json_file = request.FILES['json_file']
            test_data = json.loads(json_file.read().decode('utf-8'))
            
            # Создаем новый тест
            new_test = Test.objects.create(
                title=test_data['title'],
                description=test_data['description'],
                created_by=request.user,
                is_active=False
            )
            
            # Создаем вопросы и варианты ответов
            for question_data in test_data['questions']:
                question = Question.objects.create(
                    test=new_test,
                    text=question_data['text'],
                    question_type=question_data['question_type'],
                    correct_answer=question_data['correct_answer']
                )
                
                for option_data in question_data['options']:
                    AnswerOption.objects.create(
                        question=question,
                        text=option_data['text'],
                        is_correct=option_data['is_correct']
                    )
            
            messages.success(request, 'Тест успешно импортирован!')
            return redirect('test_detail', test_id=new_test.id)
        except Exception as e:
            messages.error(request, f'Ошибка при импорте теста: {str(e)}')
    
    return render(request, 'certification/import_test.html')

@login_required
@require_POST
def reorder_questions(request):
    try:
        data = json.loads(request.body)
        questions = data.get('questions', [])
        
        for item in questions:
            question = get_object_or_404(Question, id=item['id'])
            # Проверяем, что пользователь имеет доступ к тесту
            if not request.user.is_staff and question.test.creator != request.user:
                raise PermissionDenied
            question.order = item['order']
            question.save()
            
        return JsonResponse({'success': True})
    except PermissionDenied:
        return JsonResponse({'success': False, 'error': 'У вас нет прав для изменения порядка вопросов'}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_POST
def copy_question(request, question_id):
    try:
        original_question = get_object_or_404(Question, id=question_id)
        # Проверяем права доступа
        if not request.user.is_staff and original_question.test.creator != request.user:
            raise PermissionDenied
            
        new_question = Question.objects.create(
            test=original_question.test,
            text=original_question.text,
            question_type=original_question.question_type,
            order=Question.objects.filter(test=original_question.test).count() + 1
        )
        
        # Копируем варианты ответов
        for option in original_question.options.all():
            AnswerOption.objects.create(
                question=new_question,
                text=option.text,
                is_correct=option.is_correct
            )
            
        return JsonResponse({'success': True})
    except PermissionDenied:
        return JsonResponse({'success': False, 'error': 'У вас нет прав для копирования вопросов'}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_POST
def delete_question(request, question_id):
    if request.method == 'POST':
        question = get_object_or_404(Question, id=question_id)
        try:
            question.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@require_http_methods(['GET'])
def preview_question(request, question_id):
    try:
        question = get_object_or_404(Question, id=question_id)
        # Проверяем права доступа
        if not request.user.is_staff and question.test.creator != request.user:
            raise PermissionDenied
        context = {
            'question': question,
            'options': question.options.all()
        }
        html = render_to_string('certification/question_preview.html', context)
        return JsonResponse({'html': html})
    except PermissionDenied:
        return JsonResponse({'success': False, 'error': 'У вас нет прав для просмотра этого вопроса'}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@staff_member_required
def edit_test(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    if request.method == 'POST':
        form = TestForm(request.POST, instance=test)
        if form.is_valid():
            form.save()
            messages.success(request, 'Тест успешно обновлен')
            return redirect('edit_test', test_id=test.id)
    else:
        form = TestForm(instance=test)
    
    # Получаем вопросы с предварительной загрузкой вариантов ответов
    questions = test.questions.prefetch_related('options').all()  # Используем сортировку по умолчанию из Meta
    
    return render(request, 'certification/edit_test.html', {
        'form': form,
        'test': test,
        'questions': questions
    })

@login_required
@user_passes_test(is_admin)
def export_test_statistics_pdf(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    attempts = TestResult.objects.filter(test=test).order_by('-completed_at')
    
    # Получаем уникальных пользователей, которые проходили тест
    users = User.objects.filter(testresult__test=test).distinct()
    users_data = [{
        'id': user.id,
        'name': user.get_full_name() or user.username
    } for user in users]

    # Получаем пользователей, которые не прошли тест
    failed_users = []
    for user in users:
        has_passed = attempts.filter(
            user=user,
            score__gte=test.passing_score
        ).exists()
        
        if not has_passed:
            last_attempt = attempts.filter(user=user).order_by('-completed_at').first()
            if last_attempt:
                failed_users.append({
                    'id': user.id,
                    'name': user.get_full_name() or user.username,
                    'last_attempt_date': last_attempt.completed_at,
                    'last_attempt_score': last_attempt.score,
                    'total_attempts': attempts.filter(user=user).count()
                })

    # Добавляем информацию о правильных ответах для каждой попытки
    for attempt in attempts:
        attempt.correct_answers = attempt.answers.filter(is_correct=True).count()
        attempt.total_questions = test.questions.count()

    # Подготавливаем данные для графиков
    # 1. График лучших результатов
    plt.figure(figsize=(10, 6))
    best_scores = []
    best_users = []
    for user in users:
        best_attempt = attempts.filter(user=user).order_by('-score').first()
        if best_attempt:
            best_scores.append(best_attempt.score)
            best_users.append(user.get_full_name() or user.username)
    
    plt.pie(best_scores, labels=best_users, autopct='%1.1f%%')
    plt.title('Лучшие результаты пользователей')
    plt.axis('equal')
    
    # Сохраняем график в base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    best_results_chart = base64.b64encode(buffer.getvalue()).decode()
    plt.close()

    # 2. График распределения результатов
    plt.figure(figsize=(10, 6))
    distribution_ranges = [
        (0, 20, '0-20%'),
        (20, 40, '20-40%'),
        (40, 60, '40-60%'),
        (60, 80, '60-80%'),
        (80, 101, '80-100%')
    ]
    
    distribution_data = []
    for start, end, label in distribution_ranges:
        count = attempts.filter(score__gte=start, score__lt=end).count()
        distribution_data.append({
            'range': label,
            'count': count
        })
    
    plt.pie([d['count'] for d in distribution_data], 
            labels=[d['range'] for d in distribution_data],
            autopct='%1.1f%%',
            colors=['#dc3545', '#ffc107', '#17a2b8', '#28a745', '#007bff'])
    plt.title('Распределение результатов')
    plt.axis('equal')
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    distribution_chart = base64.b64encode(buffer.getvalue()).decode()
    plt.close()

    # 3. Тепловая карта активности
    plt.figure(figsize=(15, 8))
    heatmap_data = [[0 for _ in range(52)] for _ in range(7)]
    
    end_date = timezone.now()
    start_date = end_date - timezone.timedelta(weeks=52)
    
    for attempt in attempts.filter(completed_at__gte=start_date):
        day_of_week = attempt.completed_at.weekday()
        week_number = (end_date - attempt.completed_at).days // 7
        if 0 <= week_number < 52:
            heatmap_data[day_of_week][week_number] += 1
    
    sns.heatmap(heatmap_data, cmap='YlGn', cbar_kws={'label': 'Количество попыток'})
    plt.title('Активность прохождения теста')
    plt.xlabel('Неделя')
    plt.ylabel('День недели')
    plt.yticks(range(7), ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'])
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    heatmap_chart = base64.b64encode(buffer.getvalue()).decode()
    plt.close()

    # Подготавливаем контекст для шаблона
    context = {
        'test': test,
        'attempts': attempts,
        'average_score': attempts.aggregate(Avg('score'))['score__avg'] or 0,
        'best_score': attempts.aggregate(Max('score'))['score__max'] or 0,
        'total_attempts': attempts.count(),
        'failed_users': failed_users,
        'best_results_chart': best_results_chart,
        'distribution_chart': distribution_chart,
        'heatmap_chart': heatmap_chart,
        'now': timezone.now(),
    }

    # Рендерим HTML
    template = get_template('certification/test_statistics_pdf.html')
    html_string = template.render(context)

    # Создаем PDF
    html = HTML(string=html_string)
    pdf = html.write_pdf()

    # Создаем ответ
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="test_statistics_{test.id}.pdf"'
    
    return response
