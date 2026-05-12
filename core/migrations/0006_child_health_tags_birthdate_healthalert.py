from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_child_diet_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="child",
            name="birth_date",
            field=models.DateField(blank=True, null=True, verbose_name="出生日期"),
        ),
        migrations.AddField(
            model_name="child",
            name="allergy_tags",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="家长维护：如“花生”“牛奶”“鸡蛋”等；用于识别与预警",
                verbose_name="过敏标签",
            ),
        ),
        migrations.AddField(
            model_name="child",
            name="medical_tags",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="家长维护：如“低盐”“少油”“控糖”等；用于提醒与推荐",
                verbose_name="医嘱标签",
            ),
        ),
        migrations.CreateModel(
            name="HealthAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("alert_type", models.CharField(choices=[("allergy", "过敏预警"), ("medical", "医嘱提醒")], max_length=20, verbose_name="预警类型")),
                ("title", models.CharField(max_length=100, verbose_name="标题")),
                ("message", models.TextField(verbose_name="内容")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="结构化数据")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("is_read_by_child", models.BooleanField(default=False, verbose_name="儿童端已读")),
                ("is_read_by_parent", models.BooleanField(default=False, verbose_name="家长端已读")),
                ("is_read_by_teacher", models.BooleanField(default=False, verbose_name="学校端已读")),
                (
                    "child",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="health_alerts",
                        to="core.child",
                        verbose_name="孩子",
                    ),
                ),
            ],
            options={
                "verbose_name": "健康预警",
                "verbose_name_plural": "健康预警",
                "ordering": ["-created_at"],
            },
        ),
    ]

