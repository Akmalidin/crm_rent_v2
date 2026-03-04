from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .telegram_bot_complete import handle_command, handle_callback_query


@csrf_exempt
def telegram_webhook(request):
    """Webhook для получения сообщений от Telegram"""
    
    if request.method != 'POST':
        return JsonResponse({'ok': False})
    
    try:
        data = json.loads(request.body)
        
        # Обработка обычного сообщения
        if 'message' in data:
            message = data['message']
            handle_command(message)
        
        # Обработка нажатия кнопки
        elif 'callback_query' in data:
            callback_query = data['callback_query']
            handle_callback_query(callback_query)
            
    except Exception as e:
        print(f"Webhook error: {e}")
    
    return JsonResponse({'ok': True})