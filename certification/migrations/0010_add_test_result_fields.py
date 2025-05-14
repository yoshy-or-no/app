from django.db import migrations, models
import django.utils.timezone

class Migration(migrations.Migration):

    dependencies = [
        ('certification', '0009_test_passing_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='testresult',
            name='started_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ] 