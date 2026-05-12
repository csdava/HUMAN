from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_add_user_to_child"),
    ]

    operations = [
        migrations.AddField(
            model_name="child",
            name="diet_notes",
            field=models.TextField(
                blank=True,
                help_text="家长填写：忌口、过敏、医嘱摘要等，可选同步到儿童端展示",
                verbose_name="膳食备注",
            ),
        ),
    ]
