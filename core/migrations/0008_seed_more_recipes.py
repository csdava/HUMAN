from django.db import migrations


def seed_recipes(apps, schema_editor):
    Recipe = apps.get_model("core", "Recipe")
    rows = [
        {
            "name": "燕麦牛奶粥",
            "description": "早餐暖胃，补充钙质与膳食纤维",
            "ingredients": "燕麦40g、牛奶200ml、少量蜂蜜（可选）",
            "steps": "1.燕麦加水小火煮软\n2.倒入牛奶搅匀稍煮\n3.按口味少加蜂蜜",
            "calories": 220,
            "protein": 9,
            "carbohydrate": 32,
            "fat": 6,
            "suitable_for": "儿童早餐",
            "target_nutrients": "钙、谷物、乳制品",
        },
        {
            "name": "清蒸鲈鱼",
            "description": "优质蛋白，少油清淡",
            "ingredients": "鲈鱼一条、姜丝、葱、少量蒸鱼豉油",
            "steps": "1.鱼洗净划刀铺姜丝\n2.水开后蒸8–10分钟\n3.淋少量豉油撒葱花",
            "calories": 180,
            "protein": 28,
            "carbohydrate": 3,
            "fat": 6,
            "suitable_for": "儿童午餐/晚餐",
            "target_nutrients": "蛋白质、鱼、DHA",
        },
        {
            "name": "西兰花炒虾仁",
            "description": "蔬菜+优质蛋白，色彩吸引孩子",
            "ingredients": "西兰花200g、虾仁100g、蒜末、橄榄油少许",
            "steps": "1.西兰花焯水沥干\n2.少油爆香蒜末炒虾仁\n3.下西兰花翻炒调味",
            "calories": 160,
            "protein": 18,
            "carbohydrate": 12,
            "fat": 5,
            "suitable_for": "儿童午晚餐",
            "target_nutrients": "蔬菜、虾、蛋白质",
        },
        {
            "name": "黄瓜拌豆腐",
            "description": "清爽少油，植物蛋白",
            "ingredients": "嫩豆腐一块、黄瓜半根、少量生抽与香油",
            "steps": "1.豆腐切块黄瓜切丁\n2.拌匀调味即可",
            "calories": 140,
            "protein": 12,
            "carbohydrate": 8,
            "fat": 7,
            "suitable_for": "夏季加餐",
            "target_nutrients": "蔬菜、豆、蛋白质",
        },
        {
            "name": "香蕉酸奶杯",
            "description": "水果+乳制品，快手加餐",
            "ingredients": "香蕉1根、无糖酸奶150g、燕麦脆少许",
            "steps": "1.香蕉切片铺杯底\n2.倒酸奶\n3.撒少量燕麦脆",
            "calories": 190,
            "protein": 6,
            "carbohydrate": 34,
            "fat": 4,
            "suitable_for": "加餐",
            "target_nutrients": "水果、酸奶、钙",
        },
        {
            "name": "紫薯杂粮饭",
            "description": "粗细搭配，补充膳食纤维",
            "ingredients": "大米、小米、紫薯小块适量",
            "steps": "1.杂粮与大米淘洗\n2.与紫薯一起电饭煲煮熟",
            "calories": 200,
            "protein": 5,
            "carbohydrate": 42,
            "fat": 2,
            "suitable_for": "主食替换",
            "target_nutrients": "谷物、薯、杂粮",
        },
        {
            "name": "番茄牛肉面",
            "description": "补铁补蛋白，汤面暖胃",
            "ingredients": "瘦牛肉末80g、番茄1个、面条适量、青菜少许",
            "steps": "1.炒香牛肉末\n2.下番茄炒出汁加水煮开\n3.下面条与青菜煮熟",
            "calories": 380,
            "protein": 22,
            "carbohydrate": 48,
            "fat": 10,
            "suitable_for": "运动日午餐",
            "target_nutrients": "蛋白质、牛肉、面、蔬菜",
        },
        {
            "name": "蘑菇蒸蛋羹",
            "description": "嫩滑易吞咽，优质蛋白",
            "ingredients": "鸡蛋2个、温水适量、鲜蘑菇少许",
            "steps": "1.鸡蛋打散加温水搅匀过筛\n2.加入蘑菇丁\n3.中火蒸10分钟焖2分钟",
            "calories": 130,
            "protein": 11,
            "carbohydrate": 4,
            "fat": 8,
            "suitable_for": "早餐/病后恢复",
            "target_nutrients": "蛋、蛋白质、蔬菜",
        },
        {
            "name": "玉米胡萝卜排骨汤",
            "description": "汤水补水，玉米提供碳水",
            "ingredients": "排骨300g、玉米1根、胡萝卜半根、姜两片",
            "steps": "1.排骨焯水\n2.与玉米胡萝卜姜片炖煮40分钟\n3.撇油少盐",
            "calories": 260,
            "protein": 18,
            "carbohydrate": 18,
            "fat": 12,
            "suitable_for": "家庭晚餐",
            "target_nutrients": "蛋白质、蔬菜、谷物",
        },
        {
            "name": "凉拌菠菜木耳",
            "description": "高铁蔬菜，少油凉拌",
            "ingredients": "菠菜200g、木耳泡发、蒜末、少量香醋与香油",
            "steps": "1.菠菜焯水挤干切段\n2.木耳焯水\n3.拌匀调味",
            "calories": 90,
            "protein": 4,
            "carbohydrate": 10,
            "fat": 4,
            "suitable_for": "蔬菜补充",
            "target_nutrients": "蔬菜、纤维、维生素",
        },
        {
            "name": "三文鱼蔬菜丁",
            "description": "富含优质脂肪与蛋白",
            "ingredients": "三文鱼80g、豌豆玉米胡萝卜丁适量、橄榄油少许",
            "steps": "1.三文鱼切丁少油煎熟\n2.下蔬菜丁翻炒\n3.少盐调味",
            "calories": 220,
            "protein": 20,
            "carbohydrate": 15,
            "fat": 10,
            "suitable_for": "晚餐",
            "target_nutrients": "鱼、蛋白质、蔬菜",
        },
        {
            "name": "全麦蔬菜三明治",
            "description": "外带便当，全谷物+蔬菜",
            "ingredients": "全麦面包2片、生菜番茄黄瓜、鸡蛋1个",
            "steps": "1.鸡蛋煎熟\n2.蔬菜洗净切片\n3.夹入面包即可",
            "calories": 280,
            "protein": 14,
            "carbohydrate": 32,
            "fat": 10,
            "suitable_for": "便当",
            "target_nutrients": "谷物、蔬菜、蛋",
        },
    ]
    for r in rows:
        Recipe.objects.get_or_create(
            name=r["name"],
            defaults={
                "description": r["description"],
                "ingredients": r["ingredients"],
                "steps": r["steps"],
                "calories": r["calories"],
                "protein": r["protein"],
                "carbohydrate": r["carbohydrate"],
                "fat": r["fat"],
                "suitable_for": r["suitable_for"],
                "target_nutrients": r["target_nutrients"],
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_recipe_created_by"),
    ]

    operations = [
        migrations.RunPython(seed_recipes, noop_reverse),
    ]
