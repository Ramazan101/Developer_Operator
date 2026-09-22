import json
import os
import re
from typing import List, Optional
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_groq import ChatGroq

load_dotenv()

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    groq_api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1,
    max_tokens=1500,
)


def extract_json(raw_output):
  text = (
      raw_output.content if hasattr(raw_output, "content") else str(raw_output)
  )
  text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
  match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
  json_str = match.group(0) if match else text
  return json.loads(json_str)


MEETINGS_PROMPT = """Ты — ассистент по анализу рабочих встреч.
Твоя задача — извлечь из текста встречи список конкретных договоренностей и задач.

Правила:
1. Включай ТОЛЬКО принятые решения и задачи. Если идею только обсудили или решили ничего не менять — игнорируй.
2. "title": краткое действие в неопределенной форме глагола (например: "Исправить форму регистрации", "Подготовить макет").
3. "assignee": имя ответственного (если назначен), иначе null.
4. "deadline_text": срок (например: "до пятницы", "сегодня", "до среды"), иначе null.

Верни СТРОГО JSON-массив объектов:
[
  {{
    "title": "название задачи",
    "assignee": "имя или null",
    "deadline_text": "срок или null"
  }}
]

Текст встречи:
{text}
"""

meetings_chain = (
    ChatPromptTemplate.from_messages([
        ("system", MEETINGS_PROMPT),
        ("human", "{text}"),
    ])
    | llm
    | RunnableLambda(extract_json)
)


PLAN_PROMPT = """Ты — проектный менеджер. 
Твоя задача — составить план из ровно {count_tasks} конкретных шагов для достижения цели с учётом ограничений.

Формат ответа СТРОГО JSON:
{{
  "plan_status": "draft",
  "tasks": [
    {{
      "task_number": 1,
      "title": "Краткое название шага",
      "details": "Подробное описание с учетом ограничений",
      "priority": 1,
      "status": "todo"
    }}
  ],
  "tasks_count": {count_tasks}
}}

Цель: {goal}
Ограничения: {constraints}
Количество задач: {count_tasks}
"""

plan_chain = (
    ChatPromptTemplate.from_messages([
        ("system", PLAN_PROMPT),
        ("human", "Цель: {goal}\nОграничения: {constraints}"),
    ])
    | llm
    | RunnableLambda(extract_json)
)


def analyze_meeting(text: str) -> list:
  return meetings_chain.invoke({"text": text})


def create_plan(goal: str, constraints: str, count_tasks: int) -> dict:
  return plan_chain.invoke({
      "goal": goal,
      "constraints": constraints,
      "count_tasks": count_tasks,
  })