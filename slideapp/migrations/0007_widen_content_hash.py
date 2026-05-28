from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('slideapp', '0006_add_html_cache_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slide',
            name='content_hash',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
