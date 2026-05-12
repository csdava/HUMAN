from django.urls import path
from . import views

urlpatterns = [
    # 公共
    path('', views.index, name='index'),
    path('login/', views.user_login, name='login'),
    path('register/', views.user_register, name='register'),
    path('logout/', views.user_logout, name='logout'),
    path('setup/', views.admin_setup, name='admin_setup'),

    # 儿童端（建议仅由负责儿童端的同事修改本块）
    path('child/', views.child_dashboard, name='child_dashboard'),
    path('child/register/', views.register_child, name='register_child'),
    path('child/submit-task/<int:task_id>/', views.child_submit_task, name='child_submit_task'),
    path('child/encouragement/<int:encouragement_id>/read/', views.child_mark_encouragement_read, name='child_mark_encouragement_read'),
    path('child/meal-history/', views.child_meal_history, name='child_meal_history'),
    path('child/alerts/', views.child_health_alerts, name='child_health_alerts'),
    path('child/alerts/<int:alert_id>/read/', views.child_mark_alert_read, name='child_mark_alert_read'),
    path('child/recommended-intake/', views.child_recommended_intake, name='child_recommended_intake'),
    path('child/badges/', views.child_badges, name='child_badges'),
    path('child/update-avatar/', views.child_update_avatar, name='child_update_avatar'),

    # YOLO 膳食识别 API (预留接口)
    path('api/yolo/recognize/', views.yolo_recognize_food, name='yolo_recognize_food'),

    # 健康数据 API（供Android App调用）
    path('api/health/sync/', views.health_sync, name='health_sync'),
    path('api/health/manual-input/', views.health_manual_input, name='health_manual_input'),
    path('api/health/auto-generate/', views.health_auto_generate, name='health_auto_generate'),
    path('api/health/latest/', views.health_latest, name='health_latest'),
    path('api/health/history/', views.health_history, name='health_history'),
    path('api/health/today/', views.health_today, name='health_today'),

    # 家长端（建议仅由负责家长端的同事修改本块，避免与儿童端/学校端冲突）
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    path('parent/switch-child/', views.parent_switch_child, name='parent_switch_child'),
    path('parent/confirm-task/<int:record_id>/', views.parent_confirm_task, name='parent_confirm_task'),
    path('parent/add-manual-task/', views.parent_add_manual_task, name='parent_add_manual_task'),
    path('parent/send-encouragement/', views.parent_send_encouragement, name='parent_send_encouragement'),
    path('parent/correct-meal/<int:meal_id>/', views.parent_correct_meal, name='parent_correct_meal'),
    path('parent/meal/<int:meal_id>/detail/', views.parent_meal_detail, name='parent_meal_detail'),
    path('parent/food-materials/', views.parent_food_materials, name='parent_food_materials'),
    path('parent/meal-list/', views.parent_meal_list, name='parent_meal_list'),
    path('parent/child-diet-notes/', views.parent_child_diet_notes, name='parent_child_diet_notes'),
    path('parent/child-birth-date/', views.parent_child_birth_date, name='parent_child_birth_date'),
    path('parent/child-health-tags/', views.parent_child_health_tags, name='parent_child_health_tags'),
    path('parent/recommended-intake/', views.parent_child_recommended_intake, name='parent_child_recommended_intake'),
    path('parent/alerts/', views.parent_health_alerts, name='parent_health_alerts'),
    path('parent/alerts/<int:alert_id>/read/', views.parent_mark_alert_read, name='parent_mark_alert_read'),
    path('parent/recipes/', views.parent_recipes, name='parent_recipes'),
    path('parent/recipes/add/', views.parent_recipe_create, name='parent_recipe_create'),
    path('parent/meal-report/', views.parent_meal_report, name='parent_meal_report'),
    path('parent/export-weekly-pdf/', views.parent_export_weekly_pdf, name='parent_export_weekly_pdf'),
    path('parent/add-to-class/', views.parent_add_to_class, name='parent_add_to_class'),
    path('parent/child-class/', views.parent_set_child_class, name='parent_set_child_class'),
    path('parent/get-teachers/', views.parent_get_teachers, name='parent_get_teachers'),
    path('parent/bind-child/', views.parent_bind_child, name='parent_bind_child'),

    # 学校端（建议仅由负责学校端的同事修改本块）
    path('school/', views.school_dashboard, name='school_dashboard'),
    path('school/export-weekly-pdf/', views.school_export_weekly_pdf, name='school_export_weekly_pdf'),
    path('school/alerts/', views.school_health_alerts, name='school_health_alerts'),
    path('school/alerts/<int:alert_id>/read/', views.school_mark_alert_read, name='school_mark_alert_read'),
    path('school/create-activity/', views.school_create_activity, name='school_create_activity'),
    path('school/create-challenge/', views.school_create_challenge, name='school_create_challenge'),
    path('school/class-stats/', views.school_class_stats, name='school_class_stats'),
    path('school/challenge/<int:pk>/stats/', views.school_challenge_stats, name='school_challenge_stats'),
    path('school/challenge/<int:pk>/finalize/', views.school_challenge_finalize, name='school_challenge_finalize'),
    path('school/resource/create/', views.school_resource_create, name='school_resource_create'),
    path('school/resource/<int:pk>/push/', views.school_resource_push, name='school_resource_push'),
    path('school/resource/resync/', views.school_resource_resync, name='school_resource_resync'),
    path('school/message/create/', views.school_message_create, name='school_message_create'),
    path('school/archive/create/', views.school_archive_create, name='school_archive_create'),
]
