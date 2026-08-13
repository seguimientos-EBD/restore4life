import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='StudyArea',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='name')),
            ],
            options={
                'verbose_name': 'Study area',
                'verbose_name_plural': 'Study areas',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Wetland',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('fid', models.IntegerField(blank=True, null=True, verbose_name='FID')),
                ('v_idris', models.BigIntegerField(blank=True, null=True, verbose_name='Idris ID')),
                ('ramsar_id', models.IntegerField(blank=True, null=True, verbose_name='Ramsar ID')),
                ('iso3', models.CharField(blank=True, max_length=3, verbose_name='ISO3')),
                ('country', models.CharField(blank=True, max_length=255, verbose_name='country')),
                ('official_area', models.FloatField(blank=True, null=True, verbose_name='official area (ha)')),
                ('geom', django.contrib.gis.db.models.fields.GeometryField(srid=4326, verbose_name='geometry')),
                ('study_area', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='wetlands',
                    to='areas.studyarea',
                )),
            ],
            options={
                'verbose_name': 'Wetland',
                'verbose_name_plural': 'Wetlands',
                'ordering': ('name',),
            },
        ),
    ]
