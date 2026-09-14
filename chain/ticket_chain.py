import os
from typing import Optional

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from openai import BaseModel
from pydantic import Field

load_dotenv()
# GROQ_MODEL = os.getenv("GROQ_MODEL")
llm = ChatGroq(
    model="qwen/qwen3.6-27b",
    groq_api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1,
    max_tokens=1000
)


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


analyze_parser = JsonOutputParser(pydantic_object=AnalyzeResult)

ANALYZE_PROMPT = """Ты — аналитический модуль службы доставки. Твоя задача — проанализировать сообщение клиента и вернуть результат строго в формате JSON.

Инструкции:
1. "order_id": найди номер заказа в тексте (например "заказ 15", "№15", "order #15") и верни его как число. Если номера заказа нет, верни null.
2. "priority": определи важность сообщения от 1 до 3:
   - 3: Высокий приоритет (жалоба, задержка заказа, недовольство, "где курьер?").
   - 2: Средний приоритет (вопрос по существующему заказу, смена адреса).
   - 1: Низкий приоритет (общие справочные вопросы, например: "до скольки вы работаете?").
3. "answer": сформируй краткий ответ на вопрос клиента.
   - График работы курьерской службы: ежедневно с 09:00 до 23:00.
   - Если клиент жалуется на задержку заказа, напиши: "Мы уточняем информацию о местоположении курьера".

{format_instructions}

Текст клиента:
{text}
"""

analyze_prompt_template = ChatPromptTemplate.from_messages([
    ("system", ANALYZE_PROMPT),
    ("human", "{text}"),
]).partial(format_instructions=analyze_parser.get_format_instructions())

analyze_chain = analyze_prompt_template | llm | analyze_parser


class AnswerResult(BaseModel):
    text_draft: str = Field(
        description="Вежливый проект ответа службы поддержки клиенту"
    )
    review: bool = Field(
        description="Флаг: true, если ответ требует проверки человеком, иначе false"
    )


answer_parser = JsonOutputParser(pydantic_object=AnswerResult)

ANSWER_PROMPT = """Ты — вежливый оператор службы поддержки доставки. 
Твоя задача — составить черновик ответа клиенту (text_draft) и определить, требуется ли проверка ответа супервайзером/человеком (review).

Правила формирования "text_draft":
1. Всегда обращайся вежливо и профессионально.
2. Если клиент жалуется на задержку заказа:
   - Извинись за доставленные неудобства.
   - Укажи, что курьер уже находится в пути, но задержка могла произойти из-за дорожных условий или высокой нагрузки.
   - Заверь, что ситуация контролируется, и мы скоро предоставим обновлённую информацию.
3. Учитывай переданные факты (facts), если они предоставлены.

Правила для "review":
- Установи true, если есть жалоба, конфликт, долгая задержка заказа или если в поле "facts" недостаточно информации для окончательного решения.
- Установи false только для простых типовых благодарностей или простых справочных вопросов.

{format_instructions}

Факты по ситуации:
{facts}

Сообщение клиента:
{text}
"""

answer_prompt_template = ChatPromptTemplate.from_messages([
    ("system", ANSWER_PROMPT),
    ("human", "Текст клиента: {text}\nФакты: {facts}"),
]).partial(format_instructions=answer_parser.get_format_instructions())

answer_chain = answer_prompt_template | llm | answer_parser


def analyze_ticket(text: str):
    return analyze_chain.invoke({"text": text})


def answer_ticket(text: str, facts: str = ""):
    return answer_chain.invoke({"text": text, "facts": facts or "Нет фактов"})
