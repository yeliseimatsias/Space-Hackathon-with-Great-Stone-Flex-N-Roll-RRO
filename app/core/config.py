from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    TELEGRAM_BOT_TOKEN: str
    BASE_URL: str
    BITRIX_WEBHOOK_URL: str
    DATABASE_URL: str
    EMBEDDING_MODEL_NAME: str = "paraphrase-multilingual-MiniLM-L12-v2"
    KNOWLEDGE_THRESHOLD: float = 0.75
    LLM_API_KEY: str
    # Gemini 1.5 сняты с API (404). Актуальные: gemini-2.5-flash, gemini-2.5-flash-lite.
    LLM_MODEL: str = "gemini-2.5-flash"
    LOG_LEVEL: str = "INFO"
    # Все задачи на этого USER_ID Bitrix, если задан (см. BITRIX_PRIMARY_USER_ID_SALES_ONLY).
    PRIMARY_BITRIX_USER_ID: int | None = None
    # Если True — PRIMARY_BITRIX_USER_ID подменяет эксперта только для sales; иначе на все роли.
    BITRIX_PRIMARY_USER_ID_SALES_ONLY: bool = True
    # Если задан — все im-уведомления только ему (режим «один диспетчер»). Если None — уведомление тому, кому ушла задача.
    BITRIX_IM_OPERATOR_USER_ID: int | None = None
    BITRIX_SEND_CLIENT_MESSAGES_TO_IM: bool = True
    BITRIX_CREATE_TASK_ON_ROUTING: bool = True
    # Секрет для POST /webhook/bitrix/reply и формы GET /operator/reply.
    BITRIX_REPLY_WEBHOOK_SECRET: str = ""


settings = Settings()
