from django.urls import path
from . import views

urlpatterns = [
    # 公共
    path('', views.index, name='index'),
    path('login/', views.user_login, name='login'),
    path('register/', views.user_register, name='register'),
    path('logout/', views.user_logout, name='logout'),
    path('setup/', views.admin_setup, name='admin_setup'),

    # 儿童端
    path('child/', views.child_dashboard, name='child_dashboard'),
    path('child/register/', views.register_child, name='register_child'),
    path('child/submit-task/<int:task_id>/', views.child_submit_task, name='child_submit_task'),
    path('child/encouragement/<int:encouragement_id>/read/', views.child_mark_encouragement_read, name='child_mark_encouragement_read'),
    path('child/meal-history/', views.child_meal_history, name='child_meal_history'),
    path('child/badges/', views.child_badges, name='child_badges'),
    path('child/update-avatar/', views.child_update_avatar, name='child_update_avatar'),

    # YOLO 膳食识别 API (预留接口)
    path('api/yolo/recognize/', views.yolo_recognize_food, name='yolo_recognize_food'),

    # 家长端
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    path('parent/switch-child/', views.parent_switch_child, name='parent_switch_child'),
    path('parent/confirm-task/<int:record_id>/', views.parent_confirm_task, name='parent_confirm_task'),
    path('parent/add-manual-task/', views.parent_add_manual_task, name='parent_add_manual_task'),
    path('parent/send-encouragement/', views.parent_send_encouragement, name='parent_send_encouragement'),
    path('parent/correct-meal/<int:meal_id>/', views.parent_correct_meal, name='parent_correct_meal'),
    path('parent/recipes/', views.parent_recipes, name='parent_recipes'),
    path('parent/meal-report/', views.parent_meal_report, name='parent_meal_report'),
    path('parent/add-to-class/', views.parent_add_to_class, name='parent_add_to_class'),
    path('parent/get-teachers/', views.parent_get_teachers, name='parent_get_teachers'),
    path('parent/bind-child/', views.parent_bind_child, name='parent_bind_child'),

    # 学校端
    path('school/', views.school_dashboard, name='school_dashboard'),
    path('school/create-activity/', views.school_create_activity, name='school_create_activity'),
    path('school/create-challenge/', views.school_create_challenge, name='school_create_challenge'),
    path('school/class-stats/', views.school_class_stats, name='school_class_stats'),
]
