import os

from dotenv import load_dotenv

load_dotenv()


class CONFIG:
    WORK_DIR: str = os.getenv("WORK_DIR", "/app/data")
    DEBUG: bool = True if str(os.getenv("DEBUG", "False")).lower() == "true" else False
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "debug")
    DEPLOYMENT_LEVEL: str = os.getenv("DEPLOYMENT_LEVEL", "dev")

    # DB CONFIGURATION
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sqlite3.db")

    # SOLANA RPC URL
    SOLANA_RPC_URL: str = os.getenv(
        "SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"
    )

    # WALLET ENCRYPTION
    WALLET_ENCRYPTION_SALT: str = os.getenv(
        "WALLET_ENCRYPTION_SALT", "random_salt_value"
    )

    # PRO MEMBERSHIP CONFIGURATION
    PRO_MEMBERSHIP_WALLET: str = os.getenv(
        "PRO_MEMBERSHIP_WALLET", "CsTmcGZ5UMRzM2DmWLjayc2sTK2zumwfS4E8yyCFtK51"
    )
    PRO_MEMBERSHIP_TOKEN: str = os.getenv(
        "PRO_MEMBERSHIP_TOKEN", "4FkNq8RcCYg4ZGDWh14scJ7ej3m5vMjYTcWoJVkupump"
    )
    PRO_MEMBERSHIP_COST: int = int(os.getenv("PRO_MEMBERSHIP_COST", 22000))
    FREE_USER_DAILY_LIMIT = os.getenv("FREE_USER_DAILY_LIMIT", 10)
    PRO_USER_DAILY_LIMIT = os.getenv("PRO_USER_DAILY_LIMIT", 200)

    ###### AI APIS ######

    # OPENAI API
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # OPENROUTER API
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

    # INFYR API
    INFYR_API_KEY: str = os.getenv("INFYR_API_KEY", "")

    ##### TOOLKIT APIS #####

    # BIRDEYE - Used for pro membership verification, chat wallet evaluation, etc.
    BIRDEYE_API_KEY: str = os.getenv("BIRDEYE_API_KEY", "")

    # COIN MARKET CAP API
    CMC_API_KEY: str = os.getenv("CMC_API_KEY", "")

    # DAPPRADAR API
    DAPPRADAR_API_KEY: str = os.getenv("DAPPRADAR_API_KEY", "")
