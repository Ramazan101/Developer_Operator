import json
import os
import re
from typing import Optional
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

load_dotenv()

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    groq_api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1,
    max_tokens=1000,
)


def extract_json(raw_output):
    text = (
        raw_output.content if hasattr(raw_output, "content") else str(raw_output)
    )

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        json_str = match.group(0)
    else:
        json_str = text

    return json.loads(json_str)


class AnalyzeResult(BaseModel):
    answer: str = Field(description="Краткий и точный ответ на вопрос клиента")
    order_id: Optional[int] = Field(
        default=None,
        description=(
            "Числовой ID заказа, если он упоминается в тексте, иначе null"
        ),
    )
    priority: int = Field(
        description=(
            "Приоритет обращения от 1 до 3: 3 - задержка/жалоба/проблема, 2 -"
            " вопрос по текущему заказу, 1 - общий вопрос"
        )
    )


ANALYZE_PROMPT = """Ты — аналитический модуль службы доставки.
Проанализируй входящее сообщение клиента и верни результат СТРОГО в формате JSON без каких-либо вводных слов и тегов.

Требуемые поля JSON:
- "answer": (строка) краткий ответ на вопрос клиента.
  * График работы курьерской службы: ежедневно с 09:00 до 23:00.
  * Если жалоба на задержку: "Мы уточняем информацию о местоположении курьера."
- "order_id": (число или null) номер заказа из текста (например, 15), если есть, иначе null.
- "priority": (число от 1 до 3) 3 - жалоба/задержка, 2 - вопрос по существующему заказу, 1 - справочный вопрос.

Пример ответа:
{{"answer": "Курьер работает ежедневно с 09:00 до 23:00.", "order_id": null, "priority": 1}}

Сообщение клиента:
{text}
"""

analyze_prompt_template = ChatPromptTemplate.from_messages([
    ("system", ANALYZE_PROMPT),
    ("human", "{text}"),
])

analyze_chain = analyze_prompt_template | llm | RunnableLambda(extract_json)


class AnswerResult(BaseModel):
    text_draft: str = Field(
        description="Вежливый проект ответа службы поддержки клиенту"
    )
    review: bool = Field(
        description="Флаг: true, если ответ требует проверки человеком, иначе false"
    )


ANSWER_PROMPT = """Ты — вежливый оператор службы поддержки доставки. 
Составь проект ответа клиенту (text_draft) и определи, нужна ли проверка человеком (review).
Ответ верни СТРОГО в формате JSON без тегов и лишнего текста.

Требуемые поля JSON:
- "text_draft": (строка) вежливый ответ клиенту. При задержке извинись, укажи, что курьер в пути, ситуация под контролем.
- "review": (boolean true/false) true, если жалоба/задержка/проблема или недостаточно фактов; false, если простой справочный вопрос.

Пример ответа:
{{"text_draft": "Прошу прощения за задержку...", "review": true}}

Факты:
{facts}

Сообщение клиента:
{text}
"""

answer_prompt_template = ChatPromptTemplate.from_messages([
    ("system", ANSWER_PROMPT),
    ("human", "Текст клиента: {text}\nФакты: {facts}"),
])

answer_chain = answer_prompt_template | llm | RunnableLambda(extract_json)

ORDER_CREATE_PROMPT = """Ты — AI-ассистент службы доставки DeliveryOperator.
Твоя задача — извлечь из текста пользователя список заказываемых товаров и вернуть результат СТРОГО в формате JSON.

Правила извлечения:
1. "title": название товара в единственном числе и начальной форме (например: "кофта", "кроссовки", "мышь", "пицца").
2. "category": общая категория товара (например: "Одежда", "Обувь", "Компьютерные аксессуары", "Продукты", "Электроника").
3. "store": название магазина/ресторана, если клиент указал его в тексте, иначе null.
4. "description": характеристики товара (цвет, размер, модель, тип и т.д.) в формате "Цвет: синий; размер: L". Если характеристик нет, укажи null.
5. "quantity": количество товара целым числом (по умолчанию 1).
6. "price": цена за штуку (число), если клиент указал цену в тексте, иначе null.
7. "total_price": общая стоимость (price * quantity), если цена известна, иначе null.

Формат ответа СТРОГО:
{{
  "items": [
    {{
      "title": "кофта",
      "category": "Одежда",
      "store": null,
      "description": "Цвет: синий; размер: L",
      "quantity": 2,
      "price": null,
      "total_price": null
    }}
  ]
}}

Текст пользователя:
{text}
"""

order_create_prompt_template = ChatPromptTemplate.from_messages([
    ("system", ORDER_CREATE_PROMPT),
    ("human", "{text}"),
])

order_create_chain = (
        order_create_prompt_template | llm | RunnableLambda(extract_json)
)


def parse_order_create(text: str) -> dict:
    return order_create_chain.invoke({"text": text})


def analyze_ticket(text: str) -> dict:
    return analyze_chain.invoke({"text": text})


def answer_ticket(text: str, facts: str = "") -> dict:
    return answer_chain.invoke({"text": text, "facts": facts or "Нет фактов"})
