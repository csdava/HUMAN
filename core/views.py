import hashlib
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Count, Q, Sum, Avg
from datetime import timedelta
from .models import (
    Child, Task, TaskRecord, Encouragement, Teacher, ClassStudent, Activity,
    FoodMaterial, MealRecord, MealFoodItem, Badge, ChildBadge, Recipe,
    HealthAlert, HealthChallenge, ChallengeProgress, School, HealthData,
    HealthCourseResource, HealthResourceUnlock,
    SchoolHomeMessage, SchoolHealthArchive,
)


def is_parent(user):
    return user.is_authenticated and user.children.exists()


def is_teacher(user):
    return user.is_authenticated and Teacher.objects.filter(user=user).exists()


# ========== 公共视图 ==========

def index(request):
    """首页，选择角色"""
    return render(request, 'index.html')


def user_login(request):
    """登录视图"""
    role_names = {'parent': '家长登录', 'teacher': '教师登录', 'child': '儿童登录'}
    selected_role = request.GET.get('role', '')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            # 优先使用表单中提交的角色
            if role == 'teacher':
                return redirect('school_dashboard')
            elif role == 'parent':
                return redirect('parent_dashboard')
            elif role == 'child':
                # 检查是否是与儿童账户关联的用户
                # 儿童账户有user字段指向登录的用户，parent字段指向关联的家长
                child_account = Child.objects.filter(user=user).first()
                if child_account:
                    return redirect('child_dashboard')
                else:
                    logout(request)
                    return render(request, 'registration/login.html', {
                        'error': '此账户不是儿童账户，请选择正确的身份登录',
                        'selected_role': '',
                        'role_names': role_names
                    })
            else:
                if Teacher.objects.filter(user=user).exists():
                    return redirect('school_dashboard')
                elif user.children.exists():
                    return redirect('parent_dashboard')
                elif hasattr(user, 'child_profile'):
                    return redirect('child_dashboard')
                else:
                    return render(request, 'registration/login.html', {
                        'error': '账户类型不明确，请重新选择身份登录',
                        'selected_role': '',
                        'role_names': role_names
                    })
        return render(request, 'registration/login.html', {'error': '用户名或密码错误', 'selected_role': role, 'role_names': role_names})
    return render(request, 'registration/login.html', {'selected_role': selected_role, 'role_names': role_names})


def user_register(request):
    """注册视图"""
    role = request.GET.get('role', 'parent')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role')

        if User.objects.filter(username=username).exists():
            return render(request, 'registration/register.html', {
                'error': '用户名已存在',
                'role': role
            })

        user = User.objects.create_user(username=username, password=password)

        if role == 'child':
            child = Child.objects.create(
                name=request.POST.get('child_name', ''),
                nickname=request.POST.get('nickname', username),
                gender=request.POST.get('gender', 'M'),
                user=user,
                parent=None  # 暂时不关联家长，等家长绑定
            )
            bind_code = child.generate_bind_code()
            for code, name in Task.TASK_TYPES:
                Task.objects.get_or_create(
                    code=code,
                    defaults={'name': name, 'power_reward': 10, 'icon': '⭐'}
                )
            return render(request, 'registration/child_register_success.html', {
                'child': child,
                'bind_code': bind_code
            })

        elif role == 'parent':
            # 家长注册不再自动绑定儿童
            # 家长登录后可在家长端通过绑定码功能绑定儿童
            return redirect('login')

        elif role == 'teacher':
            school_name = request.POST.get('school_name', '').strip()
            class_name = request.POST.get('class_name', '').strip()

            if not school_name or not class_name:
                return render(request, 'registration/register.html', {
                    'error': '学校名称和班级名称不能为空',
                    'role': role
                })

            school, _ = School.objects.get_or_create(name=school_name)
            Teacher.objects.create(
                user=user,
                school=school,
                class_name=class_name
            )
            return redirect('login')

        return redirect('login')

    return render(request, 'registration/register.html', {
        'role': role
    })


def user_logout(request):
    logout(request)
    return redirect('index')


# ========== 儿童端视图 ==========


def _intake_and_tags_for_child(child: Child) -> dict:
    """与家长端 `parent_child_recommended_intake` 同源的参考摄入 + 家庭维护标签（只读展示用）。"""
    from .nutrition import recommend_intake_for_age

    age = child.age_years()
    rec = recommend_intake_for_age(age)
    return {
        'age_years': age,
        'recommendation': None
        if rec is None
        else {
            'calories_kcal_min': rec.calories_kcal_min,
            'calories_kcal_max': rec.calories_kcal_max,
            'protein_g_min': rec.protein_g_min,
            'protein_g_max': rec.protein_g_max,
            'notes': rec.notes,
        },
        'allergy_tags': list(child.allergy_tags or []),
        'medical_tags': list(child.medical_tags or []),
    }


@login_required
def child_dashboard(request):
    """儿童端首页"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return render(request, 'child/dashboard.html', {
            'error': '未找到关联的儿童账户',
            'child': None,
            'today': timezone.now().date(),
            'daily_records': [],
            'encouragements': [],
            'latest_encouragement': None,
            'progress_percent': 0,
            'today_meals': [],
            'badges': [],
            'active_challenges': [],
            'family_health_readonly': None,
        })

    if not child.bind_code:
        child.generate_bind_code()

    today = timezone.now().date()
    tasks = Task.objects.all()

    task_records = TaskRecord.objects.filter(child=child, date=today)
    task_status = {tr.task.code: tr.status for tr in task_records}

    daily_records = []
    for task in tasks:
        status = task_status.get(task.code, 'pending')
        record, created = TaskRecord.objects.get_or_create(
            child=child, task=task, date=today,
            defaults={'status': 'pending'}
        )
        if created:
            status = 'pending'
        else:
            status = record.status
        daily_records.append({
            'task': task,
            'record': record,
            'status': status
        })

    encouragements = Encouragement.objects.filter(
        child=child, is_read=False
    ).order_by('-created_at')[:5]

    latest_encouragement = encouragements.first()

    progress_percent = int((child.power / child.power_to_next) * 100)

    today_meals = MealRecord.objects.filter(child=child, date=today).prefetch_related('food_items__food')
    today_meal_totals = {'kcal': 0.0, 'protein': 0.0, 'carb': 0.0, 'fat': 0.0, 'count': 0}
    for m in today_meals:
        today_meal_totals['kcal'] += float(m.total_calories or 0)
        today_meal_totals['protein'] += float(m.total_protein or 0)
        today_meal_totals['carb'] += float(m.total_carbohydrate or 0)
        today_meal_totals['fat'] += float(m.total_fat or 0)
        today_meal_totals['count'] += 1

    badges = ChildBadge.objects.filter(child=child).select_related('badge')[:5]

    active_challenges = []
    for progress in ChallengeProgress.objects.filter(child=child, is_completed=False).select_related('challenge'):
        if progress.challenge.status == 'active':
            progress.percent = int(progress.current_value / progress.challenge.target_value * 100)
            active_challenges.append(progress)

    family_health = _intake_and_tags_for_child(child)
    family_health['today_meal_totals'] = today_meal_totals

    allergy_tags = child.allergy_tags or []
    for meal in today_meals:
        meal.allergy_hits = []
        if allergy_tags:
            food_names = [str(fi.food.name) for fi in meal.food_items.all()]
            for tag in allergy_tags:
                tag = (str(tag) or "").strip()
                if not tag:
                    continue
                for fname in food_names:
                    if tag in fname:
                        meal.allergy_hits.append({'tag': tag, 'food': fname})
                        break

    return render(request, 'child/dashboard.html', {
        'child': child,
        'today': today,
        'daily_records': daily_records,
        'encouragements': encouragements,
        'latest_encouragement': latest_encouragement,
        'progress_percent': progress_percent,
        'today_meals': today_meals,
        'today_meal_totals': today_meal_totals,
        'badges': badges,
        'active_challenges': active_challenges,
        'family_health_readonly': family_health,
    })


@login_required
@require_http_methods(["POST"])
def child_submit_task(request, task_id):
    """儿童提交任务申请"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    task = get_object_or_404(Task, id=task_id)
    today = timezone.now().date()

    record, created = TaskRecord.objects.get_or_create(
        child=child, task=task, date=today,
        defaults={'status': 'pending'}
    )

    if record.status != 'pending':
        return JsonResponse({'success': False, 'message': '任务状态不允许提交'})

    return JsonResponse({'success': True, 'message': '已提交，等家长确认哦~'})


@login_required
@require_http_methods(["POST"])
def child_mark_encouragement_read(request, encouragement_id):
    """标记鼓励语已读"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'}, status=400)
    encouragement = get_object_or_404(Encouragement, id=encouragement_id, child=child)
    encouragement.is_read = True
    encouragement.save()
    return JsonResponse({'success': True})


@login_required
def register_child(request):
    """注册孩子"""
    if request.method == 'POST':
        name = request.POST.get('name')
        nickname = request.POST.get('nickname')
        gender = request.POST.get('gender')

        child = Child.objects.create(
            name=name,
            nickname=nickname,
            gender=gender,
            parent=request.user
        )
        child.generate_bind_code()

        for code, name in Task.TASK_TYPES:
            task = Task.objects.get_or_create(
                code=code,
                defaults={'name': name, 'power_reward': 10, 'icon': '⭐'}
            )[0]

        return redirect('child_dashboard')

    return render(request, 'child/register.html')


# ========== YOLO 膳食识别 API ==========

# YOLO 类别到食材类别的映射（蔬菜模型）
YOLO_CLASS_TO_FOOD = {
    'avocado': {'name': '牛油果', 'category': 'fruit', 'color': 'blue', 'protein': 2.0, 'carbohydrate': 9.0, 'fat': 15.0, 'calories': 160},
    'beans': {'name': '豆角', 'category': 'vegetable', 'color': 'green', 'protein': 2.0, 'carbohydrate': 7.0, 'fat': 0.1, 'calories': 31},
    'beet': {'name': '甜菜', 'category': 'vegetable', 'color': 'green', 'protein': 1.6, 'carbohydrate': 10.0, 'fat': 0.1, 'calories': 43},
    'bell pepper': {'name': '甜椒', 'category': 'vegetable', 'color': 'green', 'protein': 1.0, 'carbohydrate': 6.0, 'fat': 0.3, 'calories': 26},
    'broccoli': {'name': '西兰花', 'category': 'vegetable', 'color': 'green', 'protein': 2.8, 'carbohydrate': 6.6, 'fat': 0.4, 'calories': 34},
    'brus capusta': {'name': '白菜', 'category': 'vegetable', 'color': 'green', 'protein': 1.5, 'carbohydrate': 3.0, 'fat': 0.1, 'calories': 17},
    'cabbage': {'name': '卷心菜', 'category': 'vegetable', 'color': 'green', 'protein': 1.3, 'carbohydrate': 5.0, 'fat': 0.1, 'calories': 25},
    'carrot': {'name': '胡萝卜', 'category': 'vegetable', 'color': 'green', 'protein': 0.9, 'carbohydrate': 10.0, 'fat': 0.2, 'calories': 41},
    'cayliflower': {'name': '花菜', 'category': 'vegetable', 'color': 'green', 'protein': 2.1, 'carbohydrate': 5.0, 'fat': 0.3, 'calories': 25},
    'celery': {'name': '芹菜', 'category': 'vegetable', 'color': 'green', 'protein': 0.7, 'carbohydrate': 3.0, 'fat': 0.2, 'calories': 14},
    'corn': {'name': '玉米', 'category': 'grain', 'color': 'red', 'protein': 3.4, 'carbohydrate': 22.0, 'fat': 1.2, 'calories': 96},
    'cucumber': {'name': '黄瓜', 'category': 'vegetable', 'color': 'green', 'protein': 0.7, 'carbohydrate': 2.0, 'fat': 0.1, 'calories': 12},
    'eggplant': {'name': '茄子', 'category': 'vegetable', 'color': 'green', 'protein': 1.0, 'carbohydrate': 5.0, 'fat': 0.1, 'calories': 22},
    'fasol': {'name': '芸豆', 'category': 'protein', 'color': 'yellow', 'protein': 8.0, 'carbohydrate': 22.0, 'fat': 0.5, 'calories': 123},
    'garlic': {'name': '大蒜', 'category': 'vegetable', 'color': 'green', 'protein': 6.0, 'carbohydrate': 33.0, 'fat': 0.5, 'calories': 149},
    'hot pepper': {'name': '辣椒', 'category': 'vegetable', 'color': 'green', 'protein': 1.0, 'carbohydrate': 5.0, 'fat': 0.4, 'calories': 21},
    'onion': {'name': '洋葱', 'category': 'vegetable', 'color': 'green', 'protein': 1.0, 'carbohydrate': 9.0, 'fat': 0.1, 'calories': 40},
    'peas': {'name': '豌豆', 'category': 'vegetable', 'color': 'green', 'protein': 5.0, 'carbohydrate': 14.0, 'fat': 0.4, 'calories': 81},
    'potato': {'name': '土豆', 'category': 'grain', 'color': 'red', 'protein': 2.0, 'carbohydrate': 17.0, 'fat': 0.1, 'calories': 77},
    'pumpkin': {'name': '南瓜', 'category': 'vegetable', 'color': 'green', 'protein': 1.0, 'carbohydrate': 6.0, 'fat': 0.1, 'calories': 26},
    'rediska': {'name': '小红萝卜', 'category': 'vegetable', 'color': 'green', 'protein': 0.9, 'carbohydrate': 3.0, 'fat': 0.1, 'calories': 16},
    'redka': {'name': '红菜头', 'category': 'vegetable', 'color': 'green', 'protein': 1.6, 'carbohydrate': 10.0, 'fat': 0.1, 'calories': 43},
    'salad': {'name': '生菜', 'category': 'vegetable', 'color': 'green', 'protein': 1.3, 'carbohydrate': 2.0, 'fat': 0.3, 'calories': 15},
    'squash-patisson': {'name': '西葫芦', 'category': 'vegetable', 'color': 'green', 'protein': 1.2, 'carbohydrate': 4.0, 'fat': 0.2, 'calories': 18},
    'tomato': {'name': '番茄', 'category': 'vegetable', 'color': 'green', 'protein': 0.9, 'carbohydrate': 4.0, 'fat': 0.2, 'calories': 19},
    'vegetable marrow': {'name': '节瓜', 'category': 'vegetable', 'color': 'green', 'protein': 0.7, 'carbohydrate': 3.0, 'fat': 0.1, 'calories': 13},
}

# YOLO 水果模型类别映射
YOLO_FRUIT_CLASS_TO_FOOD = {
    'Blueberries': {'name': '蓝莓', 'category': 'fruit', 'color': 'blue', 'protein': 0.7, 'carbohydrate': 14.0, 'fat': 0.3, 'calories': 57},
    'Hami Melon': {'name': '哈密瓜', 'category': 'fruit', 'color': 'orange', 'protein': 0.5, 'carbohydrate': 8.0, 'fat': 0.1, 'calories': 34},
    'Mango': {'name': '芒果', 'category': 'fruit', 'color': 'orange', 'protein': 0.8, 'carbohydrate': 15.0, 'fat': 0.4, 'calories': 65},
    'Sakya fruit': {'name': '释迦果', 'category': 'fruit', 'color': 'green', 'protein': 1.0, 'carbohydrate': 23.0, 'fat': 0.3, 'calories': 94},
    'apple': {'name': '苹果', 'category': 'fruit', 'color': 'red', 'protein': 0.3, 'carbohydrate': 14.0, 'fat': 0.2, 'calories': 52},
    'banana': {'name': '香蕉', 'category': 'fruit', 'color': 'yellow', 'protein': 1.1, 'carbohydrate': 23.0, 'fat': 0.3, 'calories': 89},
    'grape': {'name': '葡萄', 'category': 'fruit', 'color': 'purple', 'protein': 0.6, 'carbohydrate': 17.0, 'fat': 0.3, 'calories': 67},
    'guava': {'name': '番石榴', 'category': 'fruit', 'color': 'green', 'protein': 2.6, 'carbohydrate': 14.0, 'fat': 1.0, 'calories': 68},
    'mangosteen': {'name': '山竹', 'category': 'fruit', 'color': 'purple', 'protein': 0.4, 'carbohydrate': 18.0, 'fat': 0.6, 'calories': 73},
    'orange': {'name': '橙子', 'category': 'fruit', 'color': 'orange', 'protein': 0.9, 'carbohydrate': 12.0, 'fat': 0.1, 'calories': 47},
    'pear': {'name': '梨', 'category': 'fruit', 'color': 'yellow', 'protein': 0.3, 'carbohydrate': 15.0, 'fat': 0.1, 'calories': 51},
    'pineapple': {'name': '菠萝', 'category': 'fruit', 'color': 'yellow', 'protein': 0.5, 'carbohydrate': 13.0, 'fat': 0.1, 'calories': 50},
    'pitaya': {'name': '火龙果', 'category': 'fruit', 'color': 'red', 'protein': 1.1, 'carbohydrate': 13.0, 'fat': 0.2, 'calories': 60},
    'strawberry': {'name': '草莓', 'category': 'fruit', 'color': 'red', 'protein': 0.7, 'carbohydrate': 8.0, 'fat': 0.3, 'calories': 33},
    'tomato': {'name': '番茄', 'category': 'vegetable', 'color': 'green', 'protein': 0.9, 'carbohydrate': 4.0, 'fat': 0.2, 'calories': 19},
    'watermelon': {'name': '西瓜', 'category': 'fruit', 'color': 'red', 'protein': 0.6, 'carbohydrate': 8.0, 'fat': 0.2, 'calories': 30},
}

# 默认食材数据（用于未映射的类别）
DEFAULT_FOOD_DATA = {
    'grain': {'name': '主食', 'category': 'grain', 'color': 'red', 'protein': 2.5, 'carbohydrate': 25.0, 'fat': 0.5, 'calories': 110},
    'protein': {'name': '蛋白质', 'category': 'protein', 'color': 'yellow', 'protein': 20.0, 'carbohydrate': 0.5, 'fat': 3.0, 'calories': 100},
    'vegetable': {'name': '蔬菜', 'category': 'vegetable', 'color': 'green', 'protein': 1.5, 'carbohydrate': 3.0, 'fat': 0.2, 'calories': 20},
    'fruit': {'name': '水果', 'category': 'fruit', 'color': 'blue', 'protein': 0.5, 'carbohydrate': 12.0, 'fat': 0.3, 'calories': 50},
    'dairy': {'name': '乳制品', 'category': 'dairy', 'color': 'purple', 'protein': 3.0, 'carbohydrate': 5.0, 'fat': 3.0, 'calories': 60},
}


@login_required
@require_http_methods(["POST"])
def yolo_recognize_food(request):
    """
    YOLO 膳食识别接口 - 实际接入 YOLO 模型
    前端上传图片，后端调用 YOLO 模型进行识别
    识别完成后返回食材列表和营养分析
    """
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    meal_type = request.POST.get('meal_type', 'lunch')
    today = timezone.now().date()

    # 获取上传的图片
    image = request.FILES.get('image')
    if not image:
        return JsonResponse({'success': False, 'message': '请上传图片'})

    # 保存图片到临时文件
    import os
    import tempfile
    import logging
    from django.conf import settings

    logger = logging.getLogger(__name__)

    # 创建临时文件保存上传的图片
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
        for chunk in image.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    logger.warning(f"[YOLO] Temp file: {tmp_path}, size: {os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 'N/A'}")

    try:
        # 调用 YOLO 模型进行识别
        from ultralytics import YOLO
        import logging
        logger = logging.getLogger(__name__)

        # 模型路径
        vegetable_model_path = 'D:/User/Documents/PycharmProjects/human/runs/vegetable_train_v2/weights/last.pt'
        fruit_model_path = 'D:/User/Documents/PycharmProjects/human/runs/fruit_train/weights/best.pt'

        # 检查是否有可用模型
        has_vegetable_model = os.path.exists(vegetable_model_path)
        has_fruit_model = os.path.exists(fruit_model_path)

        logger.warning(f"[YOLO] Vegetable model exists: {has_vegetable_model}, Fruit model exists: {has_fruit_model}")

        if not has_vegetable_model and not has_fruit_model:
            # 模型文件都不存在，使用模拟数据
            recognized_foods = [
                DEFAULT_FOOD_DATA['grain'],
                DEFAULT_FOOD_DATA['vegetable'],
                DEFAULT_FOOD_DATA['protein'],
            ]
        else:
            # 合并两个模型的识别结果
            all_recognized_foods = []

            # 蔬菜模型识别（降低置信度阈值以检测更多食材）
            if has_vegetable_model:
                model = YOLO(vegetable_model_path)
                results = model.predict(source=tmp_path, imgsz=640, conf=0.15, verbose=False)
                logger.warning(f"[YOLO] Vegetable model results: {len(results) if results else 0}")
                if results and len(results) > 0:
                    result = results[0]
                    logger.warning(f"[YOLO] Vegetable model result.names: {result.names}")
                    boxes = result.boxes
                    logger.warning(f"[YOLO] Boxes object: {boxes}, is None: {boxes is None}")
                    if boxes is not None:
                        boxes_len = len(boxes)
                        logger.warning(f"[YOLO] Boxes length: {boxes_len}")
                        if boxes_len > 0:
                            class_ids = boxes.cls.cpu().numpy().astype(int)
                            confidences = boxes.conf.cpu().numpy()
                            logger.warning(f"[YOLO] Class IDs: {class_ids}, Confidences: {confidences}")
                            for class_id, conf in zip(class_ids, confidences):
                                if class_id < len(result.names):
                                    class_name = result.names[class_id]
                                    logger.warning(f"[YOLO] Detected class: {class_name} (id={class_id}, conf={conf})")
                                    # 首先检查是否在蔬菜模型映射中
                                    if class_name in YOLO_CLASS_TO_FOOD:
                                        food_data = YOLO_CLASS_TO_FOOD[class_name]
                                        all_recognized_foods.append({
                                            'name': food_data['name'],
                                            'category': food_data['category'],
                                            'color': food_data['color'],
                                            'confidence': float(conf),
                                            'protein': food_data['protein'],
                                            'carbohydrate': food_data['carbohydrate'],
                                            'fat': food_data['fat'],
                                            'calories': food_data['calories'],
                                            'source': 'vegetable'
                                        })
                                    else:
                                        # 不在蔬菜映射中，检查水果映射
                                        if class_name in YOLO_FRUIT_CLASS_TO_FOOD:
                                            food_data = YOLO_FRUIT_CLASS_TO_FOOD[class_name]
                                            all_recognized_foods.append({
                                                'name': food_data['name'],
                                                'category': food_data['category'],
                                                'color': food_data['color'],
                                                'confidence': float(conf),
                                                'protein': food_data['protein'],
                                                'carbohydrate': food_data['carbohydrate'],
                                                'fat': food_data['fat'],
                                                'calories': food_data['calories'],
                                                'source': 'fruit'
                                            })
                                        else:
                                            # 完全未映射，记录并使用默认数据
                                            logger.warning(f"[YOLO] Unknown class '{class_name}', not in any mapping")
                        else:
                            logger.warning("[YOLO] Vegetable model detected 0 boxes")
                    else:
                        logger.warning("[YOLO] Vegetable model boxes is None")

            # 水果模型识别
            if has_fruit_model:
                model = YOLO(fruit_model_path)
                results = model.predict(source=tmp_path, imgsz=640, conf=0.25, verbose=False)
                if results and len(results) > 0:
                    result = results[0]
                    if result.boxes is not None and len(result.boxes) > 0:
                        boxes = result.boxes
                        class_ids = boxes.cls.cpu().numpy().astype(int)
                        confidences = boxes.conf.cpu().numpy()
                        for class_id, conf in zip(class_ids, confidences):
                            if class_id < len(result.names):
                                class_name = result.names[class_id]
                                if class_name in YOLO_FRUIT_CLASS_TO_FOOD:
                                    food_data = YOLO_FRUIT_CLASS_TO_FOOD[class_name]
                                    all_recognized_foods.append({
                                        'name': food_data['name'],
                                        'category': food_data['category'],
                                        'color': food_data['color'],
                                        'confidence': float(conf),
                                        'protein': food_data['protein'],
                                        'carbohydrate': food_data['carbohydrate'],
                                        'fat': food_data['fat'],
                                        'calories': food_data['calories'],
                                        'source': 'fruit'
                                    })

            # 去重（按食材名称去重，保留高置信度结果）
            unique_foods = {}
            for food in all_recognized_foods:
                key = food['name']
                if key not in unique_foods or food['confidence'] > unique_foods[key]['confidence']:
                    unique_foods[key] = food

            recognized_foods = list(unique_foods.values())

            # 如果没有识别到任何食材，记录警告并使用默认数据
            if not recognized_foods:
                logger.warning("[YOLO] No foods recognized from models. All recognized: " + str(all_recognized_foods))
                recognized_foods = [
                    DEFAULT_FOOD_DATA['grain'],
                    DEFAULT_FOOD_DATA['vegetable'],
                    DEFAULT_FOOD_DATA['protein'],
                ]
            else:
                logger.warning(f"[YOLO] Recognized {len(recognized_foods)} foods: {[f['name'] for f in recognized_foods]}")

    except Exception as e:
        import sys
        import traceback
        print(f"YOLO识别错误: {e}")
        traceback.print_exc()
        # 检查是否是 torch 缺失问题
        if 'torch' in str(e) or 'cuda' in str(e).lower():
            print(f"[YOLO] Torch/CUDA error - torch may not be installed in Python {sys.version}")
        # 识别失败时使用模拟数据
        recognized_foods = [
            DEFAULT_FOOD_DATA['grain'],
            DEFAULT_FOOD_DATA['vegetable'],
            DEFAULT_FOOD_DATA['protein'],
        ]

    finally:
        # 删除临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # 创建膳食记录（如果当天已存在则更新）
    meal_record, created = MealRecord.objects.get_or_create(
        child=child,
        date=today,
        meal_type=meal_type,
        defaults={'is_verified': False}
    )

    # 清空原有食材（如果是更新）
    if not created:
        meal_record.food_items.all().delete()

    # 计算营养成分并保存食材
    total_calories = 0
    total_protein = 0
    total_carbohydrate = 0
    total_fat = 0
    weight = 100  # 默认每个食材100g

    # 重置宝石状态（按当天重新计算）
    child.gem_red = False
    child.gem_yellow = False
    child.gem_green = False
    child.gem_blue = False
    child.gem_purple = False
    child.save()

    for food_data in recognized_foods:
        # 创建或获取食材记录
        food, created = FoodMaterial.objects.get_or_create(
            name=food_data['name'],
            defaults={
                'category': food_data['category'],
                'color': food_data['color'],
                'protein': food_data['protein'],
                'carbohydrate': food_data['carbohydrate'],
                'fat': food_data['fat'],
                'calories': food_data['calories'],
                'yolo_class': food_data['name'],
            }
        )

        MealFoodItem.objects.create(
            meal_record=meal_record,
            food=food,
            weight=weight
        )

        # 累加营养
        total_protein += food.protein * weight / 100
        total_carbohydrate += food.carbohydrate * weight / 100
        total_fat += food.fat * weight / 100
        total_calories += food.calories * weight / 100

        # 点亮对应颜色宝石
        child.check_gem_color(food.category)

    meal_record.total_protein = total_protein
    meal_record.total_carbohydrate = total_carbohydrate
    meal_record.total_fat = total_fat
    meal_record.total_calories = total_calories
    meal_record.save()

    # 计算五色评分
    score = 0
    if child.gem_red:
        score += 1
    if child.gem_yellow:
        score += 1
    if child.gem_green:
        score += 1
    if child.gem_blue:
        score += 1
    if child.gem_purple:
        score += 1
    meal_record.total_score = score
    meal_record.save()

    # ========== 过敏预警（结构化标签）==========
    allergy_hits = []
    try:
        tags = child.allergy_tags or []
        if not isinstance(tags, list):
            tags = []
        food_names = [str(fi.food.name) for fi in meal_record.food_items.all()]
        for t in tags:
            t = (str(t) or "").strip()
            if not t:
                continue
            for n in food_names:
                if t in n:
                    allergy_hits.append({'tag': t, 'food': n})
        # 去重
        seen = set()
        uniq = []
        for h in allergy_hits:
            k = (h['tag'], h['food'])
            if k not in seen:
                seen.add(k)
                uniq.append(h)
        allergy_hits = uniq

        if allergy_hits:
            title = "过敏预警"
            msg = f"识别到可能包含过敏原：{'、'.join(sorted({h['tag'] for h in allergy_hits}))}"
            HealthAlert.objects.create(
                child=child,
                alert_type='allergy',
                title=title,
                message=msg,
                payload={
                    'meal_id': meal_record.id,
                    'date': today.isoformat(),
                    'meal_type': meal_type,
                    'hits': allergy_hits,
                },
            )
    except Exception:
        allergy_hits = []

    # 检查五色满分奖励
    bonus = 0
    if child.is_five_color_complete():
        bonus = 20
        child.add_power(20)
        Encouragement.objects.create(
            sender=child.parent,
            child=child,
            message="🎉 五色满分！获得额外20体力奖励！"
        )

    return JsonResponse({
        'success': True,
        'message': '识别成功',
        'meal_id': meal_record.id,
        'foods': [{'name': f.food.name, 'category': f.food.category, 'weight': f.weight} for f in meal_record.food_items.all()],
        'nutrition': {
            'calories': round(meal_record.total_calories, 1),
            'protein': round(meal_record.total_protein, 1),
            'carbohydrate': round(meal_record.total_carbohydrate, 1),
            'fat': round(meal_record.total_fat, 1),
        },
        'score': score,
        'five_color_bonus': bonus,
        'allergy_hits': allergy_hits,
        'gems': {
            'red': child.gem_red,
            'yellow': child.gem_yellow,
            'green': child.gem_green,
            'blue': child.gem_blue,
            'purple': child.gem_purple,
        }
    })


@login_required
@login_required
def child_health(request):
    """儿童端手环数据页"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return render(request, 'child/health.html', {
            'error': '未找到关联的儿童账户',
            'child': None,
        })
    return render(request, 'child/health.html', {'child': child})


@login_required
def child_meals(request):
    """儿童端膳食页"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return render(request, 'child/meals.html', {
            'error': '未找到关联的儿童账户',
            'child': None,
        })
    today = timezone.now().date()
    today_meals = MealRecord.objects.filter(child=child, date=today).prefetch_related('food_items__food')
    allergy_tags = child.allergy_tags or []
    for meal in today_meals:
        meal.allergy_hits = []
        if allergy_tags:
            food_names = [str(fi.food.name) for fi in meal.food_items.all()]
            for tag in allergy_tags:
                tag = (str(tag) or "").strip()
                if not tag:
                    continue
                for fname in food_names:
                    if tag in fname:
                        meal.allergy_hits.append({'tag': tag, 'food': fname})
                        break
    return render(request, 'child/meals.html', {
        'child': child,
        'today': today,
        'today_meals': today_meals,
    })


@login_required
def child_tasks(request):
    """儿童端任务页"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return render(request, 'child/tasks.html', {
            'error': '未找到关联的儿童账户',
            'child': None,
        })
    today = timezone.now().date()
    tasks = Task.objects.all()
    task_records = TaskRecord.objects.filter(child=child, date=today)
    task_status = {tr.task.code: tr.status for tr in task_records}
    daily_records = []
    for task in tasks:
        status = task_status.get(task.code, 'pending')
        record, created = TaskRecord.objects.get_or_create(
            child=child, task=task, date=today,
            defaults={'status': 'pending'}
        )
        if created:
            status = 'pending'
        else:
            status = record.status
        daily_records.append({
            'task': task,
            'record': record,
            'status': status
        })
    return render(request, 'child/tasks.html', {
        'child': child,
        'daily_records': daily_records,
    })


@login_required
def child_challenges(request):
    """儿童端挑战页"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return render(request, 'child/challenges.html', {
            'error': '未找到关联的儿童账户',
            'child': None,
        })
    active_challenges = []
    for progress in ChallengeProgress.objects.filter(child=child, is_completed=False).select_related('challenge'):
        if progress.challenge.status == 'active':
            progress.percent = int(progress.current_value / progress.challenge.target_value * 100)
            active_challenges.append(progress)
    return render(request, 'child/challenges.html', {
        'child': child,
        'active_challenges': active_challenges,
    })


@login_required
def child_encouragements(request):
    """儿童端鼓励页"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return render(request, 'child/encouragements.html', {
            'error': '未找到关联的儿童账户',
            'child': None,
        })
    encouragements = Encouragement.objects.filter(
        child=child
    ).order_by('-created_at')[:20]
    return render(request, 'child/encouragements.html', {
        'child': child,
        'encouragements': encouragements,
    })


@login_required
def child_alerts_page(request):
    """儿童端预警页"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return render(request, 'child/alerts.html', {
            'error': '未找到关联的儿童账户',
            'child': None,
        })
    return render(request, 'child/alerts.html', {'child': child})


def child_meal_history(request):
    """儿童膳食历史"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    days = int(request.GET.get('days', 7))
    start_date = timezone.now().date() - timedelta(days=days)

    meals = MealRecord.objects.filter(
        child=child, date__gte=start_date
    ).order_by('-date', '-meal_type')

    return JsonResponse({
        'success': True,
        'meals': [{
            'id': m.id,
            'date': m.date.isoformat(),
            'meal_type': m.meal_type,
            'score': m.total_score,
            'calories': round(m.total_calories, 1),
            'foods': [{'name': f.food.name, 'category': f.food.category} for f in m.food_items.all()]
        } for m in meals]
    })


@login_required
def child_recommended_intake(request):
    """儿童端：参考摄入与家庭维护标签（只读），与 `GET /parent/recommended-intake/` 字段口径一致。"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    payload = _intake_and_tags_for_child(child)
    return JsonResponse({
        'success': True,
        'child': {'id': child.id, 'nickname': child.nickname, 'age_years': payload['age_years']},
        'recommendation': payload['recommendation'],
        'allergy_tags': payload['allergy_tags'],
        'medical_tags': payload['medical_tags'],
    })


@login_required
def child_health_alerts(request):
    """儿童端拉取预警列表。"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    limit = max(1, min(100, int(request.GET.get('limit', 50))))
    alerts = HealthAlert.objects.filter(child=child).order_by('-created_at')[:limit]
    return JsonResponse({
        'success': True,
        'alerts': [{
            'id': a.id,
            'type': a.alert_type,
            'title': a.title,
            'message': a.message,
            'created_at': timezone.localtime(a.created_at).strftime('%Y-%m-%d %H:%M'),
            'is_read': a.is_read_by_child,
            'payload': a.payload,
        } for a in alerts],
    })


@login_required
@require_http_methods(["POST"])
def child_mark_alert_read(request, alert_id):
    """儿童端标记预警已读。"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})
    alert = get_object_or_404(HealthAlert, id=alert_id, child=child)
    alert.is_read_by_child = True
    alert.save(update_fields=['is_read_by_child'])
    return JsonResponse({'success': True})


@login_required
def child_badges(request):
    """儿童徽章墙"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    earned = ChildBadge.objects.filter(child=child).select_related('badge')
    all_badges = Badge.objects.all()

    return JsonResponse({
        'success': True,
        'earned': [{'id': b.badge.id, 'name': b.badge.name, 'icon': b.badge.icon,
                     'earned_at': b.earned_at.isoformat()} for b in earned],
        'locked': [{'id': b.id, 'name': b.name, 'icon': b.icon,
                    'description': b.description, 'requirement': b.requirement}
                   for b in all_badges if b not in [eb.badge for eb in earned]]
    })


@login_required
def child_badges_page(request):
    """儿童端徽章页"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return render(request, 'child/badges.html', {
            'error': '未找到关联的儿童账户',
            'child': None,
        })
    earned = ChildBadge.objects.filter(child=child).select_related('badge')
    all_badges = Badge.objects.all()
    return render(request, 'child/badges.html', {
        'child': child,
        'earned': earned,
        'all_badges': all_badges,
    })


@login_required
def child_update_avatar(request):
    """更新儿童头像"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '仅支持POST请求'})

    child = Child.objects.filter(user=request.user).first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    avatar = request.POST.get('avatar', '')
    if avatar not in ['default', 'warrior', 'princess', 'robot', 'unicorn', 'dragon', 'star', 'moon']:
        return JsonResponse({'success': False, 'message': '无效的头像选项'})

    child.avatar = avatar
    child.save()

    return JsonResponse({'success': True, 'message': '头像已更新'})


# ========== 家长端视图 ==========
# 本段路由与模板（parent/*、templates/parent/*）由「家长端」负责人维护；
# 修改时请避免改动儿童端、学校端视图与模板，减少合并冲突。


def _meal_five_color_score_from_items(meal):
    """按本餐食材覆盖的五色大类数量计分（与儿童端单次识别逻辑一致，1–5）。"""
    cats = set()
    for item in meal.food_items.all():
        c = item.food.category
        if c in ('grain', 'protein', 'vegetable', 'fruit', 'dairy'):
            cats.add(c)
    return len(cats)


def _parent_resolve_child(request):
    """当前家长会话中选中的孩子。"""
    selected_id = request.session.get('selected_child_id')
    children = Child.objects.filter(parent=request.user)
    if selected_id:
        child = children.filter(id=selected_id).first()
        if not child:
            child = children.first()
    else:
        child = children.first()
    return child, children


def _parent_task_stats_payload(child, upgraded):
    """家长端局部刷新用的体力与任务统计。"""
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    child.refresh_from_db()
    today_completed = TaskRecord.objects.filter(
        child=child, date=today, status='completed'
    ).count()
    week_completed = TaskRecord.objects.filter(
        child=child, date__gte=week_ago, status='completed'
    ).count()
    pending_count = TaskRecord.objects.filter(
        child=child, date=today, status='pending'
    ).count()
    denom = child.power_to_next or 1
    progress_percent = min(100, int((child.power / denom) * 100))
    return {
        'upgraded': upgraded,
        'new_power': child.power,
        'new_level': child.level,
        'power_to_next': child.power_to_next,
        'today_completed': today_completed,
        'week_completed': week_completed,
        'pending_count': pending_count,
        'progress_percent': progress_percent,
    }


@login_required
def parent_switch_child(request):
    """切换当前管理的孩子"""
    if request.method == 'POST':
        child_id = request.POST.get('child_id')
        children = Child.objects.filter(parent=request.user)
        if child_id:
            try:
                child = children.get(id=int(child_id))
                request.session['selected_child_id'] = child.id
            except Child.DoesNotExist:
                pass
    return redirect('parent_dashboard')


@login_required
def parent_dashboard(request):
    """家长端首页"""
    children = Child.objects.filter(parent=request.user)
    if not children.exists():
        # 没有关联儿童，显示绑定儿童页面
        return render(request, 'parent/bind_child.html')

    selected_id = request.session.get('selected_child_id')
    if selected_id:
        child = children.filter(id=selected_id).first()
        if not child:
            child = children.first()
    else:
        child = children.first()
        request.session['selected_child_id'] = child.id

    today = timezone.now().date()

    pending_tasks = TaskRecord.objects.filter(
        child=child, date=today, status='pending'
    ).select_related('task')

    week_ago = timezone.now().date() - timedelta(days=7)
    week_completed = TaskRecord.objects.filter(
        child=child, date__gte=week_ago, status='completed'
    ).count()

    today_completed = TaskRecord.objects.filter(
        child=child, date=today, status='completed'
    ).count()

    three_days_ago = timezone.now().date() - timedelta(days=3)
    recent_records = TaskRecord.objects.filter(
        child=child, date__gte=three_days_ago, status='completed'
    ).select_related('task').order_by('-date', '-submitted_at')

    encouragements = Encouragement.objects.filter(
        sender=request.user, child=child
    ).order_by('-created_at')[:15]

    denom = child.power_to_next or 1
    progress_percent = min(100, int((child.power / denom) * 100))

    today_meals = MealRecord.objects.filter(child=child, date=today).prefetch_related('food_items__food')

    today_meal_totals = {'kcal': 0.0, 'protein': 0.0, 'carb': 0.0, 'fat': 0.0, 'count': 0}
    for m in today_meals:
        today_meal_totals['kcal'] += float(m.total_calories or 0)
        today_meal_totals['protein'] += float(m.total_protein or 0)
        today_meal_totals['carb'] += float(m.total_carbohydrate or 0)
        today_meal_totals['fat'] += float(m.total_fat or 0)
        today_meal_totals['count'] += 1

    from .nutrition import recommend_intake_for_age

    age_y = child.age_years()
    intake_recommendation = recommend_intake_for_age(age_y)
    parent_health_alerts = list(
        HealthAlert.objects.filter(child=child).order_by('-created_at')[:20]
    )
    parent_alerts_unread = sum(1 for a in parent_health_alerts if not a.is_read_by_parent)

    children_class_map = {}
    for c in children:
        rows = []
        for e in ClassStudent.objects.filter(child=c).select_related('teacher__user', 'teacher__school'):
            rows.append({
                'teacher_id': e.teacher_id,
                'school': e.teacher.school.name,
                'class_name': e.teacher.class_name,
                'teacher_name': e.teacher.user.username,
            })
        children_class_map[str(c.id)] = rows

    # 获取学校发布的健康挑战（根据孩子所在的班级）
    child_teacher_ids = list(ClassStudent.objects.filter(child=child).values_list('teacher_id', flat=True))
    school_challenges = []
    if child_teacher_ids:
        from django.db.models import Q
        school_challenges = list(
            HealthChallenge.objects.filter(
                Q(teacher_id__in=child_teacher_ids) | Q(scope='school'),
                status='active'
            ).select_related('teacher').order_by('-created_at')[:10]
        )
        for challenge in school_challenges:
            progress = ChallengeProgress.objects.filter(child=child, challenge=challenge).first()
            challenge.current_value = progress.current_value if progress else 0
            challenge.is_completed = progress.is_completed if progress else False

    return render(request, 'parent/dashboard.html', {
        'child': child,
        'child_age_years': age_y,
        'children': children,
        'pending_tasks': pending_tasks,
        'week_completed': week_completed,
        'today_completed': today_completed,
        'recent_records': recent_records,
        'encouragements': encouragements,
        'progress_percent': progress_percent,
        'today_meals': today_meals,
        'today_meal_totals': today_meal_totals,
        'intake_recommendation': intake_recommendation,
        'parent_health_alerts': parent_health_alerts,
        'parent_alerts_unread': parent_alerts_unread,
        'children_class_map': children_class_map,
        'school_challenges': school_challenges,
    })


def _get_parent_child(request):
    """获取当前选中的孩子"""
    children = Child.objects.filter(parent=request.user)
    if not children.exists():
        return None
    selected_id = request.session.get('selected_child_id')
    if selected_id:
        child = children.filter(id=selected_id).first()
        if not child:
            child = children.first()
    else:
        child = children.first()
    return child


@login_required
def parent_meals(request):
    """家长端 - 膳食记录页面"""
    child = _get_parent_child(request)
    if not child:
        return render(request, 'parent/bind_child.html')

    today = timezone.now().date()
    today_meals = MealRecord.objects.filter(child=child, date=today).prefetch_related('food_items__food')
    today_meal_totals = {'kcal': 0.0, 'protein': 0.0, 'carb': 0.0, 'fat': 0.0, 'count': 0}
    for m in today_meals:
        today_meal_totals['kcal'] += float(m.total_calories or 0)
        today_meal_totals['protein'] += float(m.total_protein or 0)
        today_meal_totals['carb'] += float(m.total_carbohydrate or 0)
        today_meal_totals['fat'] += float(m.total_fat or 0)
        today_meal_totals['count'] += 1

    return render(request, 'parent/meals.html', {
        'child': child,
        'today_meals': today_meals,
        'today_meal_totals': today_meal_totals,
        'children': Child.objects.filter(parent=request.user),
    })


@login_required
def parent_trends(request):
    """家长端 - 健康趋势页面"""
    child = _get_parent_child(request)
    if not child:
        return render(request, 'parent/bind_child.html')

    return render(request, 'parent/trends.html', {
        'child': child,
        'children': Child.objects.filter(parent=request.user),
    })


@login_required
def parent_tasks(request):
    """家长端 - 健康任务页面"""
    child = _get_parent_child(request)
    if not child:
        return render(request, 'parent/bind_child.html')

    today = timezone.now().date()
    pending_tasks = TaskRecord.objects.filter(
        child=child, date=today, status='pending'
    ).select_related('task')

    return render(request, 'parent/tasks.html', {
        'child': child,
        'pending_tasks': pending_tasks,
        'children': Child.objects.filter(parent=request.user),
    })


@login_required
def parent_health_data(request):
    """家长端 - 手环数据页面"""
    child = _get_parent_child(request)
    if not child:
        return render(request, 'parent/bind_child.html')

    return render(request, 'parent/health_data.html', {
        'child': child,
        'children': Child.objects.filter(parent=request.user),
    })


@login_required
def parent_encourage(request):
    """家长端 - 鼓励语页面"""
    child = _get_parent_child(request)
    if not child:
        return render(request, 'parent/bind_child.html')

    encouragements = Encouragement.objects.filter(
        sender=request.user, child=child
    ).order_by('-created_at')[:15]

    return render(request, 'parent/encourage.html', {
        'child': child,
        'encouragements': encouragements,
        'children': Child.objects.filter(parent=request.user),
    })


@login_required
def parent_settings(request):
    """家长端 - 设置页面"""
    child = _get_parent_child(request)
    if not child:
        return render(request, 'parent/bind_child.html')

    children = Child.objects.filter(parent=request.user)
    children_class_map = {}
    for c in children:
        rows = []
        for e in ClassStudent.objects.filter(child=c).select_related('teacher__user', 'teacher__school'):
            rows.append({
                'teacher_id': e.teacher_id,
                'school': e.teacher.school.name,
                'class_name': e.teacher.class_name,
                'teacher_name': e.teacher.user.username,
            })
        children_class_map[str(c.id)] = rows

    return render(request, 'parent/settings.html', {
        'child': child,
        'children': children,
        'children_class_map': children_class_map,
    })


@login_required
@require_http_methods(["POST"])
def parent_confirm_task(request, record_id):
    """家长确认任务"""
    record = get_object_or_404(
        TaskRecord, id=record_id, child__parent=request.user
    )

    if record.status != 'pending':
        return JsonResponse({'success': False, 'message': '任务状态不允许确认'})

    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    child = record.child
    record.status = 'completed'
    record.confirmed_at = timezone.now()
    record.save()

    upgraded = child.add_power(record.task.power_reward)

    Encouragement.objects.create(
        sender=request.user,
        child=child,
        message=f"🎉 家长确认了你的任务！+{record.task.power_reward}体力"
    )

    stats = _parent_task_stats_payload(child, upgraded)
    return JsonResponse({'success': True, 'message': '确认成功', **stats})


@login_required
@require_http_methods(["POST"])
def parent_add_manual_task(request):
    """家长手动添加任务"""
    selected_id = request.session.get('selected_child_id')
    children = Child.objects.filter(parent=request.user)
    if selected_id:
        child = children.filter(id=selected_id).first()
        if not child:
            child = children.first()
    else:
        child = children.first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    task_code = request.POST.get('task_code')
    task = Task.objects.get(code=task_code)
    today = timezone.now().date()

    record, created = TaskRecord.objects.get_or_create(
        child=child, task=task, date=today,
        defaults={'status': 'completed', 'confirmed_at': timezone.now()}
    )

    if not created:
        if record.status != 'completed':
            record.status = 'completed'
            record.confirmed_at = timezone.now()
            record.save()
            upgraded = child.add_power(task.power_reward)
            stats = _parent_task_stats_payload(child, upgraded)
            return JsonResponse({
                'success': True,
                'message': f'已补充确认 {task.name}，+{task.power_reward}体力',
                **stats,
            })
        return JsonResponse({'success': False, 'message': '今日该任务已完成'})

    upgraded = child.add_power(task.power_reward)

    Encouragement.objects.create(
        sender=request.user,
        child=child,
        message=f"🎉 家长补充确认了{task.name}！+{task.power_reward}体力"
    )

    stats = _parent_task_stats_payload(child, upgraded)
    return JsonResponse({
        'success': True,
        'message': f'已补充确认 {task.name}，+{task.power_reward}体力',
        **stats,
    })


@login_required
@require_http_methods(["POST"])
def parent_send_encouragement(request):
    """家长发送鼓励语"""
    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    message = request.POST.get('message', '').strip()
    if not message:
        return JsonResponse({'success': False, 'message': '鼓励内容不能为空'})

    enc = Encouragement.objects.create(
        sender=request.user,
        child=child,
        message=message
    )

    return JsonResponse({
        'success': True,
        'message': '鼓励语已发送',
        'encouragement': {
            'id': enc.id,
            'message': enc.message,
            'created_at': timezone.localtime(enc.created_at).strftime('%Y-%m-%d %H:%M'),
            'is_read': enc.is_read,
        },
    })


@login_required
@require_http_methods(["POST"])
def parent_correct_meal(request, meal_id):
    """家长修正膳食识别结果"""
    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    meal = get_object_or_404(MealRecord, id=meal_id, child=child)

    food_ids = request.POST.getlist('food_ids')
    weights = request.POST.getlist('weights')

    meal.food_items.all().delete()

    for food_id, weight in zip(food_ids, weights):
        try:
            food = FoodMaterial.objects.get(id=int(food_id))
            w = float(weight)
            if w < 0:
                w = 0
            MealFoodItem.objects.create(meal_record=meal, food=food, weight=w)
        except (FoodMaterial.DoesNotExist, ValueError, TypeError):
            pass

    food_items = meal.food_items.all()
    meal.total_protein = sum(item.food.protein * item.weight / 100 for item in food_items)
    meal.total_carbohydrate = sum(item.food.carbohydrate * item.weight / 100 for item in food_items)
    meal.total_fat = sum(item.food.fat * item.weight / 100 for item in food_items)
    meal.total_calories = sum(item.food.calories * item.weight / 100 for item in food_items)
    meal.total_score = _meal_five_color_score_from_items(meal)
    meal.is_verified = True
    meal.save()

    # 过敏预警：家长修正也会触发（避免儿童端识别未命中）
    allergy_hits = []
    try:
        tags = child.allergy_tags or []
        if not isinstance(tags, list):
            tags = []
        food_names = [str(fi.food.name) for fi in meal.food_items.all()]
        for t in tags:
            t = (str(t) or "").strip()
            if not t:
                continue
            for n in food_names:
                if t in n:
                    allergy_hits.append({'tag': t, 'food': n})
        seen = set()
        uniq = []
        for h in allergy_hits:
            k = (h['tag'], h['food'])
            if k not in seen:
                seen.add(k)
                uniq.append(h)
        allergy_hits = uniq
        if allergy_hits:
            msg = f"修正后餐次包含可能过敏原：{'、'.join(sorted({h['tag'] for h in allergy_hits}))}"
            HealthAlert.objects.create(
                child=child,
                alert_type='allergy',
                title="过敏预警",
                message=msg,
                payload={
                    'meal_id': meal.id,
                    'date': meal.date.isoformat(),
                    'meal_type': meal.meal_type,
                    'hits': allergy_hits,
                    'source': 'parent_correct',
                },
            )
    except Exception:
        allergy_hits = []

    return JsonResponse({
        'success': True,
        'message': '膳食已修正',
        'total_score': meal.total_score,
        'allergy_hits': allergy_hits,
        'nutrition': {
            'calories': round(meal.total_calories, 1),
            'protein': round(meal.total_protein, 1),
            'carbohydrate': round(meal.total_carbohydrate, 1),
            'fat': round(meal.total_fat, 1),
        }
    })


@login_required
@require_http_methods(["GET"])
def parent_meal_detail(request, meal_id):
    """单条膳食明细（家长端修正弹窗用）。"""
    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    meal = get_object_or_404(
        MealRecord.objects.prefetch_related('food_items__food'),
        id=meal_id,
        child=child,
    )
    return JsonResponse({
        'success': True,
        'meal': {
            'id': meal.id,
            'meal_type': meal.meal_type,
            'meal_type_display': meal.get_meal_type_display(),
            'date': meal.date.isoformat(),
            'image_key': meal.image_key or '',
            'total_score': meal.total_score,
            'is_verified': meal.is_verified,
            'total_calories': round(meal.total_calories, 1),
            'foods': [{
                'food_id': item.food_id,
                'name': item.food.name,
                'weight': item.weight,
                'category': item.food.category,
            } for item in meal.food_items.all()],
        },
    })


@login_required
@require_http_methods(["GET"])
def parent_food_materials(request):
    """食材库列表（家长修正膳食时下拉用）。"""
    foods = FoodMaterial.objects.all().order_by('category', 'name')
    return JsonResponse({
        'success': True,
        'foods': [{'id': f.id, 'name': f.name, 'category': f.category} for f in foods],
    })


@login_required
@require_http_methods(["GET"])
def parent_meal_list(request):
    """按日期分组的膳食列表（家长端历史浏览、修正入口）。"""
    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    days = max(1, min(60, int(request.GET.get('days', 14))))
    end = timezone.now().date()
    start = end - timedelta(days=days - 1)

    meal_order = {'breakfast': 0, 'lunch': 1, 'dinner': 2, 'snack': 3}
    meals = (
        MealRecord.objects.filter(child=child, date__gte=start, date__lte=end)
        .prefetch_related('food_items__food')
        .order_by('-date', 'meal_type')
    )

    by_date = {}
    for m in meals:
        key = m.date.isoformat()
        names = [fi.food.name for fi in m.food_items.all()[:10]]
        by_date.setdefault(key, []).append({
            'id': m.id,
            'meal_type': m.meal_type,
            'meal_type_display': m.get_meal_type_display(),
            'total_score': m.total_score,
            'total_calories': round(m.total_calories or 0, 0),
            'is_verified': m.is_verified,
            'food_summary': '、'.join(names) if names else '—',
        })

    out_days = []
    for d in sorted(by_date.keys(), reverse=True):
        rows = sorted(by_date[d], key=lambda x: meal_order.get(x['meal_type'], 9))
        out_days.append({'date': d, 'meals': rows})

    return JsonResponse({'success': True, 'days': days, 'dates': out_days})


@login_required
@require_http_methods(["POST"])
def parent_child_diet_notes(request):
    """保存当前选中孩子的膳食备注（忌口、过敏等）。"""
    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    notes = (request.POST.get('diet_notes') or '').strip()
    if len(notes) > 4000:
        return JsonResponse({'success': False, 'message': '备注过长，请控制在4000字内'})
    child.diet_notes = notes
    child.save(update_fields=['diet_notes'])
    return JsonResponse({'success': True, 'message': '已保存'})


@login_required
@require_http_methods(["POST"])
def parent_child_birth_date(request):
    """保存当前选中孩子的出生日期（仅家庭端维护；年龄由此推算）。"""
    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    raw = (request.POST.get('birth_date') or '').strip()
    if not raw:
        child.birth_date = None
        child.save(update_fields=['birth_date'])
        return JsonResponse({
            'success': True,
            'message': '已清空出生日期',
            'birth_date': None,
            'age_years': None,
        })

    d = parse_date(raw)
    if not d:
        return JsonResponse({'success': False, 'message': '日期格式无效，请使用 YYYY-MM-DD'})

    today = timezone.now().date()
    if d > today:
        return JsonResponse({'success': False, 'message': '出生日期不能晚于今天'})
    if (today.year - d.year) > 25:
        return JsonResponse({'success': False, 'message': '出生日期过早，请核对'})

    child.birth_date = d
    child.save(update_fields=['birth_date'])
    return JsonResponse({
        'success': True,
        'message': '已保存',
        'birth_date': d.isoformat(),
        'age_years': child.age_years(),
    })


@login_required
@require_http_methods(["POST"])
def parent_child_health_tags(request):
    """保存当前选中孩子的结构化标签（过敏、医嘱）。"""
    import json

    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    def _parse_list(key: str):
        raw = request.POST.get(key, '[]')
        try:
            arr = json.loads(raw)
            if not isinstance(arr, list):
                return []
            cleaned = []
            seen = set()
            for x in arr:
                s = (str(x) or '').strip()
                if not s:
                    continue
                if len(s) > 20:
                    s = s[:20]
                if s not in seen:
                    seen.add(s)
                    cleaned.append(s)
            return cleaned[:30]
        except Exception:
            return []

    allergy_tags = _parse_list('allergy_tags')
    medical_tags = _parse_list('medical_tags')
    child.allergy_tags = allergy_tags
    child.medical_tags = medical_tags
    child.save(update_fields=['allergy_tags', 'medical_tags'])
    return JsonResponse({
        'success': True,
        'message': '已保存',
        'allergy_tags': allergy_tags,
        'medical_tags': medical_tags,
    })


@login_required
def parent_child_recommended_intake(request):
    """返回当前选中孩子的年龄与每日建议摄入（参考范围）。"""
    from .nutrition import recommend_intake_for_age

    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    age = child.age_years()
    rec = recommend_intake_for_age(age)
    return JsonResponse({
        'success': True,
        'child': {'id': child.id, 'nickname': child.nickname, 'age_years': age},
        'recommendation': None if rec is None else {
            'calories_kcal_min': rec.calories_kcal_min,
            'calories_kcal_max': rec.calories_kcal_max,
            'protein_g_min': rec.protein_g_min,
            'protein_g_max': rec.protein_g_max,
            'notes': rec.notes,
        },
        'allergy_tags': list(child.allergy_tags or []),
        'medical_tags': list(child.medical_tags or []),
    })


@login_required
def parent_health_alerts(request):
    """家长端拉取预警列表。"""
    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    limit = max(1, min(100, int(request.GET.get('limit', 50))))
    alerts = HealthAlert.objects.filter(child=child).order_by('-created_at')[:limit]
    return JsonResponse({
        'success': True,
        'alerts': [{
            'id': a.id,
            'type': a.alert_type,
            'title': a.title,
            'message': a.message,
            'created_at': timezone.localtime(a.created_at).strftime('%Y-%m-%d %H:%M'),
            'is_read': a.is_read_by_parent,
            'payload': a.payload,
        } for a in alerts],
    })


@login_required
@require_http_methods(["POST"])
def parent_mark_alert_read(request, alert_id):
    """家长端标记预警已读。"""
    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})
    alert = get_object_or_404(HealthAlert, id=alert_id, child=child)
    alert.is_read_by_parent = True
    alert.save(update_fields=['is_read_by_parent'])
    return JsonResponse({'success': True})


@login_required
def parent_recipes(request):
    """智能食谱推荐（支持 target 关键词与 fill_gaps=1 按当日未点亮的五色缺口推荐）。"""
    child, _children = _parent_resolve_child(request)
    target_nutrient = (request.GET.get('target') or '').strip()
    fill_gaps = request.GET.get('fill_gaps') == '1'
    limit = max(1, min(80, int(request.GET.get('limit', 30))))
    recipe_id = request.GET.get('id')
    force_json = request.GET.get('format') == 'json'
    is_html = not force_json and (request.GET.get('html') == '1' or 'text/html' in request.headers.get('Accept', ''))

    recipes = Recipe.objects.select_related('created_by').all()

    if recipe_id:
        recipes = recipes.filter(id=recipe_id)

    if fill_gaps and child:
        q = Q()
        if not child.gem_red:
            for kw in ('谷', '主食', '谷物', '杂粮', '米', '面', '薯', '燕麦', '饭', '粥', '玉米'):
                q |= (
                    Q(target_nutrients__icontains=kw)
                    | Q(name__icontains=kw)
                    | Q(description__icontains=kw)
                    | Q(ingredients__icontains=kw)
                )
        if not child.gem_yellow:
            for kw in ('蛋白', '肉', '鱼', '虾', '豆', '蛋', '鸡', '牛', '排骨', '鸡胸', '鲈鱼'):
                q |= (
                    Q(target_nutrients__icontains=kw)
                    | Q(name__icontains=kw)
                    | Q(description__icontains=kw)
                    | Q(ingredients__icontains=kw)
                )
        if not child.gem_green:
            for kw in ('蔬菜', '菜', '叶', '纤维', '维生素', '西兰花', '菠菜', '黄瓜', '青菜'):
                q |= (
                    Q(target_nutrients__icontains=kw)
                    | Q(name__icontains=kw)
                    | Q(description__icontains=kw)
                    | Q(ingredients__icontains=kw)
                )
        if not child.gem_blue:
            for kw in ('水果', '果', '维C', '浆果', '苹果', '香蕉', '橙'):
                q |= (
                    Q(target_nutrients__icontains=kw)
                    | Q(name__icontains=kw)
                    | Q(description__icontains=kw)
                    | Q(ingredients__icontains=kw)
                )
        if not child.gem_purple:
            for kw in ('奶', '乳', '钙', '酸奶', '芝士', '牛奶'):
                q |= (
                    Q(target_nutrients__icontains=kw)
                    | Q(name__icontains=kw)
                    | Q(description__icontains=kw)
                    | Q(ingredients__icontains=kw)
                )
        if q:
            narrowed = recipes.filter(q).distinct()
            if narrowed.exists():
                recipes = narrowed

    if target_nutrient:
        recipes = recipes.filter(
            Q(target_nutrients__icontains=target_nutrient)
            | Q(name__icontains=target_nutrient)
            | Q(description__icontains=target_nutrient)
            | Q(ingredients__icontains=target_nutrient)
        ).distinct()

    def _gap_score(r):
        if not child:
            return 0
        t = f"{r.name}\n{r.description}\n{r.ingredients}\n{r.target_nutrients or ''}"
        s = 0
        if not child.gem_red and any(k in t for k in ('谷', '主食', '谷物', '杂粮', '米', '面', '薯', '燕麦', '饭', '粥', '玉米')):
            s += 1
        if not child.gem_yellow and any(k in t for k in ('蛋白', '肉', '鱼', '虾', '豆', '蛋', '鸡', '牛', '排骨', '鸡胸', '鲈鱼')):
            s += 1
        if not child.gem_green and any(k in t for k in ('蔬菜', '菜', '叶', '纤维', '维生素', '西兰花', '菠菜', '黄瓜', '青菜')):
            s += 1
        if not child.gem_blue and any(k in t for k in ('水果', '果', '维C', '浆果', '苹果', '香蕉', '橙')):
            s += 1
        if not child.gem_purple and any(k in t for k in ('奶', '乳', '钙', '酸奶', '芝士', '牛奶')):
            s += 1
        return s

    if fill_gaps and child:
        pool = list(recipes[: max(limit * 4, 60)])
        pool.sort(
            key=lambda r: (
                -_gap_score(r),
                0 if r.created_by_id is None else 1,
                r.name,
            )
        )
        recipes = pool[:limit]
    else:
        recipes = list(recipes.order_by('-id')[:limit])

    if is_html:
        recipe_list = [{
            'id': r.id,
            'name': r.name,
            'description': r.description,
            'ingredients': r.ingredients,
            'steps': r.steps,
            'calories': r.calories,
            'protein': r.protein,
            'carbohydrate': r.carbohydrate,
            'fat': r.fat,
            'target_nutrients': r.target_nutrients,
            'target_nutrients_list': [t.strip() for t in (r.target_nutrients or '').split(',') if t.strip()],
            'is_family_recipe': bool(r.created_by_id),
            'created_by': r.created_by.username if r.created_by_id else None,
            'gap_match_score': _gap_score(r) if child else 0,
        } for r in recipes]
        return render(request, 'parent/recipes.html', {
            'child': child,
            'recipes': recipe_list,
            'children': _children,
        })

    return JsonResponse({
        'success': True,
        'recipes': [{
            'id': r.id,
            'name': r.name,
            'description': r.description,
            'ingredients': r.ingredients,
            'steps': r.steps,
            'calories': r.calories,
            'protein': r.protein,
            'carbohydrate': r.carbohydrate,
            'fat': r.fat,
            'target_nutrients': r.target_nutrients,
            'is_family_recipe': bool(r.created_by_id),
            'created_by': r.created_by.username if r.created_by_id else None,
            'gap_match_score': _gap_score(r) if child else 0,
        } for r in recipes]
    })


def parent_recipe_create(request):
    """家长添加自定义食谱（写入 Recipe，全端可见）。"""
    from .recipe_nutrition_estimate import estimate_from_ingredients_text

    if not is_parent(request.user):
        return JsonResponse({'success': False, 'message': '仅限家长账号添加食谱'}, status=403)

    if request.method == 'GET':
        return render(request, 'parent/recipe_add.html', {})

    name = (request.POST.get('name') or '').strip()
    ingredients = (request.POST.get('ingredients') or '').strip()
    if not name or not ingredients:
        return JsonResponse({'success': False, 'message': '请填写食谱名称与食材清单'})

    if len(name) > 100:
        return JsonResponse({'success': False, 'message': '食谱名称过长'})
    if len(ingredients) > 2000:
        return JsonResponse({'success': False, 'message': '食材清单过长'})
    description = (request.POST.get('description') or '').strip()[:2000]
    steps = (request.POST.get('steps') or '').strip()[:5000]
    target_nutrients = (request.POST.get('target_nutrients') or '').strip()[:100]
    suitable_for = (request.POST.get('suitable_for') or '家庭端添加').strip()[:50]

    est = estimate_from_ingredients_text(ingredients)
    if not target_nutrients:
        target_nutrients = est.get('suggested_target_nutrients', '')[:100]

    if Recipe.objects.filter(name=name).exists():
        return JsonResponse({'success': False, 'message': '已存在同名食谱，请换个名称'})

    recipe = Recipe.objects.create(
        name=name,
        description=description,
        ingredients=ingredients,
        steps=steps,
        calories=est['calories'],
        protein=est['protein'],
        carbohydrate=est['carbohydrate'],
        fat=est['fat'],
        suitable_for=suitable_for,
        target_nutrients=target_nutrients,
        created_by=request.user,
    )

    return JsonResponse({
        'success': True,
        'message': '食谱已添加（营养已由食材清单自动估算）',
        'nutrition_estimate': est,
        'recipe': {
            'id': recipe.id,
            'name': recipe.name,
            'description': recipe.description,
            'ingredients': recipe.ingredients,
            'steps': recipe.steps,
            'calories': recipe.calories,
            'protein': recipe.protein,
            'carbohydrate': recipe.carbohydrate,
            'fat': recipe.fat,
            'target_nutrients': recipe.target_nutrients,
            'is_family_recipe': True,
            'created_by': request.user.username,
        },
    })


@login_required
@require_http_methods(["POST"])
def parent_recipe_batch_import(request):
    """批量导入食谱（普通文字格式，每行一个食谱，格式：食谱名称|食材1,食材2,食材3）"""
    from .recipe_nutrition_estimate import estimate_from_ingredients_text

    if not is_parent(request.user):
        return JsonResponse({'success': False, 'message': '仅限家长账号批量导入'}, status=403)

    text = (request.POST.get('recipes_text') or '').strip()
    if not text:
        return JsonResponse({'success': False, 'message': '请输入食谱数据'}, status=400)

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return JsonResponse({'success': False, 'message': '未提供食谱数据'}, status=400)

    if len(lines) > 50:
        return JsonResponse({'success': False, 'message': '单次最多导入 50 条食谱'}, status=400)

    created = []
    errors = []
    existing = 0

    for i, line in enumerate(lines):
        parts = line.split('|')
        if len(parts) < 2:
            errors.append(f'第 {i+1} 行：格式错误，请用竖线分隔名称和食材，如：红烧冬瓜|冬瓜300g,瘦肉50g')
            continue

        name = parts[0].strip()
        ingredients = parts[1].strip()

        if not name or not ingredients:
            errors.append(f'第 {i+1} 行：名称和食材清单不能为空')
            continue

        if len(name) > 100:
            errors.append(f'第 {i+1} 行：食谱名称过长')
            continue

        if Recipe.objects.filter(name=name).exists():
            existing += 1
            continue

        est = estimate_from_ingredients_text(ingredients)
        target_nutrients = est.get('suggested_target_nutrients', '')[:100]

        recipe = Recipe.objects.create(
            name=name,
            description='',
            ingredients=ingredients,
            steps='',
            calories=est['calories'],
            protein=est['protein'],
            carbohydrate=est['carbohydrate'],
            fat=est['fat'],
            suitable_for='家庭端批量导入',
            target_nutrients=target_nutrients,
            created_by=request.user,
        )
        created.append({'id': recipe.id, 'name': recipe.name})

    return JsonResponse({
        'success': True,
        'message': f'导入完成：成功 {len(created)} 条，跳过已存在 {existing} 条',
        'created_count': len(created),
        'existing_count': existing,
        'errors': errors[:10],
        'created': created[:20],
    })


def parent_recipe_delete(request, recipe_id):
    """删除食谱（仅创建者或管理员可删除）"""
    if not is_parent(request.user):
        return JsonResponse({'success': False, 'message': '仅限家长账号'}, status=403)

    try:
        recipe = Recipe.objects.get(id=recipe_id)
    except Recipe.DoesNotExist:
        return JsonResponse({'success': False, 'message': '食谱不存在'}, status=404)

    if recipe.created_by_id != request.user.id:
        return JsonResponse({'success': False, 'message': '仅可删除自己创建的食谱'}, status=403)

    recipe.delete()
    return JsonResponse({'success': True, 'message': '食谱已删除'})


@login_required
def parent_meal_report(request):
    """多维健康报告：膳食 + 每日已确认任务 + 手环步数/睡眠（若有）。"""
    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    days = max(1, min(90, int(request.GET.get('days', 7))))
    today = timezone.now().date()
    start_date = today - timedelta(days=days - 1)

    meals = MealRecord.objects.filter(child=child, date__gte=start_date)

    total_calories = float(meals.aggregate(Sum('total_calories'))['total_calories__sum'] or 0)
    total_protein = float(meals.aggregate(Sum('total_protein'))['total_protein__sum'] or 0)
    total_carbohydrate = float(meals.aggregate(Sum('total_carbohydrate'))['total_carbohydrate__sum'] or 0)
    total_fat = float(meals.aggregate(Sum('total_fat'))['total_fat__sum'] or 0)

    health_map = {
        h.date.isoformat(): h
        for h in HealthData.objects.filter(child=child, date__gte=start_date, date__lte=today)
    }

    daily_scores = []
    step_vals = []
    for day_offset in range(days):
        day = start_date + timedelta(days=day_offset)
        day_meals = meals.filter(date=day)
        meal_count = day_meals.count()
        avg_score = sum(m.total_score for m in day_meals) / max(meal_count, 1)
        day_kcal = float(day_meals.aggregate(s=Sum('total_calories'))['s'] or 0)
        tasks_done = TaskRecord.objects.filter(child=child, date=day, status='completed').count()
        hd = health_map.get(day.isoformat())
        steps = int(hd.steps) if hd else None
        sleep_min = int(hd.sleep_duration_minutes) if hd else None
        if steps is not None:
            step_vals.append(steps)
        daily_scores.append({
            'date': day.isoformat(),
            'score': round(avg_score, 1),
            'meal_count': meal_count,
            'day_calories': round(day_kcal, 1),
            'tasks_completed': tasks_done,
            'steps': steps,
            'sleep_duration_minutes': sleep_min,
        })

    task_rows = (
        TaskRecord.objects.filter(
            child=child, date__gte=start_date, date__lte=today, status='completed'
        )
        .values('task__code', 'task__name')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')
    )
    tasks_summary = [{'code': r['task__code'], 'name': r['task__name'], 'count': r['cnt']} for r in task_rows]
    total_tasks_completed = int(
        TaskRecord.objects.filter(
            child=child, date__gte=start_date, date__lte=today, status='completed'
        ).count()
    )

    avg_daily_steps = None
    if step_vals:
        avg_daily_steps = round(sum(step_vals) / len(step_vals), 1)

    return JsonResponse({
        'success': True,
        'report': {
            'period': f'近{days}天',
            'total_calories': round(total_calories, 1),
            'total_protein': round(total_protein, 1),
            'total_carbohydrate': round(total_carbohydrate, 1),
            'total_fat': round(total_fat, 1),
            'avg_daily_score': round(sum(d['score'] for d in daily_scores) / max(len(daily_scores), 1), 1),
            'daily_scores': daily_scores,
            'tasks_summary': tasks_summary,
            'total_tasks_completed': total_tasks_completed,
            'health_days_with_data': len(step_vals),
            'avg_daily_steps': avg_daily_steps,
        }
    })


def _weekly_pdf_ctx(child, days: int, footer: str) -> dict:
    """组装健康周报 PDF 所需上下文（家长端 / 学校端共用）。"""
    from .nutrition import recommend_intake_for_age

    days = max(1, min(30, int(days)))
    today = timezone.now().date()
    start = today - timedelta(days=days - 1)

    meals = MealRecord.objects.filter(child=child, date__gte=start, date__lte=today)
    total_calories = float(meals.aggregate(Sum('total_calories'))['total_calories__sum'] or 0)
    total_protein = float(meals.aggregate(Sum('total_protein'))['total_protein__sum'] or 0)
    total_carb = float(meals.aggregate(Sum('total_carbohydrate'))['total_carbohydrate__sum'] or 0)
    total_fat = float(meals.aggregate(Sum('total_fat'))['total_fat__sum'] or 0)

    health_map = {
        h.date.isoformat(): h
        for h in HealthData.objects.filter(child=child, date__gte=start, date__lte=today)
    }

    daily_rows = []
    score_sum = 0.0
    step_sum = 0
    step_days = 0
    for offset in range(days):
        day = start + timedelta(days=offset)
        day_meals = list(meals.filter(date=day))
        cnt = len(day_meals)
        avg_score = sum(m.total_score for m in day_meals) / max(cnt, 1)
        score_sum += avg_score
        day_cals = sum(float(m.total_calories or 0) for m in day_meals)
        tasks_done = TaskRecord.objects.filter(child=child, date=day, status='completed').count()
        hd = health_map.get(day.isoformat())
        steps = int(hd.steps) if hd else None
        sleep_min = int(hd.sleep_duration_minutes) if hd else None
        if steps is not None:
            step_sum += steps
            step_days += 1
        daily_rows.append({
            'date': day.strftime('%Y-%m-%d'),
            'meal_count': cnt,
            'day_calories': day_cals,
            'avg_score': avg_score,
            'tasks_completed': tasks_done,
            'steps': steps,
            'sleep_minutes': sleep_min,
        })

    avg_daily_score = score_sum / max(days, 1)
    task_completed = TaskRecord.objects.filter(
        child=child, date__gte=start, date__lte=today, status='completed'
    ).count()

    task_rows = (
        TaskRecord.objects.filter(
            child=child, date__gte=start, date__lte=today, status='completed'
        )
        .values('task__code', 'task__name')
        .annotate(cnt=Count('id'))
        .order_by('-cnt')
    )
    tasks_summary = [{'code': r['task__code'], 'name': r['task__name'], 'count': r['cnt']} for r in task_rows]

    age = child.age_years()
    rec = recommend_intake_for_age(age)

    return {
        'title': f'儿童健康周报（近{days}天）',
        'child_label': f'孩子：{child.nickname}（{child.get_gender_display()}）',
        'age_years': age,
        'period_label': (
            f'统计区间: {start.isoformat()} - {today.isoformat()} '
            f'(膳食、任务、运动睡眠)'
        ),
        'daily_rows': daily_rows,
        'totals': {
            'kcal': total_calories,
            'protein': total_protein,
            'carb': total_carb,
            'fat': total_fat,
        },
        'avg_daily_score': avg_daily_score,
        'task_completed_count': task_completed,
        'tasks_summary': tasks_summary,
        'avg_daily_steps': round(step_sum / step_days, 1) if step_days else None,
        'health_days_with_data': step_days,
        'allergy_tags': child.allergy_tags if isinstance(child.allergy_tags, list) else [],
        'medical_tags': child.medical_tags if isinstance(child.medical_tags, list) else [],
        'intake': None if rec is None else {
            'calories_kcal_min': rec.calories_kcal_min,
            'calories_kcal_max': rec.calories_kcal_max,
            'protein_g_min': rec.protein_g_min,
            'protein_g_max': rec.protein_g_max,
            'notes': rec.notes,
        },
        'diet_notes': (child.diet_notes or '').strip(),
        'footer': footer,
        '_meta_start': start,
        '_meta_today': today,
    }


@login_required
def parent_export_weekly_pdf(request):
    """导出健康周报 PDF（膳食 + 任务 + 手环；默认近 7 天，含今天）。"""
    from urllib.parse import quote

    from .pdf_weekly import build_parent_weekly_pdf

    child, _children = _parent_resolve_child(request)
    if not child:
        return HttpResponse('未找到孩子信息', status=400, content_type='text/plain; charset=utf-8')

    days = max(1, min(30, int(request.GET.get('days', 7))))
    gen_at = timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')
    ctx = _weekly_pdf_ctx(child, days, footer=f'由健康管理家庭端生成, {gen_at}')
    start = ctx.pop('_meta_start')
    today = ctx.pop('_meta_today')

    pdf_bytes = build_parent_weekly_pdf(ctx)
    ascii_name = f'weekly_report_{child.id}_{start}_{today}.pdf'
    display_name = f'健康周报_{child.nickname}_{start}_{today}.pdf'
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = (
        f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(display_name)}'
    )
    return resp


@login_required
@user_passes_test(is_teacher)
def school_export_weekly_pdf(request):
    """学校端：为本班一名学生导出与家长端同口径的健康周报 PDF。"""
    from urllib.parse import quote

    from .pdf_weekly import build_parent_weekly_pdf

    teacher = request.user.teacher_profile
    try:
        child_id = int(request.GET.get('child_id', '0'))
    except ValueError:
        return HttpResponse('参数 child_id 无效', status=400, content_type='text/plain; charset=utf-8')

    if not ClassStudent.objects.filter(teacher=teacher, child_id=child_id).exists():
        return HttpResponse('无权导出该学生或学生不在本班', status=403, content_type='text/plain; charset=utf-8')

    child = get_object_or_404(Child, id=child_id)
    days = max(1, min(30, int(request.GET.get('days', 7))))
    gen_at = timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')
    src = f'{teacher.school.name} {teacher.class_name} 学校端'
    ctx = _weekly_pdf_ctx(child, days, footer=f'由 {src} 生成, {gen_at}')
    start = ctx.pop('_meta_start')
    today = ctx.pop('_meta_today')

    pdf_bytes = build_parent_weekly_pdf(ctx)
    ascii_name = f'school_weekly_{child.id}_{start}_{today}.pdf'
    display_name = f'健康周报_{child.nickname}_{start}_{today}.pdf'
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = (
        f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(display_name)}'
    )
    return resp


@login_required
def parent_get_teachers(request):
    """获取所有教师列表"""
    teachers = Teacher.objects.all().select_related('school')
    return JsonResponse({
        'success': True,
        'teachers': [{
            'id': t.id,
            'name': t.user.username,
            'school': t.school.name,
            'class_name': t.class_name
        } for t in teachers]
    })


@login_required
@require_http_methods(["POST"])
def parent_add_to_class(request):
    """家长将孩子添加到班级"""
    child_id = request.POST.get('child_id')
    teacher_id = request.POST.get('teacher_id')

    if not child_id or not teacher_id:
        return JsonResponse({'success': False, 'message': '参数不完整'})

    children = Child.objects.filter(parent=request.user)
    try:
        child = children.get(id=int(child_id))
    except Child.DoesNotExist:
        return JsonResponse({'success': False, 'message': '未找到孩子'})

    try:
        teacher = Teacher.objects.get(id=int(teacher_id))
    except Teacher.DoesNotExist:
        return JsonResponse({'success': False, 'message': '未找到教师'})

    # 检查是否已存在关联
    if ClassStudent.objects.filter(teacher=teacher, child=child).exists():
        return JsonResponse({'success': False, 'message': '孩子已在该班级中'})

    ClassStudent.objects.create(teacher=teacher, child=child)
    return JsonResponse({'success': True, 'message': '已成功添加到班级'})


@login_required
@require_http_methods(["POST"])
def parent_set_child_class(request):
    """将孩子与班级的关联改为指定教师班级：先解除该孩子所有进班记录，再按需加入新班；不传 teacher_id 则仅退出。"""
    child_id = (request.POST.get('child_id') or '').strip()
    teacher_id_raw = (request.POST.get('teacher_id') or '').strip()

    if not child_id:
        return JsonResponse({'success': False, 'message': '请选择孩子'})

    children = Child.objects.filter(parent=request.user)
    try:
        child = children.get(id=int(child_id))
    except (Child.DoesNotExist, ValueError):
        return JsonResponse({'success': False, 'message': '未找到孩子'})

    ClassStudent.objects.filter(child=child).delete()

    if not teacher_id_raw or teacher_id_raw in ('0', 'none', 'null'):
        return JsonResponse({
            'success': True,
            'message': '已退出所有班级',
            'enrollments': [],
        })

    try:
        teacher = Teacher.objects.select_related('school', 'user').get(id=int(teacher_id_raw))
    except (ValueError, Teacher.DoesNotExist):
        return JsonResponse({'success': False, 'message': '未找到教师/班级'})

    ClassStudent.objects.create(teacher=teacher, child=child)
    return JsonResponse({
        'success': True,
        'message': f'已切换到 {teacher.school.name} · {teacher.class_name}',
        'enrollments': [{
            'teacher_id': teacher.id,
            'school': teacher.school.name,
            'class_name': teacher.class_name,
            'teacher_name': teacher.user.username,
        }],
    })


@login_required
def parent_bind_child(request):
    """家长通过绑定码关联儿童"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '仅支持POST请求'})

    bind_code = request.POST.get('bind_code', '').strip().upper()

    if not bind_code:
        return JsonResponse({'success': False, 'message': '请输入绑定码'})

    try:
        child = Child.objects.get(bind_code=bind_code)
    except Child.DoesNotExist:
        return JsonResponse({'success': False, 'message': '绑定码无效'})

    # 检查是否已被其他家长绑定
    if child.parent is not None:
        return JsonResponse({'success': False, 'message': '该儿童已被其他家长绑定'})

    # 绑定儿童
    child.parent = request.user
    child.save()

    return JsonResponse({'success': True, 'message': f'成功绑定儿童 {child.nickname}！'})


# ========== 健康数据 API（供Android App调用）==========

@login_required
@require_http_methods(["POST"])
def health_manual_input(request):
    """手动录入健康数据：JSON 请求体（App）或表单 / FormData（儿童端页面）。"""
    child = Child.objects.filter(user=request.user).first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    today = timezone.now().date()
    ct = (request.content_type or '').lower()

    if 'application/json' in ct and request.body:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '无效的JSON数据'})
        try:
            health_data, created = HealthData.objects.get_or_create(
                child=child,
                date=today,
                defaults={
                    'steps': int(data.get('steps', 0) or 0),
                    'step_goal': int(data.get('step_goal', 8000) or 8000),
                    'active_minutes': int(data.get('active_minutes', 0) or 0),
                    'calories_burned': float(data.get('calories_burned', 0) or 0),
                    'heart_rate_avg': int(data.get('heart_rate_avg', 0) or 0),
                    'heart_rate_max': int(data.get('heart_rate_max', 0) or 0),
                    'heart_rate_min': int(data.get('heart_rate_min', 0) or 0),
                    'sleep_duration_minutes': int(data.get('sleep_duration_minutes', 0) or 0),
                    'deep_sleep_minutes': int(data.get('deep_sleep_minutes', 0) or 0),
                    'light_sleep_minutes': int(data.get('light_sleep_minutes', 0) or 0),
                    'rem_sleep_minutes': int(data.get('rem_sleep_minutes', 0) or 0),
                },
            )
            if not created:
                health_data.steps = int(data.get('steps', health_data.steps) or 0)
                health_data.step_goal = int(data.get('step_goal', health_data.step_goal) or 8000)
                health_data.active_minutes = int(data.get('active_minutes', health_data.active_minutes) or 0)
                health_data.calories_burned = float(data.get('calories_burned', health_data.calories_burned) or 0)
                health_data.heart_rate_avg = int(data.get('heart_rate_avg', health_data.heart_rate_avg) or 0)
                health_data.heart_rate_max = int(data.get('heart_rate_max', health_data.heart_rate_max) or 0)
                health_data.heart_rate_min = int(data.get('heart_rate_min', health_data.heart_rate_min) or 0)
                health_data.sleep_duration_minutes = int(
                    data.get('sleep_duration_minutes', health_data.sleep_duration_minutes) or 0
                )
                health_data.deep_sleep_minutes = int(data.get('deep_sleep_minutes', health_data.deep_sleep_minutes) or 0)
                health_data.light_sleep_minutes = int(
                    data.get('light_sleep_minutes', health_data.light_sleep_minutes) or 0
                )
                health_data.rem_sleep_minutes = int(data.get('rem_sleep_minutes', health_data.rem_sleep_minutes) or 0)
                health_data.save()
            return JsonResponse({'success': True, 'message': '数据已保存'})
        except (TypeError, ValueError) as e:
            return JsonResponse({'success': False, 'message': str(e)})

    try:
        steps = int(request.POST.get('steps', 0))
        step_goal = int(request.POST.get('step_goal', 8000))
        active_minutes = int(request.POST.get('active_minutes', 0))
        calories_burned = float(request.POST.get('calories_burned', 0))
        heart_rate_avg = int(request.POST.get('heart_rate_avg', 0))
        heart_rate_max = int(request.POST.get('heart_rate_max', 0))
        heart_rate_min = int(request.POST.get('heart_rate_min', 0))
        sleep_hours = int(request.POST.get('sleep_hours', 0))
        sleep_minutes = int(request.POST.get('sleep_minutes', 0))
        sleep_duration_minutes = sleep_hours * 60 + sleep_minutes
        deep_sleep_hours = int(request.POST.get('deep_sleep_hours', 0))
        deep_sleep_minutes = int(request.POST.get('deep_sleep_minutes', 0))
        deep_sleep_minutes = deep_sleep_hours * 60 + deep_sleep_minutes
        light_sleep_hours = int(request.POST.get('light_sleep_hours', 0))
        light_sleep_minutes = int(request.POST.get('light_sleep_minutes', 0))
        light_sleep_minutes = light_sleep_hours * 60 + light_sleep_minutes
        rem_sleep_hours = int(request.POST.get('rem_sleep_hours', 0))
        rem_sleep_minutes = int(request.POST.get('rem_sleep_minutes', 0))
        rem_sleep_minutes = rem_sleep_hours * 60 + rem_sleep_minutes

        health_data, created = HealthData.objects.get_or_create(
            child=child,
            date=today,
            defaults={
                'steps': steps,
                'step_goal': step_goal,
                'active_minutes': active_minutes,
                'calories_burned': calories_burned,
                'heart_rate_avg': heart_rate_avg,
                'heart_rate_max': heart_rate_max,
                'heart_rate_min': heart_rate_min,
                'sleep_duration_minutes': sleep_duration_minutes,
                'deep_sleep_minutes': deep_sleep_minutes,
                'light_sleep_minutes': light_sleep_minutes,
                'rem_sleep_minutes': rem_sleep_minutes,
            },
        )

        if not created:
            health_data.steps = steps
            health_data.step_goal = step_goal
            health_data.active_minutes = active_minutes
            health_data.calories_burned = calories_burned
            health_data.heart_rate_avg = heart_rate_avg
            health_data.heart_rate_max = heart_rate_max
            health_data.heart_rate_min = heart_rate_min
            health_data.sleep_duration_minutes = sleep_duration_minutes
            health_data.deep_sleep_minutes = deep_sleep_minutes
            health_data.light_sleep_minutes = light_sleep_minutes
            health_data.rem_sleep_minutes = rem_sleep_minutes
            health_data.save()

        return JsonResponse({'success': True, 'message': '健康数据已保存'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '请输入有效的数字'})


@login_required
@require_http_methods(["POST"])
def health_sync(request):
    """接收Android App推送的手环健康数据"""
    try:
        import json
        data = json.loads(request.body)

        child_id = data.get('child_id')
        if not child_id:
            return JsonResponse({'success': False, 'message': '缺少child_id'})

        children = Child.objects.filter(parent=request.user)
        if not children.filter(id=child_id).exists():
            return JsonResponse({'success': False, 'message': '无权访问该儿童数据'})

        child = children.get(id=child_id)

        date_str = data.get('date')
        if not date_str:
            return JsonResponse({'success': False, 'message': '缺少date字段'})

        from datetime import datetime
        date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # 创建或更新健康数据
        health_data, created = HealthData.objects.get_or_create(
            child=child,
            date=date,
            defaults={
                'steps': data.get('steps', 0),
                'step_goal': data.get('step_goal', 8000),
                'active_minutes': data.get('active_minutes', 0),
                'calories_burned': data.get('calories_burned', 0),
                'heart_rate_avg': data.get('heart_rate_avg', 0),
                'heart_rate_max': data.get('heart_rate_max', 0),
                'heart_rate_min': data.get('heart_rate_min', 0),
                'sleep_duration_minutes': data.get('sleep_duration_minutes', 0),
                'deep_sleep_minutes': data.get('deep_sleep_minutes', 0),
                'light_sleep_minutes': data.get('light_sleep_minutes', 0),
                'rem_sleep_minutes': data.get('rem_sleep_minutes', 0),
            }
        )

        if not created:
            # 更新已有记录
            health_data.steps = data.get('steps', health_data.steps)
            health_data.step_goal = data.get('step_goal', health_data.step_goal)
            health_data.active_minutes = data.get('active_minutes', health_data.active_minutes)
            health_data.calories_burned = data.get('calories_burned', health_data.calories_burned)
            health_data.heart_rate_avg = data.get('heart_rate_avg', health_data.heart_rate_avg)
            health_data.heart_rate_max = data.get('heart_rate_max', health_data.heart_rate_max)
            health_data.heart_rate_min = data.get('heart_rate_min', health_data.heart_rate_min)
            health_data.sleep_duration_minutes = data.get('sleep_duration_minutes', health_data.sleep_duration_minutes)
            health_data.deep_sleep_minutes = data.get('deep_sleep_minutes', health_data.deep_sleep_minutes)
            health_data.light_sleep_minutes = data.get('light_sleep_minutes', health_data.light_sleep_minutes)
            health_data.rem_sleep_minutes = data.get('rem_sleep_minutes', health_data.rem_sleep_minutes)
            health_data.save()

        return JsonResponse({
            'success': True,
            'message': '数据同步成功',
            'health_id': health_data.id
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': '无效的JSON数据'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["GET"])
def health_latest(request):
    """获取最近一次同步的健康数据"""
    child_id = request.GET.get('child_id')
    if not child_id:
        return JsonResponse({'success': False, 'message': '缺少child_id'})

    children = Child.objects.filter(parent=request.user)
    if not children.filter(id=child_id).exists():
        return JsonResponse({'success': False, 'message': '无权访问该儿童数据'})

    child = children.get(id=child_id)
    latest = HealthData.objects.filter(child=child).order_by('-date', '-last_sync').first()

    if not latest:
        return JsonResponse({
            'success': True,
            'data': None,
            'message': '暂无数据'
        })

    return JsonResponse({
        'success': True,
        'data': {
            'date': latest.date.isoformat(),
            'steps': latest.steps,
            'step_goal': latest.step_goal,
            'step_percent': int(latest.steps / latest.step_goal * 100) if latest.step_goal > 0 else 0,
            'active_minutes': latest.active_minutes,
            'calories_burned': latest.calories_burned,
            'heart_rate_avg': latest.heart_rate_avg,
            'heart_rate_max': latest.heart_rate_max,
            'heart_rate_min': latest.heart_rate_min,
            'sleep_duration_minutes': latest.sleep_duration_minutes,
            'deep_sleep_minutes': latest.deep_sleep_minutes,
            'light_sleep_minutes': latest.light_sleep_minutes,
            'rem_sleep_minutes': latest.rem_sleep_minutes,
            'last_sync': latest.last_sync.isoformat() if latest.last_sync else None,
        }
    })


@login_required
@require_http_methods(["GET"])
def health_history(request):
    """获取历史健康数据"""
    child_id = request.GET.get('child_id')
    days = int(request.GET.get('days', 7))

    if not child_id:
        return JsonResponse({'success': False, 'message': '缺少child_id'})

    children = Child.objects.filter(parent=request.user)
    if not children.filter(id=child_id).exists():
        return JsonResponse({'success': False, 'message': '无权访问该儿童数据'})

    child = children.get(id=child_id)
    start_date = timezone.now().date() - timedelta(days=days)

    records = HealthData.objects.filter(
        child=child,
        date__gte=start_date
    ).order_by('-date')

    return JsonResponse({
        'success': True,
        'records': [{
            'date': r.date.isoformat(),
            'steps': r.steps,
            'step_goal': r.step_goal,
            'step_percent': int(r.steps / r.step_goal * 100) if r.step_goal > 0 else 0,
            'active_minutes': r.active_minutes,
            'calories_burned': r.calories_burned,
            'heart_rate_avg': r.heart_rate_avg,
            'sleep_duration_minutes': r.sleep_duration_minutes,
            'deep_sleep_minutes': r.deep_sleep_minutes,
            'light_sleep_minutes': r.light_sleep_minutes,
        } for r in records]
    })


@login_required
@require_http_methods(["GET"])
def health_today(request):
    """获取今日健康数据（用于Dashboard轮询）"""
    child_id = request.GET.get('child_id')

    if child_id:
        children = Child.objects.filter(parent=request.user)
        if not children.filter(id=child_id).exists():
            return JsonResponse({'success': False, 'message': '无权访问该儿童数据'})
        child = children.get(id=child_id)
    else:
        child = Child.objects.filter(user=request.user).first()
        if not child:
            return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    today = timezone.now().date()
    health = HealthData.objects.filter(child=child, date=today).first()

    if not health:
        return JsonResponse({
            'success': True,
            'data': None,
            'message': '今日暂无数据'
        })

    return JsonResponse({
        'success': True,
        'data': {
            'date': health.date.isoformat(),
            'steps': health.steps,
            'step_goal': health.step_goal,
            'step_percent': int(health.steps / health.step_goal * 100) if health.step_goal > 0 else 0,
            'active_minutes': health.active_minutes,
            'calories_burned': health.calories_burned,
            'heart_rate_avg': health.heart_rate_avg,
            'heart_rate_max': health.heart_rate_max,
            'heart_rate_min': health.heart_rate_min,
            'sleep_duration_minutes': health.sleep_duration_minutes,
            'deep_sleep_minutes': health.deep_sleep_minutes,
            'light_sleep_minutes': health.light_sleep_minutes,
            'rem_sleep_minutes': health.rem_sleep_minutes,
            'last_sync': health.last_sync.isoformat() if health.last_sync else None,
        }
    })


@login_required
@require_http_methods(["POST"])
def health_auto_generate(request):
    """随机生成正常范围内的健康数据（模拟手环数据）"""
    import random

    child = Child.objects.filter(user=request.user).first()
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    today = timezone.now().date()

    # 生成正常范围内的随机数据
    steps = random.randint(3000, 12000)  # 步数 3000-12000
    step_goal = 8000
    active_minutes = random.randint(30, 180)  # 活动分钟 30-180
    calories_burned = random.randint(100, 500)  # 消耗卡路里 100-500

    # 心率（儿童正常心率60-120，平均80-100）
    heart_rate_avg = random.randint(70, 110)
    heart_rate_max = heart_rate_avg + random.randint(20, 40)
    heart_rate_min = heart_rate_avg - random.randint(15, 25)

    # 睡眠（儿童需要8-10小时睡眠）
    sleep_duration_minutes = random.randint(420, 600)  # 7-10小时
    deep_sleep_minutes = int(sleep_duration_minutes * random.uniform(0.2, 0.35))  # 深睡20-35%
    light_sleep_minutes = int(sleep_duration_minutes * random.uniform(0.45, 0.55))  # 浅睡45-55%
    rem_sleep_minutes = sleep_duration_minutes - deep_sleep_minutes - light_sleep_minutes  # REM

    # 创建或更新健康数据
    health_data, created = HealthData.objects.get_or_create(
        child=child,
        date=today,
        defaults={
            'steps': steps,
            'step_goal': step_goal,
            'active_minutes': active_minutes,
            'calories_burned': calories_burned,
            'heart_rate_avg': heart_rate_avg,
            'heart_rate_max': heart_rate_max,
            'heart_rate_min': heart_rate_min,
            'sleep_duration_minutes': sleep_duration_minutes,
            'deep_sleep_minutes': deep_sleep_minutes,
            'light_sleep_minutes': light_sleep_minutes,
            'rem_sleep_minutes': rem_sleep_minutes,
        }
    )

    if not created:
        health_data.steps = steps
        health_data.step_goal = step_goal
        health_data.active_minutes = active_minutes
        health_data.calories_burned = calories_burned
        health_data.heart_rate_avg = heart_rate_avg
        health_data.heart_rate_max = heart_rate_max
        health_data.heart_rate_min = heart_rate_min
        health_data.sleep_duration_minutes = sleep_duration_minutes
        health_data.deep_sleep_minutes = deep_sleep_minutes
        health_data.light_sleep_minutes = light_sleep_minutes
        health_data.rem_sleep_minutes = rem_sleep_minutes
        health_data.save()

    return JsonResponse({
        'success': True,
        'message': '已生成今日健康数据',
        'data': {
            'date': today.isoformat(),
            'steps': steps,
            'step_goal': step_goal,
            'step_percent': int(steps / step_goal * 100),
            'active_minutes': active_minutes,
            'calories_burned': calories_burned,
            'heart_rate_avg': heart_rate_avg,
            'heart_rate_max': heart_rate_max,
            'heart_rate_min': heart_rate_min,
            'sleep_duration_minutes': sleep_duration_minutes,
            'deep_sleep_minutes': deep_sleep_minutes,
            'light_sleep_minutes': light_sleep_minutes,
            'rem_sleep_minutes': rem_sleep_minutes,
        }
    })


# ========== 学校端视图 ==========


def _school_anon_label(child_id, scope_id):
    digest = hashlib.sha256(f'{child_id}-{scope_id}-campus'.encode()).hexdigest()[:5].upper()
    return f'匿名 · {digest}'


def _teacher_class_children(teacher):
    return Child.objects.filter(class_enrollments__teacher=teacher).distinct()


def _challenge_audience_children(challenge):
    if challenge.scope == 'school':
        t_ids = Teacher.objects.filter(school=challenge.teacher.school).values_list('id', flat=True)
        return Child.objects.filter(class_enrollments__teacher_id__in=t_ids).distinct()
    return _teacher_class_children(challenge.teacher)


def _challenge_progress_count(challenge, child):
    """在挑战时间窗口内，根据类型统计进度（仅读既有膳食/任务数据，不改儿童端逻辑）。"""
    today = timezone.now().date()
    end = min(challenge.end_date, today)
    start = challenge.start_date
    if end < start:
        return 0
    ctype = (challenge.challenge_type or '').lower()
    if ctype in ('nutrition', 'meal', 'diet', 'grain', '全谷物'):
        days = MealRecord.objects.filter(
            child=child, date__gte=start, date__lte=end
        ).values_list('date', flat=True).distinct()
        return len(set(days))
    if ctype in ('exercise', 'sport', '运动'):
        return TaskRecord.objects.filter(
            child=child, task__code='exercise',
            date__gte=start, date__lte=end, status='completed',
        ).count()
    if ctype in ('vegetable', 'veggie', '蔬菜', '彩虹'):
        return TaskRecord.objects.filter(
            child=child, task__code='veggie',
            date__gte=start, date__lte=end, status='completed',
        ).count()
    if ctype in ('sleep', '早睡'):
        return TaskRecord.objects.filter(
            child=child, task__code='sleep',
            date__gte=start, date__lte=end, status='completed',
        ).count()
    if ctype in ('wash', '卫生', '洗手'):
        return TaskRecord.objects.filter(
            child=child, task__code='wash',
            date__gte=start, date__lte=end, status='completed',
        ).count()
    return TaskRecord.objects.filter(
        child=child, date__gte=start, date__lte=end, status='completed'
    ).count()


def _challenge_stats_bundle(challenge, anon_scope):
    children = _challenge_audience_children(challenge)
    total = children.count()
    rows = []
    completed = 0
    target = max(challenge.target_value, 1)
    for child in children:
        raw = _challenge_progress_count(challenge, child)
        pct = min(100, int(raw / target * 100))
        done = raw >= challenge.target_value
        if done:
            completed += 1
        rows.append({
            'anon': _school_anon_label(child.id, anon_scope.id),
            'progress': raw,
            'percent': pct,
            'done': done,
        })
    rows.sort(key=lambda x: -x['progress'])
    return {
        'student_count': total,
        'completed_count': completed,
        'completion_rate': round(completed / total * 100, 1) if total else 0.0,
        'avg_progress_percent': round(sum(r['percent'] for r in rows) / len(rows), 1) if rows else 0.0,
        'leaderboard': rows[:25],
    }


def _class_health_overview(teacher, days=7):
    today = timezone.now().date()
    start = today - timedelta(days=days - 1)
    children = _teacher_class_children(teacher)
    child_ids = list(children.values_list('id', flat=True))
    n = len(child_ids)
    if n == 0:
        return {
            'period_days': days,
            'avg_protein': 0.0,
            'avg_carbohydrate': 0.0,
            'avg_fat': 0.0,
            'avg_calories': 0.0,
            'food_diversity_index': 0.0,
            'meal_checkin_rate': 0.0,
            'task_pass_rate': 0.0,
        }
    meals = MealRecord.objects.filter(child_id__in=child_ids, date__gte=start, date__lte=today)
    agg = meals.aggregate(
        Avg('total_protein'),
        Avg('total_carbohydrate'),
        Avg('total_fat'),
        Avg('total_calories'),
    )
    diversity_scores = []
    for child in children:
        dcount = MealFoodItem.objects.filter(
            meal_record__child=child,
            meal_record__date__gte=start,
            meal_record__date__lte=today,
        ).values('food__category').distinct().count()
        diversity_scores.append(min(100.0, dcount / 5.0 * 100.0))
    diversity = round(sum(diversity_scores) / len(diversity_scores), 1) if diversity_scores else 0.0
    expected_child_days = n * days
    checkins = 0
    for child in children:
        checkins += MealRecord.objects.filter(
            child=child, date__gte=start, date__lte=today
        ).values('date').distinct().count()
    meal_rate = round(checkins / expected_child_days * 100, 1) if expected_child_days else 0.0
    tasks = Task.objects.all()
    task_rates = []
    for task in tasks:
        denom = n * days
        num = TaskRecord.objects.filter(
            child_id__in=child_ids, task=task,
            date__gte=start, date__lte=today, status='completed',
        ).count()
        task_rates.append(num / denom * 100 if denom else 0)
    task_pass = round(sum(task_rates) / len(task_rates), 1) if task_rates else 0.0
    return {
        'period_days': days,
        'avg_protein': round(agg['total_protein__avg'] or 0, 1),
        'avg_carbohydrate': round(agg['total_carbohydrate__avg'] or 0, 1),
        'avg_fat': round(agg['total_fat__avg'] or 0, 1),
        'avg_calories': round(agg['total_calories__avg'] or 0, 1),
        'food_diversity_index': diversity,
        'meal_checkin_rate': meal_rate,
        'task_pass_rate': task_pass,
    }


def _anonymous_health_ranking(teacher, days=7):
    today = timezone.now().date()
    start = today - timedelta(days=days - 1)
    ranked = []
    for child in _teacher_class_children(teacher):
        meals_n = MealRecord.objects.filter(
            child=child, date__gte=start, date__lte=today
        ).count()
        task_n = TaskRecord.objects.filter(
            child=child, date__gte=start, date__lte=today, status='completed'
        ).count()
        cats = MealFoodItem.objects.filter(
            meal_record__child=child,
            meal_record__date__gte=start,
            meal_record__date__lte=today,
        ).values('food__category').distinct().count()
        score = task_n * 10 + meals_n * 5 + cats * 8
        ranked.append({
            'anon': _school_anon_label(child.id, teacher.id),
            'child_name': child.name,
            'child_nickname': child.nickname,
            'score': score,
            'tasks_ok': task_n,
            'meal_logs': meals_n,
            'food_categories': cats,
        })
    ranked.sort(key=lambda x: -x['score'])
    for i, row in enumerate(ranked, 1):
        row['rank'] = i
    return ranked


def _desensitized_alerts(teacher):
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    three_ago = today - timedelta(days=3)
    alerts = []
    child_ids = list(ClassStudent.objects.filter(teacher=teacher).values_list('child_id', flat=True))

    # 过敏预警：来自 HealthAlert（家长端/儿童端触发后上传）
    for alert in HealthAlert.objects.filter(child_id__in=child_ids, alert_type='allergy').order_by('-created_at')[:20]:
        child = alert.child
        label = _school_anon_label(child.id, teacher.id)
        hits = alert.payload.get('hits', []) if isinstance(alert.payload, dict) else []
        tags = ', '.join(sorted({h['tag'] for h in hits})) if hits else ''
        alerts.append({
            'level': 'high',
            'type': '过敏预警',
            'anon': label,
            'child_name': child.name,
            'child_nickname': child.nickname,
            'text': f"{alert.message or '检测到过敏原'}{'（' + tags + '）' if tags else ''}",
            'child_id': child.id,
        })

    for child in _teacher_class_children(teacher):
        label = _school_anon_label(child.id, teacher.id)
        recent_meals = MealRecord.objects.filter(child=child, date__gte=three_ago, date__lte=today).count()
        if recent_meals == 0:
            alerts.append({
                'level': 'high',
                'type': '膳食打卡异常',
                'anon': label,
                'child_name': child.name,
                'child_nickname': child.nickname,
                'text': '近 3 日未见膳食记录，建议关注家庭端配合。',
            })
        week_tasks = TaskRecord.objects.filter(
            child=child, date__gte=week_ago, date__lte=today, status='completed'
        ).count()
        if week_tasks < 2:
            alerts.append({
                'level': 'medium',
                'type': '健康任务偏低',
                'anon': label,
                'child_name': child.name,
                'child_nickname': child.nickname,
                'text': '近一周任务完成次数偏少，可进行个体化沟通。',
            })
        wmeals = MealRecord.objects.filter(child=child, date__gte=week_ago, date__lte=today)
        if wmeals.exists():
            avg_cal = wmeals.aggregate(Avg('total_calories'))['total_calories__avg'] or 0
            if 0 < avg_cal < 350:
                alerts.append({
                    'level': 'medium',
                    'type': '热量估算偏低',
                    'anon': label,
                    'child_name': child.name,
                    'child_nickname': child.nickname,
                    'text': '周均膳食热量估算偏低，可结合营养师建议随访。',
                })
    return alerts


def _sync_resource_unlocks(resource):
    children = _teacher_class_children(resource.teacher)
    if not resource.unlock_requires_task:
        for child in children:
            HealthResourceUnlock.objects.get_or_create(resource=resource, child=child)
        return
    if not resource.pushed_at:
        return
    since = resource.pushed_at.date()
    for child in children:
        if TaskRecord.objects.filter(
            child=child, date__gte=since, status='completed'
        ).exists():
            HealthResourceUnlock.objects.get_or_create(resource=resource, child=child)


def _challenges_visible_to_teacher(teacher):
    """本校范围内：本人发起 + 同校校级挑战。"""
    return HealthChallenge.objects.filter(
        Q(teacher=teacher) | Q(scope='school', teacher__school=teacher.school)
    ).distinct()


def _active_challenges_visible_to_teacher(teacher):
    return _challenges_visible_to_teacher(teacher).filter(status='active')


def _ensure_challenge_progress_rows(challenge):
    """儿童端依赖 ChallengeProgress，发布挑战时必须为学生建档。"""
    for child in _challenge_audience_children(challenge):
        ChallengeProgress.objects.get_or_create(
            challenge=challenge,
            child=child,
            defaults={'current_value': 0, 'is_completed': False},
        )


def _sync_challenge_progress_to_children(challenge):
    """根据既有打卡/膳食数据刷新进度，写入儿童端同一套模型。"""
    if challenge.status != 'active':
        return
    for prog in ChallengeProgress.objects.filter(challenge=challenge).select_related('child'):
        raw = _challenge_progress_count(challenge, prog.child)
        capped = min(raw, challenge.target_value)
        done = raw >= challenge.target_value
        prog.current_value = capped
        prog.is_completed = done
        if done and prog.completed_at is None:
            prog.completed_at = timezone.now()
        elif not done:
            prog.completed_at = None
        prog.save()


def _sync_all_active_challenges_for_teacher(teacher):
    for c in _active_challenges_visible_to_teacher(teacher):
        _ensure_challenge_progress_rows(c)
        _sync_challenge_progress_to_children(c)


def _broadcast_encouragements(sender_user, children, message):
    """复用家长端/儿童端已在用的 Encouragement，作班级通知。"""
    text = (message or '').strip()
    if not text:
        return
    text = text[:1900]
    for child in children:
        Encouragement.objects.create(sender=sender_user, child=child, message=text)


@login_required
@user_passes_test(is_teacher)
def school_dashboard(request):
    """学校端首页 — 校园健康教育管理中枢"""
    teacher = request.user.teacher_profile
    _sync_all_active_challenges_for_teacher(teacher)
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    students_data = []
    total_tasks = Task.objects.count()
    if total_tasks == 0:
        total_tasks = 4

    for enrollment in ClassStudent.objects.filter(teacher=teacher).select_related('child'):
        child = enrollment.child
        week_records = TaskRecord.objects.filter(
            child=child, date__gte=week_ago, status='completed'
        )

        student_tasks = {}
        for day_offset in range(7):
            day = week_ago + timedelta(days=day_offset)
            day_count = week_records.filter(date=day).count()
            student_tasks[day.isoformat()] = day_count

        avg_tasks = sum(student_tasks.values()) / 7 if student_tasks else 0

        hp = _intake_and_tags_for_child(child)

        today_meals = MealRecord.objects.filter(child=child, date=today)
        today_meal_totals = {'kcal': 0.0, 'protein': 0.0, 'carb': 0.0, 'fat': 0.0, 'count': 0}
        for m in today_meals:
            today_meal_totals['kcal'] += float(m.total_calories or 0)
            today_meal_totals['protein'] += float(m.total_protein or 0)
            today_meal_totals['carb'] += float(m.total_carbohydrate or 0)
            today_meal_totals['fat'] += float(m.total_fat or 0)
            today_meal_totals['count'] += 1

        students_data.append({
            'id': child.id,
            'nickname': child.nickname,
            'level': child.level,
            'week_tasks': week_records.count(),
            'avg_tasks': round(avg_tasks, 1),
            'daily_tasks': student_tasks,
            'age_years': hp['age_years'],
            'intake_recommendation': hp['recommendation'],
            'today_meal_totals': today_meal_totals,
            'allergy_tags': hp['allergy_tags'],
            'medical_tags': hp['medical_tags'],
        })

    students_data.sort(key=lambda x: x['level'], reverse=True)

    all_pending = []
    for enrollment in ClassStudent.objects.filter(teacher=teacher).select_related('child'):
        child = enrollment.child
        pending = TaskRecord.objects.filter(
            child=child, date=today, status='pending'
        ).count()
        if pending > 0:
            all_pending.append({
                'child_id': child.id,
                'child_nickname': child.nickname,
                'pending_count': pending
            })

    activities = Activity.objects.filter(teacher=teacher, is_active=True).order_by('-created_at')[:5]
    challenges = _challenges_visible_to_teacher(teacher).order_by('-created_at')[:25]
    challenge_stats = {c.id: _challenge_stats_bundle(c, teacher) for c in challenges}
    challenges_with_stats = [{'challenge': c, 'stats': challenge_stats[c.id]} for c in challenges]

    overview = _class_health_overview(teacher)
    acal = overview['avg_calories'] or 0
    overview['bar_calories_pct'] = min(100, int(acal / 6)) if acal else 0
    overview['bar_protein_pct'] = min(100, int((overview['avg_protein'] or 0) / 0.5))
    overview['bar_carb_pct'] = min(100, int((overview['avg_carbohydrate'] or 0) / 0.8))
    anon_ranking = _anonymous_health_ranking(teacher)
    alerts = _desensitized_alerts(teacher)

    resources = HealthCourseResource.objects.filter(teacher=teacher).order_by('-created_at')[:40]
    resource_rows = []
    class_size = _teacher_class_children(teacher).count()
    for r in resources:
        unlocked = r.unlocks.count()
        resource_rows.append({
            'obj': r,
            'unlocked': unlocked,
            'class_size': class_size,
            'unlock_pct': round(unlocked / class_size * 100, 1) if class_size else 0.0,
        })

    messages = SchoolHomeMessage.objects.filter(teacher=teacher)[:40]
    archives = SchoolHealthArchive.objects.filter(teacher=teacher)[:20]

    school_peer_teachers = Teacher.objects.filter(school=teacher.school).exclude(pk=teacher.pk)

    return render(request, 'school/dashboard.html', {
        'teacher': teacher,
        'students_data': students_data,
        'all_pending': all_pending,
        'activities': activities,
        'challenges': challenges,
        'challenges_with_stats': challenges_with_stats,
        'challenge_stats': challenge_stats,
        'total_tasks': total_tasks,
        'overview': overview,
        'anon_ranking': anon_ranking,
        'alerts': alerts,
        'resource_rows': resource_rows,
        'messages': messages,
        'archives': archives,
        'school_peer_teachers': school_peer_teachers,
    })


@login_required
@user_passes_test(is_teacher)
def school_health_alerts(request):
    """学校端拉取本班级孩子的预警列表（用于提醒老师）。"""
    teacher = request.user.teacher_profile
    limit = max(1, min(200, int(request.GET.get('limit', 100))))
    child_ids = list(ClassStudent.objects.filter(teacher=teacher).values_list('child_id', flat=True))
    alerts = HealthAlert.objects.filter(child_id__in=child_ids).order_by('-created_at')[:limit]
    return JsonResponse({
        'success': True,
        'alerts': [{
            'id': a.id,
            'child_id': a.child_id,
            'child_nickname': a.child.nickname,
            'type': a.alert_type,
            'title': a.title,
            'message': a.message,
            'created_at': timezone.localtime(a.created_at).strftime('%Y-%m-%d %H:%M'),
            'is_read': a.is_read_by_teacher,
            'payload': a.payload,
        } for a in alerts],
    })


@login_required
@user_passes_test(is_teacher)
@require_http_methods(["POST"])
def school_mark_alert_read(request, alert_id):
    """学校端标记预警已读。"""
    teacher = request.user.teacher_profile
    child_ids = list(ClassStudent.objects.filter(teacher=teacher).values_list('child_id', flat=True))
    alert = get_object_or_404(HealthAlert, id=alert_id, child_id__in=child_ids)
    alert.is_read_by_teacher = True
    alert.save(update_fields=['is_read_by_teacher'])
    return JsonResponse({'success': True})


@login_required
@user_passes_test(is_teacher)
@require_http_methods(["POST"])
def school_create_activity(request):
    """学校端创建活动"""
    teacher = request.user.teacher_profile
    title = content = activity_type = None
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'JSON 无效'})
        title = (payload.get('title') or '').strip()
        content = (payload.get('content') or '').strip()
        activity_type = (payload.get('activity_type') or 'challenge').strip()
    else:
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        activity_type = request.POST.get('activity_type', 'challenge')

    if not title or not content:
        return JsonResponse({'success': False, 'message': '标题和内容不能为空'})

    Activity.objects.create(
        teacher=teacher,
        title=title,
        content=content,
        activity_type=activity_type
    )
    msg = (
        f"【班级活动】{teacher.school.name} · {teacher.class_name}\n"
        f"{title}\n{content[:900]}"
    )
    _broadcast_encouragements(teacher.user, _teacher_class_children(teacher), msg)

    return JsonResponse({'success': True, 'message': '活动已发布'})


@login_required
@user_passes_test(is_teacher)
@require_http_methods(["POST"])
def school_create_challenge(request):
    """学校端创建健康挑战赛"""
    teacher = request.user.teacher_profile
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    challenge_type = request.POST.get('challenge_type', 'nutrition')
    start_date = request.POST.get('start_date')
    end_date = request.POST.get('end_date')
    target_value = int(request.POST.get('target_value', 7))
    power_reward = int(request.POST.get('power_reward', 50))
    scope = request.POST.get('scope', 'class')
    rule_description = request.POST.get('rule_description', '').strip()
    reward_description = request.POST.get('reward_description', '').strip()

    if scope not in ('class', 'school'):
        scope = 'class'

    if not title or not description or not start_date or not end_date:
        return JsonResponse({'success': False, 'message': '请填写完整信息'})

    from datetime import datetime
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()

    challenge = HealthChallenge.objects.create(
        teacher=teacher,
        title=title,
        description=description,
        challenge_type=challenge_type,
        start_date=start,
        end_date=end,
        target_value=target_value,
        power_reward=power_reward,
        scope=scope,
        rule_description=rule_description,
        reward_description=reward_description,
    )
    _ensure_challenge_progress_rows(challenge)
    _sync_challenge_progress_to_children(challenge)
    tip = f"时间 {start} ~ {end}\n{description[:800]}"
    if reward_description:
        tip += f"\n奖励说明：{reward_description[:300]}"
    _broadcast_encouragements(
        teacher.user,
        _challenge_audience_children(challenge),
        f"【健康挑战】{title}\n{tip}",
    )

    return JsonResponse({'success': True, 'message': '挑战赛已发布'})


@login_required
@user_passes_test(is_teacher)
def school_class_stats(request):
    """班级统计数据（膳食与任务，供看板图表）"""
    teacher = request.user.teacher_profile
    overview = _class_health_overview(teacher)
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    tasks = Task.objects.all()
    task_stats = []

    for task in tasks:
        total = 0
        for enrollment in ClassStudent.objects.filter(teacher=teacher):
            count = TaskRecord.objects.filter(
                child=enrollment.child, task=task,
                date__gte=week_ago, status='completed'
            ).count()
            total += count

        avg_rate = 0
        student_count = ClassStudent.objects.filter(teacher=teacher).count()
        if student_count > 0:
            avg_rate = total / (student_count * 7) * 100

        task_stats.append({
            'name': task.name,
            'icon': task.icon,
            'avg_rate': round(avg_rate, 1),
            'total': total
        })

    overall_rate = sum(s['avg_rate'] for s in task_stats) / len(task_stats) if task_stats else 0

    return JsonResponse({
        'task_stats': task_stats,
        'overall_rate': round(overall_rate, 1),
        'overview': overview,
    })


@login_required
@user_passes_test(is_teacher)
def school_challenge_stats(request, pk):
    teacher = request.user.teacher_profile
    challenge = get_object_or_404(
        HealthChallenge.objects.filter(
            Q(teacher=teacher) | Q(scope='school', teacher__school=teacher.school)
        ),
        pk=pk,
    )
    bundle = _challenge_stats_bundle(challenge, teacher)
    return JsonResponse(bundle)


@login_required
@user_passes_test(is_teacher)
@require_http_methods(['POST'])
def school_challenge_finalize(request, pk):
    """结束挑战并生成总结报告（存于 HealthChallenge.summary_report）"""
    teacher = request.user.teacher_profile
    challenge = get_object_or_404(HealthChallenge, pk=pk, teacher=teacher)
    bundle = _challenge_stats_bundle(challenge, teacher)
    custom = request.POST.get('summary', '').strip()
    auto = (
        f"【{challenge.title}】挑战总结\n"
        f"范围：{challenge.get_scope_display()}\n"
        f"时间：{challenge.start_date} ~ {challenge.end_date}\n"
        f"参与席位：{bundle['student_count']}，达标：{bundle['completed_count']}\n"
        f"班级达标率：{bundle['completion_rate']}%，平均完成度：{bundle['avg_progress_percent']}%\n"
        f"规则回顾：{challenge.rule_description or '—'}\n"
        f"奖励说明：{challenge.reward_description or '—'}"
    )
    challenge.summary_report = custom or auto
    challenge.status = 'completed'
    challenge.save()
    return JsonResponse({'success': True, 'summary': challenge.summary_report})


@login_required
@user_passes_test(is_teacher)
@require_http_methods(['POST'])
def school_resource_create(request):
    teacher = request.user.teacher_profile
    title = request.POST.get('title', '').strip()
    resource_type = request.POST.get('resource_type', 'article')
    summary = request.POST.get('summary', '').strip()
    content = request.POST.get('content', '').strip()
    media_file = request.FILES.get('media_file')
    media_url = request.POST.get('media_url', '').strip()
    unlock_requires_task = request.POST.get('unlock_requires_task', '1') == '1'
    if not title:
        return JsonResponse({'success': False, 'message': '标题必填'})
    if media_file:
        import os
        from django.conf import settings
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'course_resources', str(teacher.id))
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{timezone.now().strftime('%Y%m%d%H%M%S')}_{media_file.name}"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, 'wb') as f:
            for chunk in media_file.chunks():
                f.write(chunk)
        media_url = f"/media/course_resources/{teacher.id}/{filename}"
    HealthCourseResource.objects.create(
        teacher=teacher,
        title=title,
        resource_type=resource_type,
        summary=summary,
        content=content,
        media_url=media_url,
        unlock_requires_task=unlock_requires_task,
    )
    return JsonResponse({'success': True})


@login_required
@user_passes_test(is_teacher)
@require_http_methods(['POST'])
def school_resource_push(request, pk):
    teacher = request.user.teacher_profile
    resource = get_object_or_404(HealthCourseResource, pk=pk, teacher=teacher)
    first_push = resource.pushed_at is None
    resource.pushed_at = timezone.now()
    resource.save()
    _sync_resource_unlocks(resource)
    if first_push:
        lines = [
            f"【健康微课】{resource.title}",
            resource.summary or '',
            resource.media_url or '',
        ]
        if resource.unlock_requires_task:
            lines.append('请完成健康打卡，系统将自动解锁本篇内容。')
        _broadcast_encouragements(
            teacher.user,
            _teacher_class_children(teacher),
            '\n'.join(s for s in lines if s),
        )
    return JsonResponse({'success': True, 'message': '已推送至本班家庭端可见队列，并同步打卡解锁'})


@login_required
@user_passes_test(is_teacher)
@require_http_methods(['POST'])
def school_resource_resync(request):
    teacher = request.user.teacher_profile
    rid = request.POST.get('resource_id')
    resource = get_object_or_404(HealthCourseResource, pk=rid, teacher=teacher)
    _sync_resource_unlocks(resource)
    return JsonResponse({'success': True, 'unlocked_count': resource.unlocks.count()})


@login_required
@user_passes_test(is_teacher)
@require_http_methods(['POST'])
def school_message_create(request):
    teacher = request.user.teacher_profile
    title = request.POST.get('title', '').strip()
    body = request.POST.get('body', '').strip()
    if not title or not body:
        return JsonResponse({'success': False, 'message': '请填写主题与沟通要点'})
    SchoolHomeMessage.objects.create(teacher=teacher, title=title, body=body)
    return JsonResponse({'success': True})


@login_required
@user_passes_test(is_teacher)
@require_http_methods(['POST'])
def school_archive_create(request):
    teacher = request.user.teacher_profile
    title = request.POST.get('title', '').strip()
    if not title:
        title = timezone.now().strftime('健康教育归档 %Y-%m-%d %H:%M')
    overview = _class_health_overview(teacher)
    ranking_sample = _anonymous_health_ranking(teacher)[:10]
    alerts = _desensitized_alerts(teacher)
    payload = {
        'overview': overview,
        'ranking_sample': ranking_sample,
        'alerts_count': len(alerts),
    }
    SchoolHealthArchive.objects.create(
        teacher=teacher,
        title=title,
        snapshot_json=json.dumps(payload, ensure_ascii=False),
    )
    return JsonResponse({'success': True})


# ========== 管理视图 ==========

def admin_setup(request):
    """初始化演示数据"""
    if request.method == 'POST':
        admin_username = request.POST.get('admin_username', 'admin')
        admin_password = request.POST.get('admin_password', 'admin123')

        if not User.objects.filter(username=admin_username).exists():
            admin = User.objects.create_superuser(
                username=admin_username,
                password=admin_password,
                email='admin@example.com'
            )

        parent_username = request.POST.get('parent_username', 'parent1')
        parent_password = request.POST.get('parent_password', 'parent123')

        parent, created = User.objects.get_or_create(
            username=parent_username,
            defaults={'password': parent_password}
        )
        if created:
            parent.set_password(parent_password)
            parent.save()

        if not Child.objects.filter(parent=parent).exists():
            child = Child.objects.create(
                name='王小明',
                nickname='明明',
                gender='M',
                parent=parent
            )
            bind_code = child.generate_bind_code()

            for code, name in Task.TASK_TYPES:
                Task.objects.get_or_create(
                    code=code,
                    defaults={'name': name, 'power_reward': 10, 'icon': '⭐'}
                )

        teacher_username = request.POST.get('teacher_username', 'teacher1')
        teacher_password = request.POST.get('teacher_password', 'teacher123')

        teacher_user, created = User.objects.get_or_create(
            username=teacher_username,
            defaults={'password': teacher_password}
        )
        if created:
            teacher_user.set_password(teacher_password)
            teacher_user.save()

        if not hasattr(teacher_user, 'teacher_profile'):
            school, _ = School.objects.get_or_create(name='示范小学')
            Teacher.objects.create(
                user=teacher_user,
                school=school,
                class_name='三年级一班'
            )

        # 创建示例食材
        food_data = [
            ('米饭', 'grain', 'red', 2.5, 28.0, 0.3, 0.4, 116),
            ('面条', 'grain', 'red', 3.5, 25.0, 0.8, 0.9, 110),
            ('鸡胸肉', 'protein', 'yellow', 25.0, 0.5, 3.1, 0, 165),
            ('鱼肉', 'protein', 'yellow', 20.0, 0.5, 1.0, 0, 100),
            ('鸡蛋', 'protein', 'yellow', 13.0, 1.5, 11.0, 0.1, 156),
            ('青菜', 'vegetable', 'green', 2.0, 3.0, 0.2, 2.0, 14),
            ('菠菜', 'vegetable', 'green', 2.5, 3.0, 0.3, 2.2, 17),
            ('西红柿', 'vegetable', 'green', 1.0, 4.0, 0.2, 1.0, 19),
            ('苹果', 'fruit', 'blue', 0.5, 13.0, 0.3, 2.4, 52),
            ('香蕉', 'fruit', 'blue', 1.3, 22.0, 0.2, 2.6, 93),
            ('牛奶', 'dairy', 'purple', 3.2, 4.8, 3.3, 0, 61),
            ('酸奶', 'dairy', 'purple', 2.8, 6.5, 2.4, 0, 57),
        ]
        for name, category, color, protein, carb, fat, fiber, calories in food_data:
            FoodMaterial.objects.get_or_create(
                name=name,
                defaults={
                    'category': category,
                    'color': color,
                    'protein': protein,
                    'carbohydrate': carb,
                    'fat': fat,
                    'fiber': fiber,
                    'calories': calories
                }
            )

        # 创建徽章
        badges_data = [
            ('营养达人', 'nutrition_master', 'nutrition', '🏆', '连续7天膳食均衡', 7, 30),
            ('蔬菜战士', 'veggie_warrior', 'nutrition', '🥬', '每天吃蔬菜', 30, 50),
            ('运动健将', 'exercise_champion', 'exercise', '🏃', '完成10次运动打卡', 10, 40),
            ('早起标兵', 'early_bird', 'sleep', '🌅', '早睡打卡连续7天', 7, 30),
            ('卫生之星', 'hygiene_star', 'hygiene', '🧼', '正确洗手30次', 30, 40),
            ('挑战英雄', 'challenge_hero', 'challenge', '🎯', '完成5个挑战赛', 5, 60),
            ('坚持勋章', 'streak_medal', 'streak', '⭐', '连续打卡30天', 30, 100),
        ]
        for name, code, btype, icon, desc, req, power in badges_data:
            Badge.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'badge_type': btype,
                    'icon': icon,
                    'description': desc,
                    'requirement': req,
                    'power_reward': power
                }
            )

        # 创建示例食谱
        recipes_data = [
            ('番茄炒蛋', '家常美味，营养丰富', '番茄、鸡蛋、葱花', '1.番茄切块，鸡蛋打散\n2.热油炒蛋\n3.加入番茄翻炒', 120, 10, 8, 6, '6-12岁儿童', '维生素C、蛋白质'),
            ('青菜肉末粥', '易消化，养肠胃', '青菜、瘦肉、大米', '1.大米煮粥\n2.瘦肉切末\n3.青菜切碎\n4.加入粥中煮', 150, 8, 12, 5, '6-8岁儿童', '膳食纤维、蛋白质'),
            ('水果沙拉', '维生素丰富', '苹果、香蕉、酸奶', '1.水果切块\n2.淋上酸奶\n3.搅拌均匀', 100, 2, 3, 2, '6-12岁儿童', '维生素、膳食纤维'),
            ('燕麦牛奶粥', '早餐暖胃', '燕麦40g、牛奶200ml', '燕麦煮软后加牛奶搅匀', 220, 9, 32, 6, '儿童早餐', '钙、谷物、乳制品'),
            ('清蒸鲈鱼', '优质蛋白', '鲈鱼、姜丝、葱', '水开后蒸8-10分钟，少盐', 180, 28, 3, 6, '儿童', '鱼、蛋白质、DHA'),
            ('西兰花炒虾仁', '蔬菜+蛋白', '西兰花、虾仁、蒜末', '西兰花焯水后与虾仁少油翻炒', 160, 18, 12, 5, '儿童', '蔬菜、虾、蛋白质'),
            ('香蕉酸奶杯', '加餐', '香蕉、酸奶', '切块拌酸奶', 190, 6, 34, 4, '加餐', '水果、酸奶、钙'),
            ('番茄牛肉面', '汤面', '牛肉末、番茄、面条、青菜', '炒香牛肉加番茄煮汁下面', 380, 22, 48, 10, '运动日', '牛肉、面、蔬菜'),
        ]
        for name, desc, ingredients, steps, cal, prot, carb, fat, suitable, target in recipes_data:
            Recipe.objects.get_or_create(
                name=name,
                defaults={
                    'description': desc,
                    'ingredients': ingredients,
                    'steps': steps,
                    'calories': cal,
                    'protein': prot,
                    'carbohydrate': carb,
                    'fat': fat,
                    'suitable_for': suitable,
                    'target_nutrients': target
                }
            )

        return JsonResponse({'success': True, 'message': '演示数据已创建'})

    return render(request, 'admin_setup.html')
