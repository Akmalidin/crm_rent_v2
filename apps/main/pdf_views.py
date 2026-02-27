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
    Spacer, HRFlowable, PageBreak
)
from django.utils import timezone
from decimal import Decimal
from django.shortcuts import render
from django.template.loader import render_to_string
from apps.company.models import CompanyProfile
from apps.rental.models import RentalOrder

# ============================================================
# НАСТРОЙКА ШРИФТОВ
# ============================================================

# Путь к шрифтам (DejaVu поддерживает кириллицу)
import sys

def get_font_paths():
    """Найти пути к шрифтам с кириллицей"""
    candidates = [
        # Linux (matplotlib)
        '/usr/local/lib/python3.12/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf',
        '/usr/local/lib/python3.11/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf',
        '/usr/local/lib/python3.10/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf',
        # Linux (system)
        '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
        '/usr/share/fonts/ttf-dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        # Windows
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/calibri.ttf',
    ]
    candidates_bold = [
        '/usr/local/lib/python3.12/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf',
        '/usr/local/lib/python3.11/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf',
        '/usr/local/lib/python3.10/dist-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
        '/usr/share/fonts/ttf-dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        'C:/Windows/Fonts/arialbd.ttf',
        'C:/Windows/Fonts/calibrib.ttf',
    ]
    
    font_path = next((p for p in candidates if os.path.exists(p)), None)
    font_bold_path = next((p for p in candidates_bold if os.path.exists(p)), None)
    
    return font_path, font_bold_path

def setup_fonts():
    """Зарегистрировать шрифты с обработкой ошибок"""
    import logging
    logger = logging.getLogger(__name__)
    
    font_path, font_bold_path = get_font_paths()
    
    try:
        if font_path and os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('MainFont', font_path))
            logger.info(f'Registered font: {font_path}')
        else:
            logger.warning('Main font not found, using default Helvetica')
            pdfmetrics.registerFont(TTFont('MainFont', 'Helvetica'))
    except Exception as e:
        logger.error(f'Error registering main font: {e}')
        pdfmetrics.registerFont(TTFont('MainFont', 'Helvetica'))
    
    try:
        if font_bold_path and os.path.exists(font_bold_path):
            pdfmetrics.registerFont(TTFont('MainFont-Bold', font_bold_path))
            logger.info(f'Registered bold font: {font_bold_path}')
        else:
            logger.warning('Bold font not found, using default Helvetica-Bold')
            pdfmetrics.registerFont(TTFont('MainFont-Bold', 'Helvetica-Bold'))
    except Exception as e:
        logger.error(f'Error registering bold font: {e}')
        pdfmetrics.registerFont(TTFont('MainFont-Bold', 'Helvetica-Bold'))

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

def build_header(styles, doc_title, doc_number, company_name='CRM Аренда'):
    """Создать шапку документа"""
    elements = []
    elements.append(Paragraph(company_name, styles['company']))
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

def get_overdue_info(order):
    """Получить информацию о просрочке для заказа"""
    now = timezone.now()
    overdue_items = []
    total_overdue_cost = Decimal('0')
    
    for item in order.items.all():
        if item.quantity_remaining > 0 and item.planned_return_date < now:
            overdue_time = now - item.planned_return_date
            overdue_days = overdue_time.days
            overdue_hours = overdue_time.seconds // 3600
            
            # Расчёт стоимости просрочки
            if overdue_time.total_seconds() < 86400:  # Меньше суток
                hourly_rate = Decimal(str(item.price_per_day)) / 24
                overdue_cost = Decimal(str(overdue_hours)) * hourly_rate * item.quantity_remaining
            else:
                overdue_cost = Decimal(str(overdue_days)) * Decimal(str(item.price_per_day)) * item.quantity_remaining
            
            overdue_items.append({
                'product_name': item.product.name,
                'quantity': item.quantity_remaining,
                'planned_return': item.planned_return_date,
                'overdue_days': overdue_days,
                'overdue_hours': overdue_hours,
                'overdue_cost': overdue_cost,
            })
            total_overdue_cost += overdue_cost
    
    return overdue_items, total_overdue_cost

def build_debt_summary(styles, order, client, currency='сом'):
    """Создать блок сводки по долгу"""
    elements = []
    now = timezone.now()
    
    # Получаем просрочки
    overdue_items, total_overdue_cost = get_overdue_info(order)
    
    # Расчёты
    original_total = Decimal(str(order.get_original_total()))
    current_total = Decimal(str(order.get_current_total()))
    savings = original_total - current_total
    
    # Оплаченная сумма по этому заказу
    total_paid = Decimal('0')
    for payment in client.payments.all():
        if payment.notes and f'#{order.id}' in payment.notes:
            import re
            if 'Распределение:' in payment.notes:
                for line in payment.notes.split('\n'):
                    pattern = rf'Заказ\s*#{order.id}\s*:\s*(\d+(?:[\.,]\d+)?)\s*{currency}'
                    match = re.search(pattern, line)
                    if match:
                        total_paid += Decimal(match.group(1).replace(',', '.'))
                        break
    
    # Долг по заказу
    debt = current_total - total_paid
    
    # Баланс клиента
    client_balance = Decimal(str(client.get_wallet_balance()))
    
    # Сводка по стоимости
    summary_data = [
        ['Оригинальная стоимость:', f"{int(original_total):,} {currency}".replace(',', ' ')],
        ['Текущая стоимость:', f"{int(current_total):,} {currency}".replace(',', ' ')],
    ]
    
    if savings > 0:
        summary_data.append(['Экономия (досрочный возврат):', f"-{int(savings):,} {currency}".replace(',', ' ')])
    
    if total_overdue_cost > 0:
        summary_data.append(['', ''])
        summary_data.append(['⚠️ ПРОСРОЧКА:', ''])
        for item_info in overdue_items:
            summary_data.append([
                f"  • {item_info['product_name']} ({item_info['quantity']} шт)",
                f"{item_info['overdue_days']} дн {item_info['overdue_hours']} ч: +{int(item_info['overdue_cost']):,} {currency}".replace(',', ' ')
            ])
        summary_data.append(['Итого за просрочку:', f"+{int(total_overdue_cost):,} {currency}".replace(',', ' ')])
    
    summary_data.append(['', ''])
    summary_data.append(['Оплачено:', f"{int(total_paid):,} {currency}".replace(',', ' ')])
    
    if debt > 0:
        summary_data.append(['ДОЛГ ПО ЗАКАЗУ:', f"{int(debt):,} {currency}".replace(',', ' ')])
    elif debt < 0:
        summary_data.append(['ПЕРЕПЛАТА:', f"+{int(abs(debt)):,} {currency}".replace(',', ' ')])
    else:
        summary_data.append(['СТАТУС:', '✅ Полностью оплачен'])
    
    # Создаём таблицу
    summary_table = Table(summary_data, colWidths=[10*cm, 8*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
        ('FONTNAME', (0, 0), (-1, -1), 'MainFont'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ('TEXTCOLOR', (-1, 0), (-1, -1), BLUE),
        ('FONTNAME', (-1, 0), (-1, -1), 'MainFont-Bold'),
    ]))
    
    elements.append(Paragraph('ФИНАНСОВАЯ СВОДКА', styles['heading']))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(summary_table)
    
    return elements

# ============================================================
# 1. ДОГОВОР АРЕНДЫ
# ============================================================

def print_contract(request, order_id):
    """Печать договора аренды"""
    order = get_object_or_404(RentalOrder, id=order_id)
    client = order.client
    company = CompanyProfile.get_company()
    
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    
    styles = get_styles()
    elements = []
    
    # Шапка
    order_code = getattr(order, 'order_code', None) or f'#{order.id}'
    elements += build_header(
        styles,
        'ДОГОВОР АРЕНДЫ ИНСТРУМЕНТОВ',
        f'№ {order_code} от {order.created_at.strftime("%d.%m.%Y")}',
        company_name=company.company_name
    )
    
    # Информация о сторонах
    phones = ' | '.join([p.phone_number for p in client.phones.all()])
    info_rows = [
        ('Арендодатель:', company.company_name + (f', ИНН {company.inn}' if company.inn else '')),
        ('Адрес арендодателя:', company.address or '—'),
        ('Телефон арендодателя:', company.phone or '—'),
        ('Арендатор:', client.get_full_name()),
        ('Телефон арендатора:', phones or '—'),
        ('Дата выдачи:', order.created_at.strftime('%d.%m.%Y %H:%M')),
        ('Статус:', 'Активен' if order.status == 'open' else 'Закрыт'),
    ]
    elements.append(build_info_table(info_rows))
    elements.append(Spacer(1, 0.3*cm))
    
    # Заголовок таблицы товаров
    elements.append(Paragraph('ПЕРЕЧЕНЬ АРЕНДУЕМОГО ИНСТРУМЕНТА:', styles['heading']))
    elements.append(Spacer(1, 0.2*cm))
    
    # Таблица товаров
    headers = ['#', 'Наименование', 'Кол-во', 'Срок аренды', 'Цена/день', 'Стоимость']
    data = [headers]
    
    now = timezone.now()
    for i, item in enumerate(order.items.all(), 1):
        is_overdue = item.quantity_remaining > 0 and item.planned_return_date < now
        
        name = item.product.name
        if is_overdue:
            name += '⚠️'
        
        rental_period = f"{item.rental_days} дн"
        if item.rental_hours > 0:
            rental_period += f" {item.rental_hours} ч"
        
        data.append([
            str(i),
            name,
            f"{item.quantity_taken} шт",
            rental_period,
            f"{int(item.price_per_day):,} {company.currency}".replace(',', ' '),
            f"{int(item.current_total_cost):,} {company.currency}".replace(',', ' '),
        ])
    
    col_widths = [1*cm, 6*cm, 2*cm, 2.5*cm, 3*cm, 3.5*cm]
    items_table = Table(data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'MainFont-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
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
    elements.append(items_table)
    elements.append(Spacer(1, 0.3*cm))
    
    # Финансовая сводка
    elements += build_debt_summary(styles, order, client, currency=company.currency)
    elements.append(Spacer(1, 0.3*cm))
    
    # Условия договора
    elements.append(Paragraph('УСЛОВИЯ ДОГОВОРА:', styles['heading']))
    conditions = [
        '1. Арендатор обязуется вернуть инструмент в указанный срок и в исправном состоянии.',
        '2. При повреждении или утере инструмента арендатор возмещает полную стоимость.',
        '3. Оплата производится наличными или переводом на момент возврата или до возврата.',
        '4. При досрочном возврате стоимость пересчитывается по фактическому времени использования.',
        '5. При просрочке начисляется дополнительная плата за каждый день просрочки.',
    ]
    for condition in conditions:
        elements.append(Paragraph(condition, styles['normal']))
    
    if order.notes:
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph(f'<b>Примечания:</b> {order.notes}', styles['normal']))
    
    elements.append(Spacer(1, 0.5*cm))
    
    # Подписи
    elements.append(build_signatures(
        styles,
        'АРЕНДОДАТЕЛЬ:',
        'АРЕНДАТОР:',
        left_name=company.short_name or company.company_name,
        right_name=client.get_full_name()
    ))
    
    # Футер
    footer_text = ''
    if company.footer_text:
        footer_text = company.footer_text + '\n'
    footer_text += f'Документ сформирован автоматически системой {company.company_name} • {timezone.now().strftime("%d.%m.%Y")}'
    elements += build_footer(styles, footer_text)
    
    doc.build(elements)
    
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="contract_{order.id}_{order_code}.pdf"'
    return response

# ============================================================
# 2. КВИТАНЦИЯ ОБ ОПЛАТЕ
# ============================================================

def print_receipt(request, payment_id):
    """Печать квитанции об оплате"""
    from apps.rental.models import Payment
    
    payment = get_object_or_404(Payment, id=payment_id)
    client = payment.client
    company = CompanyProfile.get_company()
    
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    
    styles = get_styles()
    elements = []
    
    # Шапка
    elements += build_header(
        styles,
        'КВИТАНЦИЯ ОБ ОПЛАТЕ',
        f'№ {payment.id} от {payment.payment_date.strftime("%d.%m.%Y")}',
        company_name=company.company_name
    )
    
    # Информация об оплате
    phones = ' | '.join([p.phone_number for p in client.phones.all()])
    info_rows = [
        ('Плательщик:', client.get_full_name()),
        ('Телефон:', phones or '—'),
        ('Дата оплаты:', payment.payment_date.strftime('%d.%m.%Y %H:%M')),
        ('Способ оплаты:', payment.get_payment_method_display()),
    ]
    elements.append(build_info_table(info_rows))
    elements.append(Spacer(1, 0.5*cm))
    
    # Сумма (большая и красивая)
    from reportlab.platypus import KeepTogether

    amount_elements = []
    amount_elements.append(Paragraph('Принято от клиента:', styles['total_label']))
    amount_elements.append(Spacer(1, 0.2*cm))
    amount_elements.append(Paragraph(f"{int(payment.amount):,} {company.currency}".replace(',', ' '), styles['big_amount']))
    amount_elements.append(Spacer(1, 0.7*cm))

    # Способ оплаты в отдельной строке
    payment_method_para = Paragraph(
        f'<font color="gray" size="9">{payment.get_payment_method_display()}</font>',
        styles['center']
    )
    amount_elements.append(payment_method_para)

    # Создаём таблицу с рамкой
    amount_box_data = [[amount_elements]]
    amount_box = Table(amount_box_data, colWidths=[16*cm])
    amount_box.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 2, BLUE),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    elements.append(amount_box)
    elements.append(Spacer(1, 0.5*cm))
    
    # Примечания
    if payment.notes:
        elements.append(Paragraph('<b>Назначение платежа:</b>', styles['heading']))
        elements.append(Paragraph(payment.notes.replace('\n', '<br/>'), styles['normal']))
        elements.append(Spacer(1, 0.3*cm))
    
    # Итого с балансом
    total_paid = client.get_total_paid()
    total_debt = client.get_total_debt()
    wallet_balance = client.get_wallet_balance()
    
    balance_data = [
        ['Всего оплачено клиентом:', f"{int(total_paid):,} {company.currency}".replace(',', ' ')],
        ['Общий долг клиента:', f"{int(total_debt):,} {company.currency}".replace(',', ' ')],
        ['Баланс кошелька:', f"{int(wallet_balance):,} {company.currency}".replace(',', ' ')],
    ]
    
    balance_table = Table(balance_data, colWidths=[10*cm, 8*cm])
    balance_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'MainFont'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'MainFont-Bold'),
        ('FONTNAME', (-1, -1), (-1, -1), 'MainFont-Bold'),
        ('FONTSIZE', (-1, -1), (-1, -1), 12),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ('TEXTCOLOR', (-1, 0), (-1, 0), GREEN),
        ('TEXTCOLOR', (-1, 1), (-1, 1), RED),
        ('TEXTCOLOR', (-1, 2), (-1, 2), GREEN if wallet_balance >= 0 else RED),
        ('BACKGROUND', (0, 2), (-1, 2), LIGHT_BLUE),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(balance_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Подписи
    elements.append(build_signatures(
        styles,
        'ПРИНЯЛ (Кассир):',
        'ОПЛАТИЛ:',
        left_name=company.short_name or company.company_name,
        right_name=client.get_full_name()
    ))
    
    # Футер
    footer_text = ''
    if company.footer_text:
        footer_text = company.footer_text + '\n'
    footer_text += f'Квитанция сформирована системой {company.company_name} • {payment.payment_date.strftime("%d.%m.%Y")}'
    elements += build_footer(styles, footer_text)
    
    doc.build(elements)
    
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{payment.id}.pdf"'
    return response


def _build_receipt_elements(styles, company, client, payment):
    """Собрать элементы одной квитанции для мульти-печати"""
    elements = []

    elements += build_header(
        styles,
        'КВИТАНЦИЯ ОБ ОПЛАТЕ',
        f'№ {payment.id} от {payment.payment_date.strftime("%d.%m.%Y")}',
        company_name=company.company_name
    )

    phones = ' | '.join([p.phone_number for p in client.phones.all()])
    info_rows = [
        ('Плательщик:', client.get_full_name()),
        ('Телефон:', phones or '—'),
        ('Дата оплаты:', payment.payment_date.strftime('%d.%m.%Y %H:%M')),
        ('Способ оплаты:', payment.get_payment_method_display()),
    ]
    elements.append(build_info_table(info_rows))
    elements.append(Spacer(1, 0.5*cm))

    amount_elements = []
    amount_elements.append(Paragraph('Принято от клиента:', styles['total_label']))
    amount_elements.append(Spacer(1, 0.2*cm))
    amount_elements.append(Paragraph(f"{int(payment.amount):,} {company.currency}".replace(',', ' '), styles['big_amount']))
    amount_elements.append(Spacer(1, 0.7*cm))
    amount_elements.append(
        Paragraph(
            f'<font color="gray" size="9">{payment.get_payment_method_display()}</font>',
            styles['center']
        )
    )

    amount_box = Table([[amount_elements]], colWidths=[16*cm])
    amount_box.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 2, BLUE),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    elements.append(amount_box)
    elements.append(Spacer(1, 0.5*cm))

    if payment.notes:
        elements.append(Paragraph('<b>Назначение платежа:</b>', styles['heading']))
        elements.append(Paragraph(payment.notes.replace('\n', '<br/>'), styles['normal']))
        elements.append(Spacer(1, 0.3*cm))

    total_paid = client.get_total_paid()
    total_debt = client.get_total_debt()
    wallet_balance = client.get_wallet_balance()

    balance_data = [
        ['Всего оплачено клиентом:', f"{int(total_paid):,} {company.currency}".replace(',', ' ')],
        ['Общий долг клиента:', f"{int(total_debt):,} {company.currency}".replace(',', ' ')],
        ['Баланс кошелька:', f"{int(wallet_balance):,} {company.currency}".replace(',', ' ')],
    ]

    balance_table = Table(balance_data, colWidths=[10*cm, 8*cm])
    balance_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'MainFont'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'MainFont-Bold'),
        ('FONTNAME', (-1, -1), (-1, -1), 'MainFont-Bold'),
        ('FONTSIZE', (-1, -1), (-1, -1), 12),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ('TEXTCOLOR', (-1, 0), (-1, 0), GREEN),
        ('TEXTCOLOR', (-1, 1), (-1, 1), RED),
        ('TEXTCOLOR', (-1, 2), (-1, 2), GREEN if wallet_balance >= 0 else RED),
        ('BACKGROUND', (0, 2), (-1, 2), LIGHT_BLUE),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(balance_table)
    elements.append(Spacer(1, 0.5*cm))

    elements.append(build_signatures(
        styles,
        'ПРИНЯЛ (Кассир):',
        'ОПЛАТИЛ:',
        left_name=company.short_name or company.company_name,
        right_name=client.get_full_name()
    ))

    footer_text = ''
    if company.footer_text:
        footer_text = company.footer_text + '\n'
    footer_text += f'Квитанция сформирована системой {company.company_name} • {payment.payment_date.strftime("%d.%m.%Y")}'
    elements += build_footer(styles, footer_text)

    return elements


def print_receipts_bulk(request, client_id):
    """Скачать одним PDF все квитанции клиента (или по конкретному заказу)"""
    from apps.rental.models import Payment
    from apps.clients.models import Client
    import re

    client = get_object_or_404(Client, id=client_id)
    company = CompanyProfile.get_company()

    order_id = request.GET.get('order')
    payments_qs = client.payments.all()

    order_id_int = None
    if order_id:
        try:
            order_id_int = int(order_id)
        except (TypeError, ValueError):
            order_id_int = None

    if order_id_int:
        payments_qs = payments_qs.filter(notes__icontains=f'#{order_id_int}')

    payments = payments_qs.order_by('payment_date')

    if not payments.exists():
        return HttpResponse('Нет квитанций для печати', status=404)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = get_styles()
    elements = []

    for idx, payment in enumerate(payments):
        elements += _build_receipt_elements(styles, company, client, payment)
        if idx < (payments.count() - 1):
            elements.append(PageBreak())

    doc.build(elements)

    suffix = f"_order_{order_id_int}" if order_id_int else ""
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipts_client_{client.id}{suffix}.pdf"'
    return response

# ============================================================
# 3. АКТ ПРИЁМА-ПЕРЕДАЧИ
# ============================================================

def print_acceptance(request, order_id):
    """Печать акта приёма-передачи"""
    order = get_object_or_404(RentalOrder, id=order_id)
    client = order.client
    company = CompanyProfile.get_company()
    now = timezone.now()
    
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    
    styles = get_styles()
    elements = []
    
    # Шапка
    order_code = getattr(order, 'order_code', None) or f'#{order.id}'
    elements += build_header(
        styles,
        'АКТ ПРИЁМА-ПЕРЕДАЧИ',
        f'к Договору аренды № {order_code} от {order.created_at.strftime("%d.%m.%Y")}',
        company_name=company.company_name
    )
    
    # Информация
    phones = ' | '.join([p.phone_number for p in client.phones.all()])
    info_rows = [
        ('Арендодатель:', company.company_name),
        ('Адрес:', company.address or '—'),
        ('Арендатор:', client.get_full_name()),
        ('Телефон:', phones or '—'),
        ('Дата выдачи:', order.created_at.strftime('%d.%m.%Y %H:%M')),
    ]
    elements.append(build_info_table(info_rows))
    elements.append(Spacer(1, 0.3*cm))
    
    elements.append(Paragraph('Арендодатель передал, а Арендатор принял следующий инструмент в исправном состоянии:', styles['normal']))
    elements.append(Spacer(1, 0.3*cm))
    
    # Таблица товаров
    headers = ['#', 'Наименование', 'Кол-во', 'Срок', 'Возврат до', 'Цена/день', 'Стоимость', 'Состояние']
    data = [headers]
    
    for i, item in enumerate(order.items.all(), 1):
        is_overdue = item.quantity_remaining > 0 and item.planned_return_date < now
        
        rental_period = f"{item.rental_days} дн"
        if item.rental_hours > 0:
            rental_period += f" {item.rental_hours} ч"
        
        status = 'Просрочен' if is_overdue else 'Исправен'
        
        data.append([
            str(i),
            item.product.name,
            f"{item.quantity_taken} шт",
            rental_period,
            item.planned_return_date.strftime('%d.%m.%Y'),
            f"{int(item.price_per_day):,} {company.currency}".replace(',', ' '),
            f"{int(item.current_total_cost):,} {company.currency}".replace(',', ' '),
            status,
        ])
    
    col_widths = [0.8*cm, 4.5*cm, 1.5*cm, 2*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2*cm]
    items_table = Table(data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'MainFont-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'MainFont'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('TEXTCOLOR', (-2, 1), (-2, -1), BLUE),
        ('FONTNAME', (-2, 1), (-2, -1), 'MainFont-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.3*cm))
    
    # Финансовая сводка
    elements += build_debt_summary(styles, order, client, currency=company.currency)
    elements.append(Spacer(1, 0.5*cm))
    
    # Подписи
    elements.append(build_signatures(
        styles,
        'ПЕРЕДАЛ (Арендодатель):',
        'ПРИНЯЛ (Арендатор):',
        left_name=company.short_name or company.company_name,
        right_name=client.get_full_name()
    ))
    
    # Футер
    footer_text = ''
    if company.footer_text:
        footer_text = company.footer_text + '\n'
    footer_text += f'Акт сформирован системой {company.company_name} • {now.strftime("%d.%m.%Y")}'
    elements += build_footer(styles, footer_text)
    
    doc.build(elements)
    
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="acceptance_{order.id}_{order_code}.pdf"'
    return response

# ============================================================
# 4. НАКЛАДНАЯ НА ВОЗВРАТ
# ============================================================

def print_return(request, order_id):
    """Печать накладной на возврат"""
    order = get_object_or_404(RentalOrder, id=order_id)
    client = order.client
    company = CompanyProfile.get_company()
    now = timezone.now()
    
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
    order_code = getattr(order, 'order_code', None) or f'#{order.id}'
    elements += build_header(
        styles,
        'НАКЛАДНАЯ НА ВОЗВРАТ',
        f'к Договору аренды № {order_code} от {order.created_at.strftime("%d.%m.%Y")}',
        company_name=company.company_name
    )
    
    # Информация
    phones = ' | '.join([p.phone_number for p in client.phones.all()])
    info_rows = [
        ('Арендодатель:', company.company_name),
        ('Арендатор:', client.get_full_name()),
        ('Телефон:', phones or '—'),
        ('Заказ №:', f'{order_code} от {order.created_at.strftime("%d.%m.%Y")}'),
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
        if ret.calculated_cost is not None:
            cost = int(ret.calculated_cost)
        else:
            cost = 0
            
        total_return_cost += cost
        data.append([
            str(i),
            order_item.product.name,
            f"{ret.quantity} шт",
            str(ret.actual_days),
            str(ret.actual_hours),
            f"{int(order_item.price_per_day):,} {company.currency}".replace(',', ' '),
            f"{cost:,} {company.currency}".replace(',', ' '),
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
    
    # ИТОГО + ДОЛГ/ПРОСРОЧКА
    elements.append(Spacer(1, 0.3*cm))
    elements += build_debt_summary(styles, order, client, currency=company.currency)
    elements.append(Spacer(1, 0.5*cm))
    
    # Невозвращённые товары
    unreturned = [item for item in order.items.all() if item.quantity_remaining > 0]
    if unreturned:
        elements.append(Paragraph('⚠️ НЕВОЗВРАЩЁННЫЕ ТОВАРЫ:', styles['heading']))
        for item in unreturned:
            is_overdue = item.planned_return_date < now
            overdue_text = ''
            if is_overdue:
                overdue_days = (now - item.planned_return_date).days
                overdue_text = f' (ПРОСРОЧЕНО на {overdue_days} дн!)'
            
            text = f"• {item.product.name} — {item.quantity_remaining} шт (возврат до: {item.planned_return_date.strftime('%d.%m.%Y %H:%M')}){overdue_text}"
            elements.append(Paragraph(text, styles['small']))
        elements.append(Spacer(1, 0.3*cm))
    
    # Подписи
    elements.append(build_signatures(
        styles,
        'ПРИНЯЛ (Арендодатель):',
        'СДАЛ (Арендатор):',
        left_name=company.short_name or company.company_name,
        right_name=client.get_full_name()
    ))
    
    # Футер
    footer_text = ''
    if company.footer_text:
        footer_text = company.footer_text + '\n'
    footer_text += f'Накладная сформирована системой {company.company_name} • {now.strftime("%d.%m.%Y")}'
    elements += build_footer(styles, footer_text)
    
    doc.build(elements)
    
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="return_{order.id}_{order_code}.pdf"'
    return response