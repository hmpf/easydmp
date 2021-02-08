# Generated by Django 2.2.17 on 2020-11-24 12:48

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import easydmp.dmpt.models
import easydmp.dmpt.utils


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0008_alter_user_username_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('abbreviation', models.CharField(blank=True, max_length=8)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('published', models.DateTimeField(blank=True, help_text='Date when the template is publically available, and set read-only.', null=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('description', models.TextField(blank=True)),
                ('domain_specific', models.BooleanField(default=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('more_info', models.URLField(blank=True)),
                ('retired', models.DateTimeField(blank=True, help_text='Date after which the template should no longer be used.', null=True)),
                ('cloned_from', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clones', to='dmpt.Template')),
                ('cloned_when', models.DateTimeField(blank=True, null=True)),
                ('reveal_questions', models.BooleanField(default=False, help_text='Should the questions be shown in the generated text?')),
            ],
            options={
                'permissions': (('use_template', 'Can use template'),),
                'unique_together': {('version', 'title')},
            },
        ),
        migrations.CreateModel(
            name='TemplateUserObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permissions_user', to='dmpt.Template')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
                'unique_together': {('user', 'permission', 'content_object')},
            },
        ),
        migrations.CreateModel(
            name='TemplateGroupObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permissions_group', to='dmpt.Template')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
            ],
            options={
                'abstract': False,
                'unique_together': {('group', 'permission', 'content_object')},
            },
        ),
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, help_text='May be empty for **one** section per template', max_length=255)),
                ('introductory_text', models.TextField(blank=True)),
                ('position', models.PositiveIntegerField(default=1, help_text='A specific position may only occur once per template')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='dmpt.Template')),
                ('comment', models.TextField(blank=True)),
                ('label', models.CharField(blank=True, max_length=16)),
                ('section_depth', models.PositiveSmallIntegerField(default=1)),
                ('super_section', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='subsections', to='dmpt.Section')),
                ('branching', models.BooleanField(default=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('cloned_from', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clones', to='dmpt.Section')),
                ('cloned_when', models.DateTimeField(blank=True, null=True)),
                ('optional', models.BooleanField(default=False, help_text='True if this section is optional. The template designer needs to provide a wording to an automatically generated yes/no question at the start of the section.')),
            ],
            options={
                'unique_together': {('template', 'super_section', 'position'), ('template', 'title')},
            },
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('input_type', models.CharField(choices=[('bool', 'bool'), ('choice', 'choice'), ('daterange', 'daterange'), ('multichoiceonetext', 'multichoiceonetext'), ('reason', 'reason'), ('shortfreetext', 'shortfreetext'), ('positiveinteger', 'positiveinteger'), ('date', 'date'), ('externalchoice', 'externalchoice'), ('extchoicenotlisted', 'extchoicenotlisted'), ('externalmultichoiceonetext', 'externalmultichoiceonetext'), ('extmultichoicenotlistedonetext', 'extmultichoicenotlistedonetext'), ('namedurl', 'namedurl'), ('multinamedurlonetext', 'multinamedurlonetext'), ('multidmptypedreasononetext', 'multidmptypedreasononetext'), ('multirdacostonetext', 'multirdacostonetext'), ('storageforecast', 'storageforecast')], max_length=32)),
                ('position', models.PositiveIntegerField(default=1, help_text='Position in section. Must be unique.')),
                ('question', models.CharField(max_length=255)),
                ('label', models.CharField(blank=True, max_length=16)),
                ('help_text', models.TextField(blank=True)),
                ('framing_text', models.TextField(blank=True)),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='dmpt.Section')),
                ('comment', models.TextField(blank=True, null=True)),
                ('on_trunk', models.BooleanField(default=True)),
                ('optional', models.BooleanField(default=False)),
                ('optional_canned_text', models.TextField(blank=True)),
                ('cloned_from', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clones', to='dmpt.Question')),
                ('cloned_when', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ('section', 'position'),
                'unique_together': {('section', 'position')},
            },
        ),
        migrations.AddIndex(
            model_name='question',
            index=models.Index(fields=['input_type', 'id'], name='dmpt_questi_input_t_d0047e_idx'),
        ),
        migrations.AddIndex(
            model_name='question',
            index=models.Index(fields=['section', 'position'], name='dmpt_questi_section_9fdc5f_idx'),
        ),
        migrations.CreateModel(
            name='BooleanQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('dmpt.question',),
        ),
        migrations.CreateModel(
            name='ChoiceQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('dmpt.question',),
        ),
        migrations.CreateModel(
            name='DateRangeQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('dmpt.question',),
        ),
        migrations.CreateModel(
            name='MultipleChoiceOneTextQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('dmpt.question',),
        ),
        migrations.CreateModel(
            name='PositiveIntegerQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=(easydmp.dmpt.models.SimpleFramingTextMixin, 'dmpt.question'),
        ),
        migrations.CreateModel(
            name='ReasonQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=(easydmp.dmpt.models.SimpleFramingTextMixin, 'dmpt.question'),
        ),
        migrations.CreateModel(
            name='ExternalChoiceQuestion',
            fields=[
            ],
            options={
                'indexes': [],
                'proxy': True,
            },
            bases=('dmpt.question',),
        ),
        migrations.CreateModel(
            name='ExternalMultipleChoiceOneTextQuestion',
            fields=[
            ],
            options={
                'indexes': [],
                'proxy': True,
            },
            bases=('dmpt.question',),
        ),
        migrations.CreateModel(
            name='NamedURLQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('dmpt.question',),
        ),
        migrations.CreateModel(
            name='MultiNamedURLOneTextQuestion',
            fields=[
            ],
            options={
                'indexes': [],
                'proxy': True,
            },
            bases=('dmpt.question',),
        ),
        migrations.CreateModel(
            name='ExternalChoiceNotListedQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('dmpt.question',),
        ),
        migrations.CreateModel(
            name='ExternalMultipleChoiceNotListedOneTextQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('dmpt.question',),
        ),
        migrations.CreateModel(
            name='MultiDMPTypedReasonOneTextQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('dmpt.question',),
        ),
        migrations.CreateModel(
            name='ShortFreetextQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=(easydmp.dmpt.models.NoCheckMixin, easydmp.dmpt.models.SimpleFramingTextMixin, 'dmpt.question'),
        ),
        migrations.CreateModel(
            name='DateQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=(easydmp.dmpt.models.NoCheckMixin, easydmp.dmpt.models.SimpleFramingTextMixin, 'dmpt.question'),
        ),
        migrations.CreateModel(
            name='MultiRDACostOneTextQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=(easydmp.dmpt.models.NoCheckMixin, 'dmpt.question'),
        ),
        migrations.CreateModel(
            name='StorageForecastQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=(easydmp.dmpt.models.NoCheckMixin, 'dmpt.question'),
        ),
        migrations.CreateModel(
            name='ExplicitBranch',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('Last', 'Last'), ('CannedAnswer', 'CannedAnswer'), ('ExplicitBranch', 'ExplicitBranch'), ('Edge', 'Edge'), ('Node-edgeless', 'Node-edgeless')], max_length=16)),
                ('condition', models.CharField(blank=True, max_length=255)),
                ('current_question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='forward_transitions', to='dmpt.Question')),
                ('next_question', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='backward_transitions', to='dmpt.Question')),
            ],
            options={
                'unique_together': {('current_question', 'category', 'condition', 'next_question')},
            },
            bases=(easydmp.dmpt.utils.DeletionMixin, models.Model),
        ),
        migrations.CreateModel(
            name='CannedAnswer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('choice', models.CharField(help_text='Human friendly view of condition', max_length=255)),
                ('canned_text', models.TextField(blank=True, null=True)),
                ('comment', models.TextField(blank=True, null=True)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='canned_answers', to='dmpt.Question')),
                ('position', models.PositiveIntegerField(blank=True, default=1, help_text='Position in question. Just used for ordering.', null=True)),
                ('cloned_from', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clones', to='dmpt.CannedAnswer')),
                ('cloned_when', models.DateTimeField(blank=True, null=True)),
                ('transition', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='canned_answers', to='dmpt.ExplicitBranch')),
            ],
        ),
        migrations.AddIndex(
            model_name='cannedanswer',
            index=models.Index(fields=['question', 'position'], name='dmpt_preferred_ca_ordering_idx'),
        ),
        migrations.AddIndex(
            model_name='cannedanswer',
            index=models.Index(fields=['question', 'position', 'id'], name='dmpt_fallback_ca_ordering_idx'),
        ),
    ]
