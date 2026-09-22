import asyncio
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    groq_api_key=GROQ_API_KEY,
    temperature=0.2,
    max_tokens=800,
)

SYSTEM_PROMPT = """Ты — AI-ассистент Motion Web IT Academy.
Твоя задача — отвечать на вопросы о курсах, направлениях обучения и академии.

БАЗА ЗНАНИЙ:
Обучение проводится по следующим направлениям:
1. Жасалма интеллект / Artificial Intelligence (AI) — длительность: 15 месяцев. Стоимость: 15 000 сом в месяц.
2. Full-stack разработка — длительность: 14 месяцев.
3. Киберкоопсуздук / Кибербезопасность (CyberSecurity) — длительность: 12 месяцев.
4. JS (программирование на JavaScript).

ПРАВИЛА ОТВЕТОВ:
1. Если спрашивают "Какие курсы есть?": перечисли направления списком с длительностью и добавь:
"Выбор направления зависит от ваших целей и интересов. Если вас интересуют подробности о конкретном курсе, пожалуйста, уточните, и я постараюсь помочь!"
2. Если спрашивают стоимость курса AI: укажи "Стоимость обучения на курсе «Искусственный интеллект» (AI) составляет 15 000 сом в месяц."
3. Если спрашивают подробную программу или то, чего нет в базе знаний (например, подробности программы Кибербезопасности): ответь строго вежливо:
"К сожалению, у меня нет подробной информации о программе обучения на данном курсе. Чтобы узнать, что именно входит в программу этого направления, пожалуйста, оставьте заявку на нашем сайте или свяжитесь с менеджерами академии — они с радостью предоставят вам все необходимые детали."
4. Отвечай вежливо, форматируй ключевые названия жирным шрифтом (**название**).
"""

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{question}"),
])

ai_chain = chat_prompt | llm

user_history = {}
user_stats = {}

HELP_TEXT = """📚 Команды:

/start — запустить бота
/help — показать команды
/new — начать новый диалог
/history — показать последние сообщения
/clear — очистить историю сообщений
/stats — показать статистику
/about — информация о вас

Или просто задайте вопрос о Motion Web IT Academy."""


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
  user_name = message.from_user.full_name
  user_tag = (
      f"@{message.from_user.username}"
      if message.from_user.username
      else message.from_user.first_name
  )
  text = (
      f"👋 Здравствуйте, {user_name} [ {user_tag} ]!\n\n"
      "Я AI-ассистент Motion Web IT Academy.\n"
      "Отвечаю на вопросы о курсах, направлениях обучения и академии.\n\n"
      f"{HELP_TEXT}"
  )
  await message.answer(text)


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
  await message.answer(HELP_TEXT)


@dp.message(Command("new"))
async def cmd_new(message: types.Message):
  user_id = message.from_user.id
  user_history[user_id] = []
  await message.answer(
      "🔄 Начат новый диалог. Задайте любой вопрос о Motion Web IT Academy!"
  )


@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
  user_id = message.from_user.id
  user_history[user_id] = []
  await message.answer("🗑 История сообщений очищена.")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
  user_id = message.from_user.id
  count = user_stats.get(user_id, 0)
  await message.answer(f"📊 Количество отправленных вами вопросов: {count}")


@dp.message(Command("about"))
async def cmd_about(message: types.Message):
  u = message.from_user
  username_text = f"@{u.username}" if u.username else "не указан"
  text = f"👤 Имя: {u.full_name}\n📛 Username: {username_text}\n🆔 ID: {u.id}"
  await message.answer(text)


@dp.message(Command("history"))
async def cmd_history(message: types.Message):
  user_id = message.from_user.id
  history = user_history.get(user_id, [])
  if not history:
    await message.answer("История сообщений пуста.")
    return

  text = "📑 Последние сообщения:\n\n"
  for item in history[-5:]:  # последние 5 пар сообщений
    text += f"👤 Вы:\n{item['q']}\n\n🤖 Бот:\n{item['a']}\n\n"
  await message.answer(text.strip())


@dp.message(F.text)
async def handle_question(message: types.Message):
  user_id = message.from_user.id
  question = message.text

  user_stats[user_id] = user_stats.get(user_id, 0) + 1

  response = ai_chain.invoke({"question": question})
  answer = response.content if hasattr(response, "content") else str(response)

  if user_id not in user_history:
    user_history[user_id] = []
  user_history[user_id].append({"q": question, "a": answer})

  await message.answer(answer)


async def main():
  print("Бот Motion Web IT Academy запущен...")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())