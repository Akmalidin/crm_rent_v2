from django import forms
from ..rental.models import OrderItem

class EditOrderItemForm(forms.ModelForm):
    '''Форма редактирования позиции заказа'''
    
    class Meta:
        model = OrderItem
        fields = ['planned_return_date', 'quantity', 'price_per_day']
        widgets = {
            'planned_return_date': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': 'px-4 py-2 border rounded-lg'
                }
            ),
        }