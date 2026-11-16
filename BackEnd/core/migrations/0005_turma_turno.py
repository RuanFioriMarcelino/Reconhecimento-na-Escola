from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_alter_alerta_severidade_alter_alerta_status_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Turno",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=20, unique=True)),
                ("inicio", models.TimeField()),
                ("limite_entrada", models.TimeField()),
                ("ativo", models.BooleanField(default=True)),
            ],
            options={"db_table": "turno", "ordering": ["inicio", "nome"]},
        ),
        migrations.CreateModel(
            name="Turma",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=80, unique=True)),
                ("ano_letivo", models.PositiveIntegerField()),
                ("ativo", models.BooleanField(default=True)),
                (
                    "turno",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="turmas",
                        to="core.turno",
                    ),
                ),
            ],
            options={"db_table": "turma", "ordering": ["ano_letivo", "nome"]},
        ),
        migrations.AddField(
            model_name="aluno",
            name="turma_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="alunos",
                to="core.turma",
            ),
        ),
        migrations.AddField(
            model_name="aluno",
            name="turno_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="alunos",
                to="core.turno",
            ),
        ),
    ]
