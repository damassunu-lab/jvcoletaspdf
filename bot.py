import os
import glob
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import img2pdf

# Configurar logs
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

TOKEN = os.getenv("TOKEN")
BASE_DIR = "downloads_temp"
os.makedirs(BASE_DIR, exist_ok=True)

# 1. Mini servidor Flask para satisfazer a exigência de porta HTTP do Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Telegram PDF está online e rodando!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Funções do Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Olá! Envie suas 30+ fotos em sequência.\n\n"
        "Comandos:\n"
        "• `/gerar_pdf` - Gera o PDF com nome padrão.\n"
        "• `/gerar_pdf nome_personalizado` - Gera o PDF com nome escolhido."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_folder = os.path.join(BASE_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    
    existing_files = glob.glob(os.path.join(user_folder, "*.jpg"))
    file_index = len(existing_files) + 1
    file_path = os.path.join(user_folder, f"{file_index:04d}.jpg")

    await file.download_to_drive(file_path)
    await update.message.reply_text(f"📥 Foto {file_index} armazenada com sucesso.")

async def gerar_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_folder = os.path.join(BASE_DIR, str(user_id))
    
    image_paths = sorted(glob.glob(os.path.join(user_folder, "*.jpg")))
    
    if not image_paths:
        await update.message.reply_text("⚠️ Nenhuma foto encontrada! Envie as imagens antes de usar o comando.")
        return

    args = context.args
    pdf_name = "documento_convertido.pdf"
    if args:
        custom_name = "_".join(args)
        if not custom_name.endswith(".pdf"):
            custom_name += ".pdf"
        pdf_name = "".join(c for c in custom_name if c.isalnum() or c in (' ', '.', '_', '-')).strip()
        if not pdf_name:
            pdf_name = "documento_convertido.pdf"

    pdf_path = os.path.join(BASE_DIR, f"{user_id}_{pdf_name}")
    
    try:
        await update.message.reply_text(f"⚙️ Processando {len(image_paths)} imagens e gerando o PDF...")
        
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(image_paths))
        
        with open(pdf_path, "rb") as f:
            await update.message.reply_document(document=f, filename=pdf_name)
            
        await update.message.reply_text("✅ PDF gerado e enviado com sucesso!")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao gerar o PDF: {e}")
    finally:
        for img in image_paths:
            os.remove(img)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

def main():
    # Inicia o servidor Flask em uma thread separada para manter a porta aberta para o Render
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Configuração do Bot do Telegram
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("gerar_pdf", gerar_pdf))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    application.run_polling()

if __name__ == "__main__":
    main()
