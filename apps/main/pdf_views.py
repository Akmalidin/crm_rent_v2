import os
from io import BytesIO
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, HRFlowable
)

# ============================================================
# НАСТРОЙКА ШРИФТОВ
# ============================================================

# Путь к шрифтам (DejaVu поддерживает кириллицу)
# Windows: используем шрифты из matplotlib или системные
import sys

def get_font_paths():
    """Найти пути к шрифтам с кириллицей"""
    candidates = [
        # Linux (matplotlib)
        '/usr/local/lib/python3.12/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf',
        '/usr/local/lib/python3.11/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf',
        # Linux (system)
        '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
        '/usr/share/fonts/ttf-dejavu/DejaVuSans.ttf',
        # Windows
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/calibri.ttf',
    ]
    candidates_bold = [
        '/usr/local/lib/python3.12/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf',
        '/usr/local/lib/python3.11/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
        '/usr/share/fonts/ttf-dejavu/DejaVuSans-Bold.ttf',
        'C:/Windows/Fonts/arialbd.ttf',
        'C:/Windows/Fonts/calibrib.ttf',
    ]
    
    font_path = next((p for p in candidates if os.path.exists(p)), None)
    font_bold_path = next((p for p in candidates_bold if os.path.exists(p)), None)
    
    return font_path, font_bold_path

def setup_fonts():
    """Зарегистрировать шрифты"""
    font_path, font_bold_path = get_font_paths()
    
    if font_path:
        pdfmetrics.registerFont(TTFont('MainFont', font_path))
    else:
        # Запасной вариант - стандартный шрифт
        pass
    
    if font_bold_path:
        pdfmetrics.registerFont(TTFont('MainFont-Bold', font_bold_path))


# Инициализируем шрифты
setup_fonts()

# ============================================================
# СТИЛИ
# ============================================================

BLUE = colors.HexColor('#1a56db')
LIGHT_BLUE = colors.HexColor('#e8f0fe')
GREEN = colors.HexColor('#059669')
RED = colors.HexColor('#dc2626')
GRAY = colors.HexColor('#6b7280')
LIGHT_GRAY = colors.HexColor('#f8f9fa')
DARK = colors.HexColor('#1a1a1a')

def get_styles():
    return {
        'company': ParagraphStyle('company',
            fontName='MainFont-Bold', fontSize=18,
            alignment=TA_CENTER, textColor=BLUE, spaceAfter=4),
        'doc_title': ParagraphStyle('doc_title',
            fontName='MainFont-Bold', fontSize=15,
            alignment=TA_CENTER, textColor=DARK, spaceAfter=4),
        'doc_number': ParagraphStyle('doc_number',
            fontName='MainFont', fontSize=10,
            alignment=TA_CENTER, textColor=GRAY, spaceAfter=12),
        'heading': ParagraphStyle('heading',
            fontName='MainFont-Bold', fontSize=11,
            textColor=DARK, spaceBefore=8, spaceAfter=4),
        'normal': ParagraphStyle('normal',
            fontName='MainFont', fontSize=10,
            textColor=DARK, spaceAfter=3),
        'small': ParagraphStyle('small',
            fontName='MainFont', fontSize=9,
            textColor=GRAY, spaceAfter=2),
        'label': ParagraphStyle('label',
            fontName='MainFont-Bold', fontSize=10,
            textColor=GRAY),
        'value': ParagraphStyle('value',
            fontName='MainFont', fontSize=10,
            textColor=DARK),
        'total': ParagraphStyle('total',
            fontName='MainFont-Bold', fontSize=15,
            textColor=BLUE, alignment=TA_RIGHT),
        'total_label': ParagraphStyle('total_label',
            fontName='MainFont', fontSize=10,
            textColor=GRAY, alignment=TA_RIGHT),
        'footer': ParagraphStyle('footer',
            fontName='MainFont', fontSize=8,
            textColor=GRAY, alignment=TA_CENTER),
        'center': ParagraphStyle('center',
            fontName='MainFont', fontSize=10,
            alignment=TA_CENTER, textColor=DARK),
        'big_amount': ParagraphStyle('big_amount',
            fontName='MainFont-Bold', fontSize=24,
            alignment=TA_CENTER, textColor=GREEN),
    }


def build_header(styles, doc_title, doc_number):
    """Создать шапку документа"""
    elements = []
    elements.append(Paragraph('CRM Аренда', styles['company']))
    elements.append(Paragraph(doc_title, styles['doc_title']))
    elements.append(Paragraph(doc_number, styles['doc_number']))
    elements.append(HRFlowable(width='100%', thickness=2, color=BLUE))
    elements.append(Spacer(1, 0.3*cm))
    return elements


def build_info_table(rows):
    """Создать таблицу с информацией (label: value)"""
    styles = get_styles()
    data = [[Paragraph(label, styles['label']), Paragraph(value, styles['value'])]
            for label, value in rows]
    
    table = Table(data, colWidths=[5*cm, 12*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, -1), 10),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#dbeafe')),
    ]))
    return table


def build_footer(styles, text):
    """Создать подвал документа"""
    elements = []
    elements.append(Spacer(1, 0.5*cm))
    elements.append(HRFlowable(width='100%', thickness=0.5, color=GRAY))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(Paragraph(text, styles['footer']))
    return elements


def build_signatures(styles, left_title, right_title, left_name='', right_name=''):
    """Создать блок подписей"""
    data = [
        [Paragraph(f'<b>{left_title}</b>', styles['normal']),
         Paragraph(f'<b>{right_title}</b>', styles['normal'])],
        ['', ''],
        ['', ''],
        [Paragraph('Подпись: ______________________', styles['small']),
         Paragraph('Подпись: ______________________', styles['small'])],
        [Paragraph(f'ФИО: {left_name}', styles['small']),
         Paragraph(f'ФИО: {right_name}', styles['small'])],
        [Paragraph('Дата: ________________________', styles['small']),
         Paragraph('Дата: ________________________', styles['small'])],
    ]
    
    table = Table(data, colWidths=[9*cm, 9*cm])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    return table


# ============================================================
# 1. ДОГОВОР АРЕНДЫ
# ============================================================

def print_contract(request, order_id):
    from apps.rental.models import RentalOrder
    order = get_object_or_404(RentalOrder, id=order_id)
    client = order.client
    
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    
    styles = get_styles()
    elements = []
    
    # Шапка
    elements += build_header(styles,
        'ДОГОВОР АРЕНДЫ ИНСТРУМЕНТОВ',
        f'№ {order.id} от {order.created_at.strftime("%d.%m.%Y")}')
    
    # Информация о сторонах
    phones = ' | '.join([p.phone_number for p in client.phones.all()])
    info_rows = [
        ('Арендодатель:', 'ИП / ООО [Ваше название]'),
        ('Арендатор:', client.get_full_name()),
        ('Телефон:', phones or '—'),
        ('Дата выдачи:', order.created_at.strftime('%d.%m.%Y %H:%M')),
        ('Статус:', 'Активен' if order.status == 'open' else 'Закрыт'),
    ]
    elements.append(build_info_table(info_rows))
    elements.append(Spacer(1, 0.4*cm))
    
    # Таблица товаров
    elements.append(Paragraph('ПЕРЕЧЕНЬ АРЕНДУЕМОГО ИНСТРУМЕНТА:', styles['heading']))
    
    headers = ['#', 'Наименование', 'Кол-во', 'Срок аренды', 'Цена/день', 'Стоимость']
    data = [headers]
    
    for i, item in enumerate(order.items.all(), 1):
        period = f"{item.rental_days} дн."
        if item.rental_hours > 0:
            period += f" {item.rental_hours} ч."
        data.append([
            str(i),
            item.product.name,
            f"{item.quantity_taken} шт",
            period,
            f"{int(item.price_per_day):,} сом".replace(',', ' '),
            f"{int(item.current_total_cost):,} сом".replace(',', ' '),
        ])
    
    col_widths = [0.8*cm, 5.5*cm, 2*cm, 2.5*cm, 2.5*cm, 3.7*cm]
    items_table = Table(data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        # Заголовок
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'MainFont-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
        # Данные
        ('FONTNAME', (0, 1), (-1, -1), 'MainFont'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
        ('TEXTCOLOR', (-1, 1), (-1, -1), BLUE),
        ('FONTNAME', (-1, 1), (-1, -1), 'MainFont-Bold'),
        # Сетка
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(items_table)
    
    # Итого
    total = int(order.get_current_total())
    total_data = [
        [Paragraph('Итого стоимость аренды:', styles['total_label']),
         Paragraph(f"{total:,} сом".replace(',', ' '), styles['total'])],
    ]
    total_table = Table(total_data, colWidths=[12*cm, 5*cm])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(total_table)
    elements.append(Spacer(1, 0.4*cm))
    
    # Условия
    elements.append(Paragraph('УСЛОВИЯ ДОГОВОРА:', styles['heading']))
    conditions = [
        '1. Арендатор обязуется вернуть инструмент в указанный срок и в исправном состоянии.',
        '2. При повреждении или утере инструмента арендатор возмещает полную стоимость.',
        '3. Оплата производится наличными или переводом на момент возврата или до возврата.',
        '4. При досрочном возврате стоимость пересчитывается по фактическому времени использования.',
        '5. При просрочке начисляется дополнительная плата за каждый день просрочки.',
    ]
    for cond in conditions:
        elements.append(Paragraph(cond, styles['normal']))
    
    # Примечания
    if order.notes:
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph(f'Примечания: {order.notes}', styles['small']))
    
    elements.append(Spacer(1, 0.5*cm))
    
    # Подписи
    elements.append(build_signatures(
        styles,
        'АРЕНДОДАТЕЛЬ:',
        'АРЕНДАТОР:',
        right_name=client.get_full_name()
    ))
    
    elements += build_footer(styles,
        f'Документ сформирован автоматически системой CRM Аренда • {order.created_at.strftime("%d.%m.%Y")}')
    
    doc.build(elements)
    
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="contract_{order.id}.pdf"'
    return response


# ============================================================
# 2. КВИТАНЦИЯ ОБ ОПЛАТЕ
# ============================================================

def print_receipt(request, payment_id):
    from apps.rental.models import Payment
    payment = get_object_or_404(Payment, id=payment_id)
    client = payment.client
    
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    
    styles = get_styles()
    elements = []
    
    # Шапка
    elements += build_header(styles,
        'КВИТАНЦИЯ ОБ ОПЛАТЕ',
        f'№ {payment.id} от {payment.payment_date.strftime("%d.%m.%Y")}')
    
    # Информация
    phones = ' | '.join([p.phone_number for p in client.phones.all()])
    info_rows = [
        ('Плательщик:', client.get_full_name()),
        ('Телефон:', phones or '—'),
        ('Дата оплаты:', payment.payment_date.strftime('%d.%m.%Y %H:%M')),
        ('Способ оплаты:', payment.get_payment_method_display()),
    ]
    elements.append(build_info_table(info_rows))
    elements.append(Spacer(1, 0.5*cm))
    
    # Большая сумма
    elements.append(Paragraph('Принято от клиента:', styles['total_label']))
    elements.append(Spacer(1, 0.2*cm))
    amount_data = [[Paragraph(
        f"{int(payment.amount):,} сом".replace(',', ' '),
        styles['big_amount']
    )]]
    amount_table = Table(amount_data, colWidths=[17*cm])
    amount_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#d1fae5')),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('ROUNDEDCORNERS', [5, 5, 5, 5]),
    ]))
    elements.append(amount_table)
    elements.append(Spacer(1, 0.4*cm))
    
    # Примечания
    if payment.notes:
        elements.append(Paragraph('Назначение платежа:', styles['heading']))
        elements.append(Paragraph(payment.notes.replace('\n', '<br/>'), styles['normal']))
        elements.append(Spacer(1, 0.3*cm))
    
    # Баланс клиента
    elements.append(Paragraph('СОСТОЯНИЕ СЧЁТА КЛИЕНТА:', styles['heading']))
    balance_data = [
        ['Всего оплачено:', f"{int(client.get_total_paid()):,} сом".replace(',', ' ')],
        ['Всего долг:', f"{int(client.get_total_debt()):,} сом".replace(',', ' ')],
        ['Баланс кошелька:', f"{int(client.get_wallet_balance()):,} сом".replace(',', ' ')],
    ]
    balance_table = Table(balance_data, colWidths=[8*cm, 9*cm])
    balance_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'MainFont'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'MainFont-Bold'),
        ('FONTNAME', (1, -1), (1, -1), 'MainFont-Bold'),
        ('FONTSIZE', (1, -1), (1, -1), 13),
        ('TEXTCOLOR', (1, 0), (1, 0), GREEN),
        ('TEXTCOLOR', (1, 1), (1, 1), RED),
        ('TEXTCOLOR', (1, 2), (1, 2), BLUE),
        ('BACKGROUND', (0, 2), (-1, 2), LIGHT_BLUE),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(balance_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Подписи
    elements.append(build_signatures(
        styles,
        'ПРИНЯЛ (Кассир):',
        'ОПЛАТИЛ:',
        right_name=client.get_full_name()
    ))
    
    elements += build_footer(styles,
        f'Квитанция сформирована автоматически системой CRM Аренда • {payment.payment_date.strftime("%d.%m.%Y")}')
    
    doc.build(elements)
    
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{payment.id}.pdf"'
    return response


# ============================================================
# 3. АКТ ПРИЁМА-ПЕРЕДАЧИ
# ============================================================

def print_acceptance(request, order_id):
    from apps.rental.models import RentalOrder
    order = get_object_or_404(RentalOrder, id=order_id)
    client = order.client
    
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    
    styles = get_styles()
    elements = []
    
    # Шапка
    elements += build_header(styles,
        'АКТ ПРИЁМА-ПЕРЕДАЧИ',
        f'к Договору аренды № {order.id} от {order.created_at.strftime("%d.%m.%Y")}')
    
    # Информация
    phones = ' | '.join([p.phone_number for p in client.phones.all()])
    info_rows = [
        ('Арендодатель:', 'ИП / ООО [Ваше название]'),
        ('Арендатор:', client.get_full_name()),
        ('Телефон:', phones or '—'),
        ('Дата выдачи:', order.created_at.strftime('%d.%m.%Y %H:%M')),
    ]
    elements.append(build_info_table(info_rows))
    elements.append(Spacer(1, 0.3*cm))
    
    elements.append(Paragraph(
        'Арендодатель передал, а Арендатор принял следующий инструмент в исправном состоянии:',
        styles['normal']))
    elements.append(Spacer(1, 0.3*cm))
    
    # Таблица товаров
    headers = ['#', 'Наименование', 'Кол-во', 'Срок аренды', 'Возврат до', 'Цена/день', 'Стоимость', 'Состояние']
    data = [headers]
    
    for i, item in enumerate(order.items.all(), 1):
        period = f"{item.rental_days} дн."
        if item.rental_hours > 0:
            period += f" {item.rental_hours} ч."
        data.append([
            str(i),
            item.product.name,
            f"{item.quantity_taken} шт",
            period,
            item.planned_return_date.strftime('%d.%m.%Y'),
            f"{int(item.price_per_day):,} сом".replace(',', ' '),
            f"{int(item.current_total_cost):,} сом".replace(',', ' '),
            'Исправен',
        ])
    
    col_widths = [0.6*cm, 4*cm, 1.5*cm, 1.8*cm, 2*cm, 2.2*cm, 2.5*cm, 2.4*cm]
    items_table = Table(data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'MainFont-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'MainFont'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('TEXTCOLOR', (-2, 1), (-2, -1), BLUE),
        ('FONTNAME', (-2, 1), (-2, -1), 'MainFont-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(items_table)
    
    # Итого
    total = int(order.get_current_total())
    total_data = [[
        Paragraph('Итого стоимость аренды:', styles['total_label']),
        Paragraph(f"{total:,} сом".replace(',', ' '), styles['total'])
    ]]
    total_table = Table(total_data, colWidths=[12*cm, 5*cm])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(total_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Подписи
    elements.append(build_signatures(
        styles,
        'ПЕРЕДАЛ (Арендодатель):',
        'ПРИНЯЛ (Арендатор):',
        right_name=client.get_full_name()
    ))
    
    elements += build_footer(styles,
        f'Акт сформирован автоматически системой CRM Аренда • {order.created_at.strftime("%d.%m.%Y")}')
    
    doc.build(elements)
    
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="acceptance_{order.id}.pdf"'
    return response


# ============================================================
# 4. НАКЛАДНАЯ НА ВОЗВРАТ
# ============================================================

def print_return(request, order_id):
    from apps.rental.models import RentalOrder
    from django.utils import timezone
    order = get_object_or_404(RentalOrder, id=order_id)
    client = order.client
    
    # Получаем все возвращённые товары
    returned_items = []
    for item in order.items.all():
        for ret in item.returns.all():
            returned_items.append((item, ret))
    
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    
    styles = get_styles()
    elements = []
    
    # Шапка
    elements += build_header(styles,
        'НАКЛАДНАЯ НА ВОЗВРАТ',
        f'к Договору аренды № {order.id} от {order.created_at.strftime("%d.%m.%Y")}')
    
    # Информация
    phones = ' | '.join([p.phone_number for p in client.phones.all()])
    now = timezone.now()
    info_rows = [
        ('Арендатор:', client.get_full_name()),
        ('Телефон:', phones or '—'),
        ('Заказ №:', f'{order.id} от {order.created_at.strftime("%d.%m.%Y")}'),
        ('Дата возврата:', now.strftime('%d.%m.%Y %H:%M')),
    ]
    elements.append(build_info_table(info_rows))
    elements.append(Spacer(1, 0.3*cm))
    
    elements.append(Paragraph('Арендатор вернул следующий инструмент:', styles['normal']))
    elements.append(Spacer(1, 0.3*cm))
    
    # Таблица возвращённых товаров
    headers = ['#', 'Наименование', 'Кол-во', 'Факт. дней', 'Факт. часов', 'Цена/день', 'Итого']
    data = [headers]
    
    total_return_cost = 0
    for i, (order_item, ret) in enumerate(returned_items, 1):
        cost = int(ret.calculated_cost) if hasattr(ret, 'calculated_cost') else 0
        total_return_cost += cost
        data.append([
            str(i),
            order_item.product.name,
            f"{ret.quantity} шт",
            str(ret.actual_days),
            str(ret.actual_hours),
            f"{int(order_item.price_per_day):,} сом".replace(',', ' '),
            f"{cost:,} сом".replace(',', ' '),
        ])
    
    if not returned_items:
        data.append(['—', 'Нет возвращённых товаров', '—', '—', '—', '—', '—'])
    
    col_widths = [0.8*cm, 5.5*cm, 2*cm, 2*cm, 2*cm, 2.5*cm, 3.2*cm]
    ret_table = Table(data, colWidths=col_widths)
    ret_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'MainFont-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'MainFont'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('TEXTCOLOR', (-1, 1), (-1, -1), BLUE),
        ('FONTNAME', (-1, 1), (-1, -1), 'MainFont-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(ret_table)
    
    # Итого
    original = int(order.get_original_total())
    current = int(order.get_current_total())
    savings = original - current
    
    summary_data = [
        ['Оригинальная стоимость заказа:', f"{original:,} сом".replace(',', ' ')],
        ['Фактическая стоимость (после возвратов):', f"{current:,} сом".replace(',', ' ')],
    ]
    if savings > 0:
        summary_data.append(['Экономия клиента:', f"{savings:,} сом".replace(',', ' ')])
    
    summary_table = Table(summary_data, colWidths=[12*cm, 5*cm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'MainFont'),
        ('FONTNAME', (0, 0), (0, -1), 'MainFont-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (1, 1), (1, 1), 'MainFont-Bold'),
        ('FONTSIZE', (1, 1), (1, 1), 13),
        ('TEXTCOLOR', (1, 1), (1, 1), BLUE),
        ('TEXTCOLOR', (1, 2), (1, 2), GREEN) if savings > 0 else ('TEXTCOLOR', (0, 0), (0, 0), DARK),
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEABOVE', (0, 0), (-1, 0), 1, BLUE),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Подписи
    elements.append(build_signatures(
        styles,
        'ПРИНЯЛ (Арендодатель):',
        'СДАЛ (Арендатор):',
        right_name=client.get_full_name()
    ))
    
    elements += build_footer(styles,
        f'Накладная сформирована автоматически системой CRM Аренда • {now.strftime("%d.%m.%Y")}')
    
    doc.build(elements)
    
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="return_{order.id}.pdf"'
    return response