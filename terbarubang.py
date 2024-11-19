import hashlib
import requests
import re
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Konstanta
API_URL_LOGIN = "https://mtacc.mobilelegends.com/v2.1/inapp/login-new"
API_URL_CHANGE_EMAIL = "https://mtacc.mobilelegends.com/v2.1/inapp/changebindemail"
BOT_TOKEN = "YOUR_BOT_TOKEN"
user_data = {}

# Fungsi Validasi
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

# Fungsi Konversi MD5
def convert_password_to_md5(password):
    md5_hash = hashlib.md5()
    md5_hash.update(password.encode("utf-8"))
    return md5_hash.hexdigest()

# Fungsi Login untuk mengambil session
def login(account, password, verification_code):
    md5pwd = convert_password_to_md5(password)
    login_data = {
        "op": "login",
        "sign": "ca62428dca478c20b860f65cf000201f",
        "params": {"account": account, "md5pwd": md5pwd, "game_token": "", "recaptcha_token": verification_code},
        "lang": "cn",
    }

    try:
        response = requests.post(API_URL_LOGIN, json=login_data, timeout=10)
        if response.status_code == 200:
            login_response = response.json()
            game_token = login_response.get("data", {}).get("game_token")
            guid = login_response.get("data", {}).get("guid")
            token = login_response.get("data", {}).get("token")
            session = login_response.get("data", {}).get("session")  # Menambahkan session
            return game_token, guid, token, session
    except requests.RequestException as e:
        logger.error(f"Login request failed: {e}")
    return None, None, None, None

# Fungsi Ganti Email
def change_email(game_token, guid, token, new_email, verification_code_new_email):
    change_email_data = {
        "op": "email_rebind_email_code_second",  # Ganti OP untuk email baru
        "params": {"email": new_email, "guid": guid, "game_token": game_token, "token": verification_code_new_email, "verification_code": verification_code_new_email},
        "lang": "id",
    }
    try:
        response = requests.post(API_URL_CHANGE_EMAIL, json=change_email_data, timeout=10)
        if response.status_code == 200:
            return response.json().get("message", "Sukses.")
    except requests.RequestException as e:
        logger.error(f"Change email request failed: {e}")
    return "Permintaan gagal."

# Fungsi untuk mengirim kode ke email lama
def send_old_email_verification_code(game_token, guid, token):
    old_email_verification_data = {
        "op": "email_rebind_email_code",  # Ganti OP untuk kode email lama
        "params": {"sign": "ca62428dca478c20b860f65cf000201f", "game_token": game_token, "guid": guid, "token": token},
        "lang": "id",
    }
    try:
        response = requests.post(API_URL_CHANGE_EMAIL, json=old_email_verification_data, timeout=10)
        if response.status_code == 200:
            return response.json().get("message", "Kode verifikasi telah dikirim.")
    except requests.RequestException as e:
        logger.error(f"Failed to send old email verification code: {e}")
    return "Gagal mengirim kode verifikasi email lama."

# Command Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selamat datang! Kirimkan ID Anda.")
    return "WAITING_FOR_ID"

# Menangani ID
async def receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    roleid = update.message.text
    user_data[update.message.chat_id] = {"roleid": roleid}
    await update.message.reply_text("Sekarang, kirimkan server Anda.")
    return "WAITING_FOR_SERVER"

# Menangani server
async def receive_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    zoneid = update.message.text
    user_data[update.message.chat_id]["zoneid"] = zoneid
    await update.message.reply_text("Sekarang, kirimkan email lama Anda.")
    return "WAITING_FOR_OLD_EMAIL"

# Menangani email lama
async def receive_old_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    old_email = update.message.text
    if not is_valid_email(old_email):
        await update.message.reply_text("Format email salah. Coba lagi.")
        return "WAITING_FOR_OLD_EMAIL"
    user_data[update.message.chat_id]["old_email"] = old_email
    await update.message.reply_text("Sekarang, kirimkan password Moonton Anda.")
    return "WAITING_FOR_PASSWORD"

# Menangani password
async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    user_data[update.message.chat_id]["password"] = password
    await update.message.reply_text("Sekarang, kirimkan kode verifikasi Moonton (dikirim ke email lama).")
    return "WAITING_FOR_MOONTON_VERIFICATION_CODE"

# Menangani kode verifikasi Moonton
async def receive_moonton_verification_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    verification_code = update.message.text
    user_data[update.message.chat_id]["verification_code"] = verification_code
    await update.message.reply_text("Sekarang, kirimkan email baru yang ingin Anda kaitkan.")
    return "WAITING_FOR_NEW_EMAIL"

# Menangani email baru
async def receive_new_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_email = update.message.text
    if not is_valid_email(new_email):
        await update.message.reply_text("Format email salah. Coba lagi.")
        return "WAITING_FOR_NEW_EMAIL"
    user_data[update.message.chat_id]["new_email"] = new_email
    await update.message.reply_text("Terakhir, kirimkan kode verifikasi dari email baru.")
    return "WAITING_FOR_NEW_EMAIL_VERIFICATION_CODE"

# Menangani kode verifikasi email baru
async def receive_new_email_verification_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_email_verification_code = update.message.text
    user_data[update.message.chat_id]["new_email_verification_code"] = new_email_verification_code

    # Ambil data yang diperlukan untuk login
    roleid = user_data[update.message.chat_id]["roleid"]
    zoneid = user_data[update.message.chat_id]["zoneid"]
    old_email = user_data[update.message.chat_id]["old_email"]
    password = user_data[update.message.chat_id]["password"]
    verification_code = user_data[update.message.chat_id]["verification_code"]
    new_email = user_data[update.message.chat_id]["new_email"]

    # Login ke Mobile Legends dan dapatkan game_token, guid, token, session
    game_token, guid, token, session = login(old_email, password, verification_code)

    if game_token and guid and token:
        # Kirim kode verifikasi ke email lama
        result = send_old_email_verification_code(game_token, guid, token)
        await update.message.reply_text(result)

        # Ganti email setelah verifikasi
        result = change_email(game_token, guid, token, new_email, new_email_verification_code)
        await update.message.reply_text(result)
    else:
        await update.message.reply_text("Login gagal. Cek kembali email, password, atau kode verifikasi Anda.")

    # Reset data untuk pengguna
    user_data.pop(update.message.chat_id, None)

    return ConversationHandler.END

# Menangani pembatalan
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Proses dibatalkan. Anda bisa mulai lagi dengan mengetik /start.")
    return ConversationHandler.END

# Penanganan Error
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.message:
        await update.message.reply_text("Terjadi kesalahan. Silakan coba lagi nanti.")

# Fungsi utama
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Definisikan langkah percakapan
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            "WAITING_FOR_ID": [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id)],
            "WAITING_FOR_SERVER": [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_server)],
            "WAITING_FOR_OLD_EMAIL": [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_old_email)],
            "WAITING_FOR_PASSWORD": [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
            "WAITING_FOR_MOONTON_VERIFICATION_CODE": [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_moonton_verification_code)],
            "WAITING_FOR_NEW_EMAIL": [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_email)],
            "WAITING_FOR_NEW_EMAIL_VERIFICATION_CODE": [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_email_verification_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conversation_handler)
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == "__main__":
    main()