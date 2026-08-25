from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver


@receiver(post_save, sender='accounts.CustomUser')
def _custom_user_post_save(sender, instance, created, **kwargs):
    try:
        from .services import UserHierarchyService
        UserHierarchyService.ensure_hierarchy_for_user(instance, audit_actor=instance)
    except Exception:
        pass


@receiver(m2m_changed, sender='accounts.CustomUser.positions.through')
def _custom_user_positions_changed(sender, instance, action, **kwargs):
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return
    try:
        from .services import UserHierarchyService
        UserHierarchyService.ensure_hierarchy_for_user(instance, audit_actor=instance)
    except Exception:
        pass
