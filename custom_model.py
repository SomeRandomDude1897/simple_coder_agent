from typing import Any, List, Optional, Mapping
from langchain_core.language_models.llms import BaseLLM
from langchain_core.callbacks import CallbackManagerForLLMRun
from pydantic.v1 import Field, PrivateAttr
from langchain_core.outputs import LLMResult, Generation
from dotenv import load_dotenv
from openai import OpenAI
import os
import tiktoken
import json
import requests
import re

load_dotenv()
import json
import re


import json, re


def sanitize_llm_output(raw_output: str) -> dict:
    # Убираем code fences
    cleaned = re.sub(r"```.*?```", "", raw_output, flags=re.DOTALL).strip()
    # Меняем одинарные кавычки ключей на двойные
    cleaned = re.sub(r"(\w+):", r'"\1":', cleaned)
    # Пробуем распарсить JSON
    obj = json.loads(cleaned)
    # Экранируем внутренние двойные кавычки в Action Input
    if "Action Input" in obj:
        action_input = obj["Action Input"]
        action_input = action_input.replace(
            '"', "'"
        )  # двойные кавычки -> одинарные внутри команды
        obj["Action Input"] = action_input
    return obj


class CustomCloudLLM(BaseLLM):
    """
    Кастомная LLM для работы с новым API foundation-models.api.cloud.ru
    через OpenAI-совместимый клиент.
    """

    # Параметры модели
    api_key: str = os.getenv("PROXY_BASE_TOKEN")
    base_url: str = os.getenv("PROXY_BASE_URL")
    model: str = Field("gpt-5", description="Имя модели")
    temperature: float = Field(0.7, description="Температура генерации")
    prompt: str = Field("", description="Системный промпт")
    times_used: int = Field(0, description="Количество обращений к LLM")
    tokens_used: int = Field(0, description="Количество использованных токенов")
    _cloud_client = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cloud_client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def _llm_type(self) -> str:
        return "custom_cloud_llm"

    def change_prompt(self, new_prompt):
        self.prompt = new_prompt

    def get_tokens(self):
        return self.tokens_used

    def get_times_used(self):
        return self.times_used

    def _generate(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Основной метод для выполнения запроса"""

        try:
            response = self._cloud_client.chat.completions.create(
                model=self.model,
                presence_penalty=0,
                messages=[
                    {"role": "system", "content": self.prompt},
                    {"role": "user", "content": prompt[0]},
                ],
            )
            self.tokens_used += int(response.usage.total_tokens)
            self.times_used += 1

        except Exception as e:
            print(f"Ошибка API: {e}")
            if "Please reduce the length of the input messages" in str(e):
                return self._generate(
                    prompt=(
                        self.memory[:-1]
                        if hasattr(self, "memory")
                        else []
                        + "The observation is too large to handle for the LLM, please specify or change your request"
                    )
                )
            else:
                return LLMResult(generations=[[Generation(text="error")]])

        if not response or not response.choices:
            raise LLMResult(generations=[[Generation(text="error")]])

        clean_output = response.choices[0].message.content
        print("_______")
        print(clean_output)
        print("_______")
        llm_result = LLMResult(generations=[[Generation(text=str(clean_output))]])
        return llm_result

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "base_url": self.base_url,
        }
