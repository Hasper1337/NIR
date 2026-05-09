from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
import os
from datetime import datetime

def generate_report(prediction_data, output_path):
    """
    Генерация PDF-отчёта с результатами анализа.
    
    Аргументы:
        prediction_data: dict с результатами из /api/analyze
        output_path: куда сохранить PDF
    """
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                           rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    story = []
    styles = getSampleStyleSheet()
    
    # Заголовок
    title = Paragraph("<b>Отчёт диагностики</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 0.5*cm))
    
    # Дата
    date = Paragraph(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles['Normal'])
    story.append(date)
    story.append(Spacer(1, 0.5*cm))
    
    # Диагноз
    diag = Paragraph(
        f"<b>Диагноз:</b> {prediction_data['predicted_class']}<br/>"
        f"<b>Уверенность:</b> {prediction_data['confidence']:.1%}",
        styles['Heading3']
    )
    story.append(diag)
    story.append(Spacer(1, 0.5*cm))
    
    # Таблица вероятностей
    data = [['Класс', 'Вероятность']]
    for cls, prob in prediction_data['probabilities'].items():
        data.append([cls, f"{prob:.2%}"])
    
    table = Table(data, colWidths=[8*cm, 4*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976D2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table)
    story.append(Spacer(1, 1*cm))
    
    # Изображения (если есть пути)
    if 'original_url' in prediction_data:
        story.append(Paragraph("<b>Исходное изображение:</b>", styles['Heading4']))
        # Загрузка из static/ по относительному пути
        img_path = prediction_data['original_url'].replace('/static/', 'static/')
        if os.path.exists(img_path):
            img = Image(img_path, width=8*cm, height=8*cm)
            story.append(img)
        story.append(Spacer(1, 0.5*cm))
    
    if 'heatmap_url' in prediction_data:
        story.append(Paragraph("<b>Grad-CAM визуализация:</b>", styles['Heading4']))
        hm_path = prediction_data['heatmap_url'].replace('/static/', 'static/')
        if os.path.exists(hm_path):
            img = Image(hm_path, width=8*cm, height=8*cm)
            story.append(img)
    
    # Построение PDF
    doc.build(story)
    return output_path