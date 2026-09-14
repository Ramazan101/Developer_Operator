from lanchain_core.prompt import ChatPromptTempleate
from lanchain_ollama import ChatOllama
import os
from dotenv import load_dotenv
from developeroperator.schemas import TicketOutputSchema
load_dotenv()


ticket_prompt = ChatPromptTempleate.from_messages(
    [
        (
            "system",
            "Ты помогаешь оператору службы доставки разбирать обращения."
            ""
        )
    ]
)

ticket_model = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_URL,
    temperature=0,
    num_predict=250,
)

structured_ticket_model = ticket_model.with_structured_output(
    TicketOutputSchema,
    method="json_schema"
)
ticket_chain = ticket_prompt | structured_ticket_model