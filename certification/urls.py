from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('test/create/', views.create_test, name='create_test'),
    path('test/<int:test_id>/add-question/', views.add_question, name='add_question'),
    path('test/<int:test_id>/', views.test_detail, name='test_detail'),
    path('test/<int:test_id>/edit/', views.edit_test, name='edit_test'),
    path('test/<int:test_id>/statistics/', views.test_statistics, name='test_statistics'),
    path('test/<int:test_id>/copy/', views.copy_test, name='copy_test'),
    path('test/<int:test_id>/export/', views.export_test, name='export_test'),
    path('test/import/', views.import_test, name='import_test'),
    path('test/<int:test_id>/toggle/', views.toggle_test_status, name='toggle_test_status'),
    path('test/<int:test_id>/delete/', views.delete_test, name='delete_test'),
    path('test/<int:test_id>/result/<int:result_id>/', views.test_result, name='test_result'),
    path('test/<int:test_id>/attempt/<int:attempt_id>/details/', views.attempt_details, name='attempt_details'),
    path('users/', views.manage_users, name='manage_users'),
    
    # API endpoints для работы с вопросами
    path('api/questions/reorder/', views.reorder_questions, name='reorder_questions'),
    path('api/questions/<int:question_id>/copy/', views.copy_question, name='copy_question'),
    path('api/questions/<int:question_id>/delete/', views.delete_question, name='delete_question'),
    path('api/questions/<int:question_id>/preview/', views.preview_question, name='preview_question'),
    path('test/<int:test_id>/statistics/export-pdf/', views.export_test_statistics_pdf, name='export_test_statistics_pdf'),
] 