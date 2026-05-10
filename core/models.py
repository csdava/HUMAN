from django.db import models
from django.contrib.auth.models import User


class Child(models.Model):
    """孩子模型"""
    GENDER_CHOICES = [
        ('M', '男孩'),
        ('F', '女孩'),
    ]

    name = models.CharField(max_length=50, verbose_name='姓名')
    nickname = models.CharField(max_length=50, verbose_name='昵称')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, verbose_name='性别')
    avatar = models.CharField(max_length=20, default='default', verbose_name='头像')
    level = models.IntegerField(default=1, verbose_name='勇士等级')
    power = models.IntegerField(default=0, verbose_name='当前体力值')
    power_to_next = models.IntegerField(default=40, verbose_name='升级所需体力')
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='child_profile', verbose_name='关联用户')
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='children', null=True, blank=True, verbose_name='关联家长')
    bind_code = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name='绑定码')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    # 五色宝石状态
    gem_red = models.BooleanField(default=False, verbose_name='红色谷物宝石')
    gem_yellow = models.BooleanField(default=False, verbose_name='黄色蛋白质宝石')
    gem_green = models.BooleanField(default=False, verbose_name='绿色蔬菜宝石')
    gem_blue = models.BooleanField(default=False, verbose_name='蓝色水果宝石')
    gem_purple = models.BooleanField(default=False, verbose_name='紫色乳制品宝石')

    class Meta:
        verbose_name = '孩子'
        verbose_name_plural = '孩子们'

    def __str__(self):
        return self.nickname

    def generate_bind_code(self):
        """生成唯一绑定码"""
        import random
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not Child.objects.filter(bind_code=code).exists():
                self.bind_code = code
                self.save()
                return code

    def add_power(self, amount):
        """增加体力值，处理升级逻辑"""
        self.power += amount
        upgraded = False
        while self.power >= self.power_to_next:
            self.power -= self.power_to_next
            self.level += 1
            self.power_to_next = self.level * 40
            upgraded = True
        self.save()
        return upgraded

    def reset_daily_gems(self):
        """重置每日宝石状态"""
        self.gem_red = False
        self.gem_yellow = False
        self.gem_green = False
        self.gem_blue = False
        self.gem_purple = False
        self.save()

    def check_gem_color(self, food_category):
        """根据食物类别点亮宝石"""
        if food_category == 'grain':
            self.gem_red = True
        elif food_category == 'protein':
            self.gem_yellow = True
        elif food_category == 'vegetable':
            self.gem_green = True
        elif food_category == 'fruit':
            self.gem_blue = True
        elif food_category == 'dairy':
            self.gem_purple = True
        self.save()

    def is_five_color_complete(self):
        """检查五色是否全部点亮"""
        return all([self.gem_red, self.gem_yellow, self.gem_green, self.gem_blue, self.gem_purple])


class FoodMaterial(models.Model):
    """食材库"""
    CATEGORY_CHOICES = [
        ('grain', '谷物类'),
        ('protein', '蛋白质类'),
        ('vegetable', '蔬菜类'),
        ('fruit', '水果类'),
        ('dairy', '乳制品类'),
        ('other', '其他'),
    ]

    COLOR_CHOICES = [
        ('red', '红-谷物'),
        ('yellow', '黄-蛋白质'),
        ('green', '绿-蔬菜'),
        ('blue', '蓝-水果'),
        ('purple', '紫-乳制品'),
    ]

    name = models.CharField(max_length=50, unique=True, verbose_name='食材名称')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='食材类别')
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, verbose_name='五色分类')
    protein = models.FloatField(default=0, verbose_name='蛋白质(g/100g)')
    carbohydrate = models.FloatField(default=0, verbose_name='碳水化合物(g/100g)')
    fat = models.FloatField(default=0, verbose_name='脂肪(g/100g)')
    fiber = models.FloatField(default=0, verbose_name='膳食纤维(g/100g)')
    calories = models.FloatField(default=0, verbose_name='热量(kcal/100g)')
    image_url = models.CharField(max_length=200, blank=True, verbose_name='食材图片')
    yolo_class = models.CharField(max_length=50, blank=True, verbose_name='YOLO识别类别')

    class Meta:
        verbose_name = '食材'
        verbose_name_plural = '食材库'
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class MealRecord(models.Model):
    """膳食记录"""
    MEAL_TYPE_CHOICES = [
        ('breakfast', '早餐'),
        ('lunch', '午餐'),
        ('dinner', '晚餐'),
        ('snack', '零食/加餐'),
    ]

    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='meal_records', verbose_name='孩子')
    date = models.DateField(verbose_name='日期')
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE_CHOICES, verbose_name='餐次')
    image_key = models.CharField(max_length=200, blank=True, verbose_name='图片存储KEY')
    total_score = models.IntegerField(default=0, verbose_name='五色评分')
    total_calories = models.FloatField(default=0, verbose_name='总热量')
    total_protein = models.FloatField(default=0, verbose_name='总蛋白质')
    total_carbohydrate = models.FloatField(default=0, verbose_name='总碳水')
    total_fat = models.FloatField(default=0, verbose_name='总脂肪')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='记录时间')
    is_verified = models.BooleanField(default=False, verbose_name='是否人工确认')

    class Meta:
        verbose_name = '膳食记录'
        verbose_name_plural = '膳食记录'
        unique_together = ['child', 'date', 'meal_type']
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.child.nickname} - {self.get_meal_type_display()} - {self.date}"


class MealFoodItem(models.Model):
    """膳食记录中的食材明细"""
    meal_record = models.ForeignKey(MealRecord, on_delete=models.CASCADE, related_name='food_items', verbose_name='膳食记录')
    food = models.ForeignKey(FoodMaterial, on_delete=models.CASCADE, verbose_name='食材')
    weight = models.FloatField(default=100, verbose_name='预估重量(g)')

    class Meta:
        verbose_name = '膳食食材'
        verbose_name_plural = '膳食食材明细'

    def __str__(self):
        return f"{self.food.name} ({self.weight}g)"


class Task(models.Model):
    """任务模板"""
    TASK_TYPES = [
        ('veggie', '吃够5种蔬菜'),
        ('exercise', '户外运动30分钟'),
        ('sleep', '早睡打卡'),
        ('wash', '洗手20秒'),
    ]

    name = models.CharField(max_length=100, verbose_name='任务名称')
    code = models.CharField(max_length=20, unique=True, verbose_name='任务代码')
    power_reward = models.IntegerField(default=10, verbose_name='奖励体力')
    icon = models.CharField(max_length=10, default='⭐', verbose_name='图标')
    description = models.CharField(max_length=200, blank=True, verbose_name='描述')

    class Meta:
        verbose_name = '任务'
        verbose_name_plural = '任务'

    def __str__(self):
        return self.name


class TaskRecord(models.Model):
    """任务记录"""
    STATUS_CHOICES = [
        ('pending', '待确认'),
        ('completed', '已完成'),
        ('confirmed', '已确认'),
    ]

    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='task_records', verbose_name='孩子')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, verbose_name='任务')
    date = models.DateField(verbose_name='日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')

    class Meta:
        verbose_name = '任务记录'
        verbose_name_plural = '任务记录'
        unique_together = ['child', 'task', 'date']
        ordering = ['-date', '-submitted_at']

    def __str__(self):
        return f"{self.child.nickname} - {self.task.name} - {self.date}"


class Badge(models.Model):
    """成就徽章模板"""
    BADGE_TYPES = [
        ('nutrition', '营养达人'),
        ('exercise', '运动健将'),
        ('sleep', '作息标兵'),
        ('hygiene', '卫生之星'),
        ('challenge', '挑战英雄'),
        ('streak', '坚持勋章'),
    ]

    name = models.CharField(max_length=50, unique=True, verbose_name='徽章名称')
    code = models.CharField(max_length=30, unique=True, verbose_name='徽章代码')
    badge_type = models.CharField(max_length=20, choices=BADGE_TYPES, default='nutrition', verbose_name='徽章类型')
    icon = models.CharField(max_length=50, default='🏅', verbose_name='徽章图标')
    description = models.CharField(max_length=200, blank=True, verbose_name='徽章描述')
    requirement = models.IntegerField(default=1, verbose_name='解锁条件(数值)')
    power_reward = models.IntegerField(default=20, verbose_name='体力奖励')

    class Meta:
        verbose_name = '成就徽章'
        verbose_name_plural = '成就徽章'

    def __str__(self):
        return self.name


class ChildBadge(models.Model):
    """孩子已获得徽章"""
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='badges', verbose_name='孩子')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, verbose_name='徽章')
    earned_at = models.DateTimeField(auto_now_add=True, verbose_name='获得时间')

    class Meta:
        verbose_name = '孩子徽章'
        verbose_name_plural = '孩子徽章'
        unique_together = ['child', 'badge']

    def __str__(self):
        return f"{self.child.nickname} - {self.badge.name}"


class Encouragement(models.Model):
    """鼓励语"""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='encouragements', verbose_name='发送者')
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='encouragements', verbose_name='孩子')
    message = models.TextField(verbose_name='鼓励内容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='发送时间')
    is_read = models.BooleanField(default=False, verbose_name='已读')

    class Meta:
        verbose_name = '鼓励语'
        verbose_name_plural = '鼓励语'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender.username} -> {self.child.nickname}: {self.message[:20]}"


class Recipe(models.Model):
    """食谱推荐"""
    name = models.CharField(max_length=100, verbose_name='食谱名称')
    description = models.TextField(blank=True, verbose_name='食谱描述')
    ingredients = models.TextField(verbose_name='食材清单')
    steps = models.TextField(blank=True, verbose_name='烹饪步骤')
    calories = models.FloatField(default=0, verbose_name='热量(kcal)')
    protein = models.FloatField(default=0, verbose_name='蛋白质(g)')
    carbohydrate = models.FloatField(default=0, verbose_name='碳水化合物(g)')
    fat = models.FloatField(default=0, verbose_name='脂肪(g)')
    suitable_for = models.CharField(max_length=50, blank=True, verbose_name='适宜人群')
    target_nutrients = models.CharField(max_length=100, blank=True, verbose_name='补充营养')
    image_url = models.CharField(max_length=200, blank=True, verbose_name='食谱图片')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '食谱'
        verbose_name_plural = '食谱推荐'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class School(models.Model):
    """学校"""
    name = models.CharField(max_length=100, verbose_name='学校名称')

    class Meta:
        verbose_name = '学校'
        verbose_name_plural = '学校'

    def __str__(self):
        return self.name


class Teacher(models.Model):
    """老师"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile', verbose_name='用户')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='teachers', verbose_name='学校')
    class_name = models.CharField(max_length=50, verbose_name='班级名称')

    class Meta:
        verbose_name = '老师'
        verbose_name_plural = '老师们'

    def __str__(self):
        return f"{self.user.username} ({self.class_name})"


class ClassStudent(models.Model):
    """班级学生关联"""
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='students', verbose_name='老师')
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='class_enrollments', verbose_name='孩子')
    enrolled_at = models.DateTimeField(auto_now_add=True, verbose_name='加入时间')

    class Meta:
        verbose_name = '班级学生'
        verbose_name_plural = '班级学生'
        unique_together = ['teacher', 'child']

    def __str__(self):
        return f"{self.child.nickname} in {self.teacher.class_name}"


class Activity(models.Model):
    """班级健康活动"""
    ACTIVITY_TYPES = [
        ('challenge', '健康挑战'),
        ('competition', '班级比赛'),
        ('education', '健康教育'),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='activities', verbose_name='发布老师')
    title = models.CharField(max_length=200, verbose_name='活动标题')
    content = models.TextField(verbose_name='活动内容')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES, default='challenge', verbose_name='活动类型')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '活动'
        verbose_name_plural = '活动'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class HealthChallenge(models.Model):
    """健康挑战赛"""
    STATUS_CHOICES = [
        ('active', '进行中'),
        ('completed', '已结束'),
        ('cancelled', '已取消'),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='challenges', verbose_name='发布老师')
    title = models.CharField(max_length=200, verbose_name='挑战标题')
    description = models.TextField(verbose_name='挑战说明')
    challenge_type = models.CharField(max_length=30, verbose_name='挑战类型')
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    target_value = models.IntegerField(default=7, verbose_name='目标值')
    power_reward = models.IntegerField(default=50, verbose_name='完成奖励体力')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='状态')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '健康挑战'
        verbose_name_plural = '健康挑战赛'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ChallengeProgress(models.Model):
    """挑战进度"""
    challenge = models.ForeignKey(HealthChallenge, on_delete=models.CASCADE, related_name='progress', verbose_name='挑战')
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='challenge_progress', verbose_name='孩子')
    current_value = models.IntegerField(default=0, verbose_name='当前进度')
    is_completed = models.BooleanField(default=False, verbose_name='是否完成')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')

    class Meta:
        verbose_name = '挑战进度'
        verbose_name_plural = '挑战进度'
        unique_together = ['challenge', 'child']

    def __str__(self):
        return f"{self.child.nickname} - {self.challenge.title}"
