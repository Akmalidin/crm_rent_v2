from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .tg_handlers import handle_command, handle_callback_query


@csrf_exempt
def telegram_webhook(request):
    """Webhook для получения сообщений от Telegram"""

    if request.method != 'POST':
        return JsonResponse({'ok': False})

    try:
        data = json.loads(request.body)

        if 'message' in data:
            handle_command(data['message'])

        elif 'callback_query' in data:
            handle_callback_query(data['callback_query'])

    except Exception as e:
        print(f"Webhook error: {e}")

    return JsonResponse({'ok': True})
