from django.apps import AppConfig


class MainConfig(AppConfig):
    name = 'apps.main'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in, user_logged_out
        from django.dispatch import receiver

        @receiver(user_logged_in)
        def on_login(sender, request, user, **kwargs):
            try:
                from apps.main.models import RequestLog
                ip = (request.META.get('HTTP_X_FORWARDED_FOR', '') or
                      request.META.get('REMOTE_ADDR', ''))
                if ',' in ip:
                    ip = ip.split(',')[0].strip()
                RequestLog.objects.create(
                    user=user,
                    username=user.username,
                    ip=ip or None,
                    method='POST',
                    path='/login/',
                    status_code=200,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    event='login',
                )
            except Exception:
                pass

        @receiver(user_logged_out)
        def on_logout(sender, request, user, **kwargs):
            try:
                from apps.main.models import RequestLog
                ip = (request.META.get('HTTP_X_FORWARDED_FOR', '') or
                      request.META.get('REMOTE_ADDR', ''))
                if ',' in ip:
                    ip = ip.split(',')[0].strip()
                RequestLog.objects.create(
                    user=user,
                    username=user.username if user else '',
                    ip=ip or None,
                    method='POST',
                    path='/logout/',
                    status_code=200,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    event='logout',
                )
            except Exception:
                pass
