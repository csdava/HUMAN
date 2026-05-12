from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Count, Q, Sum
from datetime import timedelta
from .models import (
    Child, Task, TaskRecord, Encouragement, Teacher, ClassStudent, Activity,
    FoodMaterial, MealRecord, MealFoodItem, Badge, ChildBadge, Recipe,
    HealthAlert, HealthChallenge, ChallengeProgress, School
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
            'active_challenges': []
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

    encouragements = Encouragement.objects.filter(
        child=child, is_read=False
    ).order_by('-created_at')[:5]

    latest_encouragement = encouragements.first()

    progress_percent = int((child.power / child.power_to_next) * 100)

    today_meals = MealRecord.objects.filter(child=child, date=today)
    badges = ChildBadge.objects.filter(child=child).select_related('badge')[:5]

    active_challenges = []
    for progress in ChallengeProgress.objects.filter(child=child, is_completed=False).select_related('challenge'):
        if progress.challenge.status == 'active':
            progress.percent = int(progress.current_value / progress.challenge.target_value * 100)
            active_challenges.append(progress)

    return render(request, 'child/dashboard.html', {
        'child': child,
        'daily_records': daily_records,
        'encouragements': encouragements,
        'latest_encouragement': latest_encouragement,
        'progress_percent': progress_percent,
        'today_meals': today_meals,
        'badges': badges,
        'active_challenges': active_challenges,
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
    encouragement = get_object_or_404(
        Encouragement, id=encouragement_id, child__parent=request.user
    )
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

        for code, name in Task.TASK_TYPES:
            task = Task.objects.get_or_create(
                code=code,
                defaults={'name': name, 'power_reward': 10, 'icon': '⭐'}
            )[0]

        return redirect('child_dashboard')

    return render(request, 'child/register.html')


# ========== YOLO 膳食识别 API ==========

# YOLO 类别到食材类别的映射
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
    from django.conf import settings

    # 创建临时文件保存上传的图片
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
        for chunk in image.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        # 调用 YOLO 模型进行识别
        from ultralytics import YOLO

        # 使用训练好的模型
        model_path = 'D:/User/Documents/PycharmProjects/human/runs/vegetable_train_v2/weights/last.pt'

        if os.path.exists(model_path):
            model = YOLO(model_path)
            # 运行推理
            results = model.predict(source=tmp_path, imgsz=640, conf=0.5, verbose=False)

            # 解析识别结果
            recognized_foods = []
            if results and len(results) > 0:
                result = results[0]
                if result.boxes is not None and len(result.boxes) > 0:
                    boxes = result.boxes
                    class_ids = boxes.cls.cpu().numpy().astype(int)
                    confidences = boxes.conf.cpu().numpy()

                    for class_id, conf in zip(class_ids, confidences):
                        if class_id < len(result.names):
                            class_name = result.names[class_id]
                            if class_name in YOLO_CLASS_TO_FOOD:
                                food_data = YOLO_CLASS_TO_FOOD[class_name]
                                recognized_foods.append({
                                    'name': food_data['name'],
                                    'category': food_data['category'],
                                    'color': food_data['color'],
                                    'confidence': float(conf),
                                    'protein': food_data['protein'],
                                    'carbohydrate': food_data['carbohydrate'],
                                    'fat': food_data['fat'],
                                    'calories': food_data['calories'],
                                })
                            elif class_name not in recognized_foods:
                                # 使用默认数据
                                food_data = DEFAULT_FOOD_DATA.get('vegetable', DEFAULT_FOOD_DATA['vegetable'])
                                recognized_foods.append({
                                    'name': class_name.title(),
                                    'category': food_data['category'],
                                    'color': food_data['color'],
                                    'confidence': float(conf),
                                    **food_data
                                })

            # 去重（同一食材只保留一个）
            unique_foods = {}
            for food in recognized_foods:
                key = food['category']
                if key not in unique_foods or food['confidence'] > unique_foods[key]['confidence']:
                    unique_foods[key] = food

            recognized_foods = list(unique_foods.values())
        else:
            # 模型文件不存在，使用模拟数据
            recognized_foods = [
                DEFAULT_FOOD_DATA['grain'],
                DEFAULT_FOOD_DATA['vegetable'],
                DEFAULT_FOOD_DATA['protein'],
            ]

    except Exception as e:
        print(f"YOLO识别错误: {e}")
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

    return render(request, 'parent/dashboard.html', {
        'child': child,
        'child_age_years': child.age_years(),
        'children': children,
        'pending_tasks': pending_tasks,
        'week_completed': week_completed,
        'today_completed': today_completed,
        'recent_records': recent_records,
        'encouragements': encouragements,
        'progress_percent': progress_percent,
        'today_meals': today_meals,
        'today_meal_totals': today_meal_totals,
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

    recipes = Recipe.objects.select_related('created_by').all()

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
def parent_meal_report(request):
    """多维膳食报告"""
    child, _children = _parent_resolve_child(request)
    if not child:
        return JsonResponse({'success': False, 'message': '未找到孩子信息'})

    days = max(1, min(90, int(request.GET.get('days', 7))))
    today = timezone.now().date()
    start_date = today - timedelta(days=days - 1)

    meals = MealRecord.objects.filter(
        child=child, date__gte=start_date
    )

    total_calories = meals.aggregate(Sum('total_calories'))['total_calories__sum'] or 0
    total_protein = meals.aggregate(Sum('total_protein'))['total_protein__sum'] or 0
    total_carbohydrate = meals.aggregate(Sum('total_carbohydrate'))['total_carbohydrate__sum'] or 0
    total_fat = meals.aggregate(Sum('total_fat'))['total_fat__sum'] or 0

    daily_scores = []
    for day_offset in range(days):
        day = start_date + timedelta(days=day_offset)
        day_meals = meals.filter(date=day)
        avg_score = sum(m.total_score for m in day_meals) / max(day_meals.count(), 1)
        daily_scores.append({
            'date': day.isoformat(),
            'score': round(avg_score, 1),
            'meal_count': day_meals.count()
        })

    return JsonResponse({
        'success': True,
        'report': {
            'period': f'近{days}天',
            'total_calories': round(total_calories, 1),
            'total_protein': round(total_protein, 1),
            'total_carbohydrate': round(total_carbohydrate, 1),
            'total_fat': round(total_fat, 1),
            'avg_daily_score': round(sum(d['score'] for d in daily_scores) / max(len(daily_scores), 1), 1),
            'daily_scores': daily_scores
        }
    })


@login_required
def parent_export_weekly_pdf(request):
    """导出膳食与任务周报 PDF（默认近 7 天，含今天）。"""
    from urllib.parse import quote

    from .pdf_weekly import build_parent_weekly_pdf

    child, _children = _parent_resolve_child(request)
    if not child:
        return HttpResponse('未找到孩子信息', status=400, content_type='text/plain; charset=utf-8')

    days = max(1, min(30, int(request.GET.get('days', 7))))
    today = timezone.now().date()
    start = today - timedelta(days=days - 1)

    meals = MealRecord.objects.filter(child=child, date__gte=start, date__lte=today)
    total_calories = float(meals.aggregate(Sum('total_calories'))['total_calories__sum'] or 0)
    total_protein = float(meals.aggregate(Sum('total_protein'))['total_protein__sum'] or 0)
    total_carb = float(meals.aggregate(Sum('total_carbohydrate'))['total_carbohydrate__sum'] or 0)
    total_fat = float(meals.aggregate(Sum('total_fat'))['total_fat__sum'] or 0)

    daily_rows = []
    score_sum = 0.0
    for offset in range(days):
        day = start + timedelta(days=offset)
        day_meals = list(meals.filter(date=day))
        cnt = len(day_meals)
        avg_score = sum(m.total_score for m in day_meals) / max(cnt, 1)
        score_sum += avg_score
        day_cals = sum(float(m.total_calories or 0) for m in day_meals)
        daily_rows.append({
            'date': day.strftime('%Y-%m-%d'),
            'meal_count': cnt,
            'day_calories': day_cals,
            'avg_score': avg_score,
        })

    avg_daily_score = score_sum / max(days, 1)
    task_completed = TaskRecord.objects.filter(
        child=child, date__gte=start, date__lte=today, status='completed'
    ).count()

    from .nutrition import recommend_intake_for_age
    age = child.age_years()
    rec = recommend_intake_for_age(age)

    gen_at = timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')
    ctx = {
        'title': f'儿童膳食周报（近{days}天）',
        'child_label': f'孩子：{child.nickname}（{child.get_gender_display()}）',
        'age_years': age,
        'period_label': f'统计区间：{start.isoformat()} ～ {today.isoformat()}',
        'daily_rows': daily_rows,
        'totals': {
            'kcal': total_calories,
            'protein': total_protein,
            'carb': total_carb,
            'fat': total_fat,
        },
        'avg_daily_score': avg_daily_score,
        'task_completed_count': task_completed,
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
        'footer': f'由健康管理家庭端生成 · {gen_at}',
    }

    pdf_bytes = build_parent_weekly_pdf(ctx)
    ascii_name = f'weekly_report_{child.id}_{start}_{today}.pdf'
    display_name = f'膳食周报_{child.nickname}_{start}_{today}.pdf'
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


# ========== 学校端视图 ==========

@login_required
@user_passes_test(is_teacher)
def school_dashboard(request):
    """学校端首页"""
    teacher = request.user.teacher_profile
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

        students_data.append({
            'id': child.id,
            'nickname': child.nickname,
            'level': child.level,
            'week_tasks': week_records.count(),
            'avg_tasks': round(avg_tasks, 1),
            'daily_tasks': student_tasks,
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

    activities = Activity.objects.filter(is_active=True)[:5]
    challenges = HealthChallenge.objects.filter(teacher=teacher, status='active')[:5]

    return render(request, 'school/dashboard.html', {
        'teacher': teacher,
        'students_data': students_data,
        'all_pending': all_pending,
        'activities': activities,
        'challenges': challenges,
        'total_tasks': total_tasks,
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
        power_reward=power_reward
    )

    return JsonResponse({'success': True, 'message': '挑战赛已发布'})


@login_required
@user_passes_test(is_teacher)
def school_class_stats(request):
    """班级统计数据"""
    teacher = request.user.teacher_profile
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
        'overall_rate': round(overall_rate, 1)
    })


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
