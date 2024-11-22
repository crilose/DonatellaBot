from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, JobQueue
from config import TELEGRAM_TOKEN  # Importa il token dal file di configurazione
import openai
from datetime import datetime, time
import json
import os

# Usa datetime.time correttamente

# Configura OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Verifica se la chiave è presente
if openai.api_key is None:
    print("Errore: la chiave API di OpenAI non è stata trovata.")
else:
    print("Chiave API di OpenAI caricata correttamente.")

# Percorso del file JSON per salvare i messaggi
MESSAGES_FILE = 'messages.json'

# Ora specifica per il riassunto giornaliero
RIASSUNTO_ORA = 17
RIASSUNTO_MINUTO = 20
riassunto_orario = time(RIASSUNTO_ORA, RIASSUNTO_MINUTO)
# ID della chat da impostare una volta che lo ottieni tramite il comando `/getchatid`
CHAT_ID = None  # Per ora lascia vuoto, verrà settato dopo aver ottenuto l'ID della chat


# Funzione per ottenere l'ID della chat
async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    chat_id = update.message.chat_id  # Ottieni l'ID della chat
    CHAT_ID = chat_id  # Salva l'ID
    await update.message.reply_text(f"L'ID della chat è: {chat_id}")


# Funzione di avvio del bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Risponde con un messaggio di benvenuto quando l'utente invia il comando /start
    await update.message.reply_text(
        "Ciao! Sono il bot che riassume i messaggi di questo gruppo ogni giorno."
    )


# Funzione per salvare i messaggi nel file JSON
async def save_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Controlla se update.message è valido
    if not update.message or not update.message.text:
        return  # Ignora aggiornamenti senza messaggi di testo

    user = update.message.from_user.full_name  # Nome dell'utente
    text = update.message.text  # Testo del messaggio

    # Ottieni la data odierna come stringa (formato YYYY-MM-DD)
    today = datetime.now().strftime('%Y-%m-%d')

    # Se il file non esiste o è vuoto, crealo
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'w') as f:
            json.dump({}, f)

    # Leggi i messaggi già salvati nel file JSON
    try:
        with open(MESSAGES_FILE, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        # Se il file è vuoto o non è un JSON valido, inizializza il dizionario
        data = {}

    # Aggiungi il messaggio alla lista del giorno corrente
    if today not in data:
        data[today] = []
    data[today].append(f"{user}: {text}")

    # Salva nuovamente i dati nel file JSON
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# Funzione per fare il riassunto su richiesta
async def riassumi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID:
        await update.message.reply_text("Impossibile ottenere l'ID della chat."
                                        )
        return

    # Leggi i messaggi dal file JSON
    with open(MESSAGES_FILE, 'r') as f:
        data = json.load(f)

    today = datetime.now().strftime('%Y-%m-%d')
    if today not in data or not data[today]:
        await update.message.reply_text("Non ci sono messaggi da riassumere.")
        return

    # Usa OpenAI per generare un riassunto
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Usa il modello di chat
            messages=[{
                "role":
                "system",
                "content":
                "Sei un assistente che crea riassunti brevi e chiari."
            }, {
                "role":
                "user",
                "content":
                f"Riassumi questa conversazione:\n\n{chr(10).join(data[today])}"
            }],
            max_tokens=100)
        riassunto = response['choices'][0]['message']['content'].strip()
    except Exception as e:
        riassunto = f"Errore: {e}"

    # Invia il riassunto e svuota i messaggi per oggi
    await update.message.reply_text(f"Ecco il riassunto:\n{riassunto}")

    # Svuota i messaggi per oggi
    data[today] = []
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(data, f)


# Funzione per il riassunto giornaliero
async def riassunto_giornaliero(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID:
        return

    # Leggi i messaggi dal file JSON
    with open(MESSAGES_FILE, 'r') as f:
        data = json.load(f)

    today = datetime.now().strftime('%Y-%m-%d')
    if today not in data or not data[today]:
        await context.bot.send_message(CHAT_ID,
                                       "Non ci sono messaggi da riassumere.")
        return

    # Usa OpenAI per generare un riassunto
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Usa il modello di chat
            messages=[{
                "role":
                "system",
                "content":
                "Sei un assistente che crea riassunti brevi e chiari."
            }, {
                "role":
                "user",
                "content":
                f"Riassumi questa conversazione:\n\n{chr(10).join(data[today])}"
            }],
            max_tokens=100)
        riassunto = response['choices'][0]['message']['content'].strip()
    except Exception as e:
        riassunto = f"Errore: {e}"

    # Invia il riassunto giornaliero
    await context.bot.send_message(
        CHAT_ID, f"Ecco il riassunto giornaliero:\n{riassunto}")

    # Svuota i messaggi per oggi
    data[today] = []
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(data, f)


# Funzione principale
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, save_message))
    application.add_handler(CommandHandler("riassumi", riassumi))
    application.add_handler(CommandHandler("getchatid", get_chat_id))

    # Accedi alla coda dei job direttamente dall'oggetto `application`
    application.job_queue.run_daily(
        riassunto_giornaliero,  # La funzione per il riassunto
        riassunto_orario)

    application.run_polling()


if __name__ == "__main__":
    main()
