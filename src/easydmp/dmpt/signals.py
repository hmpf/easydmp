from django.db.models.signals import pre_save
from django.dispatch import receiver


@receiver(pre_save, sender='dmpt.Question')
def prohibit_0_question_position(sender, instance, **kwargs):
    if instance.position == 0:
        raise ValueError('Question position 0 is reserved for internal use')
