import sqlite3
from datetime import datetime, timedelta
import pytz
from io import BytesIO

from aiogram import Bot
from aiogram.types import BufferedInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.database.db import DB_PATH
from config import TIMEZONE

# --- KUNLIK HISOBOT FUNKSIYASI ---
async def daily_report_job(bot: Bot):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    yesterday_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, balance FROM users")
    users = cursor.fetchall()
    
    for user_id, balance in users:
        cursor.execute("""
            SELECT c.name, e.item_name, e.amount, e.time 
            FROM expenses e
            JOIN categories c ON e.category_id = c.id
            WHERE e.user_id = ? AND e.date = ?
        """, (user_id, yesterday_date))
        rows = cursor.fetchall()
        
        if not rows:
            continue
            
        text = f"📊 **Kunlik Hisobot ({yesterday_date}):**\n\n"
        total = 0
        for cat, item, amt, tm in rows:
            text += f"• [{tm}] {cat}: {item} — {amt:,.0f} so'm\n"
            total += amt
        text += f"\n━━━━━━━━━━\n💰 **Jami xarajat: {total:,.0f} so'm**\n💳 **Qolgan balans: {balance:,.0f} so'm**"
        
        try:
            await bot.send_message(user_id, text, parse_mode="Markdown")
        except Exception as e:
            print(f"Xatolik (Kunlik hisobot, {user_id}): {e}")
            
    conn.close()

# --- HAFTALIK PDF HISOBOT FUNKSIYASI ---
async def weekly_pdf_report_job(bot: Bot):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today_str = now.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, balance FROM users")
    users = cursor.fetchall()
    
    for user_id, balance in users:
        cursor.execute("""
            SELECT e.date, c.name, e.item_name, e.amount 
            FROM expenses e
            JOIN categories c ON e.category_id = c.id
            WHERE e.user_id = ? AND e.date BETWEEN ? AND ?
            ORDER BY e.date DESC
        """, (user_id, week_ago, today_str))
        rows = cursor.fetchall()
        
        if not rows:
            continue
            
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=12
        )
        
        elements.append(Paragraph("Haftalik Moliyaviy Hisobot", title_style))
        elements.append(Paragraph(f"Davr: {week_ago} dan {today_str} gacha", styles['Normal']))
        elements.append(Spacer(1, 15))
        
        table_data = [["Sana", "Kategoriya", "Nomi", "Summa (so'm)"]]
        total_week = 0
        for dt, cat, item, amt in rows:
            table_data.append([dt, cat, item, f"{amt:,.0f}"])
            total_week += amt
            
        t = Table(table_data, colWidths=[80, 110, 140, 110])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4A90E2")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#F9F9F9")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 15))
        
        elements.append(Paragraph(f"<b>Jami haftalik xarajat:</b> {total_week:,.0f} so'm", styles['Normal']))
        elements.append(Paragraph(f"<b>Joriy balans:</b> {balance:,.0f} so'm", styles['Normal']))
        
        doc.build(elements)
        buffer.seek(0)
        
        pdf_file = BufferedInputFile(buffer.getvalue(), filename="weekly_report.pdf")
        try:
            await bot.send_document(
                user_id, 
                pdf_file, 
                caption="📄 Sizning haftalik moliyaviy hisobotingiz (PDF formatida)."
            )
        except Exception as e:
            print(f"Xatolik (Haftalik PDF, {user_id}): {e}")
            
    conn.close()

# --- SCHEDULERNI ISHGA TUSHIRISH ---
def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))
    
    # Har kuni soat 00:00 da kunlik hisobot
    scheduler.add_job(daily_report_job, 'cron', hour=0, minute=0, args=[bot])
    
    # Har yakshanba soat 18:00 da haftalik PDF hisobot
    scheduler.add_job(weekly_pdf_report_job, 'cron', day_of_week='sun', hour=18, minute=0, args=[bot])
    
    scheduler.start()
