import io
import json
import random
import string
import sys
import traceback
from datetime import datetime, timedelta
from typing import Any, AsyncIterable, Dict, List, Optional
import aiohttp

import tiktoken
from fastapi.responses import StreamingResponse
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.callbacks.base import BaseCallbackHandler
from langchain.globals import set_debug, set_verbose
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from api.users.controllers import check_user_pro_status, verify_signature
from models.requests import Requests
from models.users import User
from settings.config import CONFIG
from settings.logger import logger
from tools import (BirdeyeAllTimeTradesTool, BirdeyeTokenTrendingTool,
                   CMCCryptoNewsTool, CMCTrendingCoinsTool,
                   CNMemecoinsNewsTool, CoinGeckoCoinDataTool,
                   CoinGeckoExchangeRatesTool, CoinGeckoGlobalCryptoDataTool,
                   CoinGeckoTrendingTool, DappRadarGameTrackerTool,
                   DexScreenerTokenInformationTool, DexScreenerTopBoostsTool,
                   FluxBeamTokenPriceTool, GTPumpFunTrendingTool, JupiterSwapTool,
                   JupiterTokenInformationTool, JupiterTokenPriceTool,
                   PumpFunLaunchCoinTool, RugcheckTokenInformationTool,
                   SolanaBurnTokenTool, SolanaSendSolTool,
                   SolanaSendSplTokensTool, TokenIdentificationTool,
                   WalletPortfolioTool, get_tools_system_message)

from .schema import (AllowedModelName, ChatRequest, ConversationSummary,
                     GetConversationRequest, LastConversationsRequest,
                     MessageResponse)

###############################################
##### CHAT CONTROLLER #####
###############################################


def generate_conversation_key(length=10):
    """Generate a random alphanumeric string of specified length"""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


class DebugCaptureCallbackHandler(BaseCallbackHandler):
    """Callback handler to capture debug output in memory for storage in database"""

    def __init__(self, request_id, db):
        """Initialize with request ID and database session"""
        self.request_id = request_id
        self.db = db
        self.generated_text = ""
        self.debug_buffer = io.StringIO()
        self.original_stdout = sys.stdout

    def __enter__(self):
        """Capture stdout when entering context"""
        sys.stdout = self.debug_buffer
        # Enable debug mode to capture all events
        set_debug(True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore stdout when exiting context"""
        sys.stdout = self.original_stdout
        # Disable debug mode
        set_debug(False)

        # Save the captured debug output to database
        try:
            request = (
                self.db.query(Requests).filter(Requests.id == self.request_id).first()
            )
            if request:
                request.verbose = self.debug_buffer.getvalue()
                self.db.commit()
                logger.info(
                    f"[LUMOKIT] Stored debug output for request {self.request_id}"
                )
        except Exception as e:
            logger.error(f"[LUMOKIT] Failed to save debug output: {str(e)}")
            logger.error(traceback.format_exc())

    def on_llm_new_token(self, token, **kwargs):
        """Process a new token from the LLM."""
        self.generated_text += token
        return token


class StreamingCallback(BaseCallbackHandler):
    """Callback handler that streams tokens to the client and updates the database"""

    def __init__(self, request_id, db):
        self.request_id = request_id
        self.db = db
        self.generated_text = ""
        self.token_buffer = []  # Buffer to collect tokens for client
        self.last_db_update = 0  # Track last database update

    def on_llm_start(self, serialized, prompts, **kwargs):
        """Called when LLM starts generating."""
        logger.info(f"[LUMOKIT] Starting LLM generation for request {self.request_id}")

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Process tokens as they come in from the LLM."""
        # Append token to accumulated text
        self.generated_text += token

        # Add token to buffer to be returned to client
        self.token_buffer.append(token)

        # Update database periodically (every 50 characters)
        if len(self.generated_text) - self.last_db_update >= 50:
            try:
                request = (
                    self.db.query(Requests)
                    .filter(Requests.id == self.request_id)
                    .first()
                )
                if request:
                    request.response = self.generated_text
                    self.db.commit()
                    self.last_db_update = len(self.generated_text)
            except Exception as e:
                # Just log the error but don't interrupt token generation
                logger.error(f"[LUMOKIT] Error in periodic update: {str(e)}")

    def on_llm_end(self, response, **kwargs):
        """Called when LLM ends streaming."""
        try:
            logger.info(
                f"[LUMOKIT] LLM finished generating response for request {self.request_id}, text length: {len(self.generated_text)}"
            )

            # Update the database with the final text
            request = (
                self.db.query(Requests).filter(Requests.id == self.request_id).first()
            )
            if request:
                request.response = self.generated_text
                request.success = True
                self.db.commit()
                logger.info(
                    f"[LUMOKIT] Successfully stored response in database, length: {len(self.generated_text)}"
                )
            else:
                logger.error(
                    f"[LUMOKIT] Request {self.request_id} not found when trying to update response"
                )
        except Exception as e:
            logger.error(f"[LUMOKIT] Error updating chat request in database: {str(e)}")
            logger.error(traceback.format_exc())
            self.db.rollback()

    def on_llm_error(self, error, **kwargs):
        """Called when LLM errors."""
        try:
            logger.error(
                f"[LUMOKIT] LLM generation error for request {self.request_id}: {str(error)}"
            )
            request = (
                self.db.query(Requests).filter(Requests.id == self.request_id).first()
            )
            if request:
                request.success = False
                request.response = f"Error: {str(error)}"
                self.db.commit()
                logger.error(
                    f"[LUMOKIT] Chat request {self.request_id} failed: {str(error)}"
                )
        except Exception as e:
            logger.error(f"[LUMOKIT] Error updating chat request with error: {str(e)}")
            self.db.rollback()


def count_tokens(messages, model="gpt-4"):
    """Count the number of tokens in a message or list of messages"""
    try:
        # Always use cl100k_base encoding which works for all OpenAI models
        encoding = tiktoken.get_encoding("cl100k_base")

        if isinstance(messages, str):
            return len(encoding.encode(messages))

        if isinstance(messages, list):
            # For a list of messages, count each message
            total = 0
            for message in messages:
                if isinstance(message, str):
                    total += len(encoding.encode(message))
                elif hasattr(message, "content"):
                    total += len(encoding.encode(message.content))
            return total

        # For LangChain message objects
        if hasattr(messages, "content"):
            return len(encoding.encode(messages.content))

        return 0
    except Exception as e:
        logger.error(f"[LUMOKIT] Error counting tokens: {str(e)}")
        return 0


async def process_chat_request(chat_request: ChatRequest, db: Session):
    """
    Process a chat request:
    1. Verify signature
    2. Handle conversation key (create new or validate existing)
    3. Store request in database
    4. Process with LangChain and ChatGPT
    5. Stream response
    """
    try:
        # Verify signature
        is_valid = await verify_signature(
            chat_request.public_key, chat_request.signature
        )
        if not is_valid:
            logger.error(
                f"[LUMOKIT] Chat authentication failed: Invalid signature for {chat_request.public_key}"
            )
            return StreamingResponse(
                iter(
                    [
                        json.dumps(
                            {
                                "error": "Authentication failed, please relogin and try again."
                            }
                        )
                    ]
                ),
                media_type="application/json",
            )

        # Check user request limits
        user_pro_status = await check_user_pro_status(
            {"public_key": chat_request.public_key}, db
        )
        is_pro_user = user_pro_status.get("is_pro", False)

        # Log the pro status for debugging
        logger.info(
            f"[LUMOKIT] User {chat_request.public_key} pro status: {is_pro_user}"
        )

        # Validate model selection - free users can only use gpt-4.1-mini and lumo models
        if (
            not is_pro_user
            and chat_request.model_name
            and chat_request.model_name != "gpt-4.1-mini"
            and not chat_request.model_name.startswith("lumo-")
        ):
            logger.warning(
                f"[LUMOKIT] Free user {chat_request.public_key} attempted to use model {chat_request.model_name}"
            )
            return StreamingResponse(
                iter(
                    [
                        json.dumps(
                            {
                                "error": "Free users can only use the default gpt-4.1-mini model or Lumo models. Upgrade to Pro for access to additional models."
                            }
                        )
                    ]
                ),
                media_type="application/json",
            )

        # Get daily limits from environment variables, with fallbacks
        # Convert limits to integers to prevent type errors
        free_user_daily_limit = int(getattr(CONFIG, "FREE_USER_DAILY_LIMIT", 10))
        pro_user_daily_limit = int(getattr(CONFIG, "PRO_USER_DAILY_LIMIT", 200))

        # Calculate the start of the current day (UTC)
        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Count today's requests for this user
        today_request_count = (
            db.query(Requests)
            .filter(
                Requests.pubkey == chat_request.public_key, Requests.time >= today_start
            )
            .count()
        )

        # Check if user has exceeded their daily limit
        if is_pro_user and today_request_count >= pro_user_daily_limit:
            logger.warning(
                f"[LUMOKIT] Pro user {chat_request.public_key} has reached daily limit of {pro_user_daily_limit} requests"
            )
            return StreamingResponse(
                iter(
                    [
                        json.dumps(
                            {
                                "error": "You've hit today's message limit. It will reset automatically tomorrow."
                            }
                        )
                    ]
                ),
                media_type="application/json",
            )
        elif not is_pro_user and today_request_count >= free_user_daily_limit:
            logger.warning(
                f"[LUMOKIT] Free user {chat_request.public_key} has reached daily limit of {free_user_daily_limit} requests"
            )
            return StreamingResponse(
                iter(
                    [
                        json.dumps(
                            {
                                "error": "You've reached today's message limit. Upgrade to Pro for more access."
                            }
                        )
                    ]
                ),
                media_type="application/json",
            )

        logger.info(
            f"[LUMOKIT] User {chat_request.public_key} has used {today_request_count + 1}/{pro_user_daily_limit if is_pro_user else free_user_daily_limit} requests today"
        )

        # Handle conversation key
        conversation_key = chat_request.conversation_key
        if not conversation_key:
            # Generate new conversation key
            conversation_key = generate_conversation_key()
            logger.info(f"[LUMOKIT] Generated new conversation key: {conversation_key}")
        else:
            # Verify conversation key exists for this user
            existing_convo = (
                db.query(Requests)
                .filter(
                    Requests.pubkey == chat_request.public_key,
                    Requests.conversation_key == conversation_key,
                )
                .first()
            )

            if not existing_convo:
                logger.warning(
                    f"[LUMOKIT] Conversation key {conversation_key} not found for user {chat_request.public_key}"
                )
                # Generate a new key since the provided one doesn't exist
                conversation_key = generate_conversation_key()
                logger.info(
                    f"[LUMOKIT] Generated replacement conversation key: {conversation_key}"
                )

        # Get the model name from the request, use the default if not provided
        model_name = chat_request.model_name or "gpt-4.1-mini"

        # Validate temperature
        temperature = chat_request.temperature
        if temperature is None:
            temperature = 0.7
        else:
            # Ensure temperature is within valid range (0.0 to 1.0)
            if temperature < 0.0 or temperature > 1.0:
                logger.warning(
                    f"[LUMOKIT] Invalid temperature value {temperature} for user {chat_request.public_key}. Using default 0.7"
                )
                temperature = 0.7

        # Store all input parameters except agent_public and agent_private
        input_params = {
            "public_key": chat_request.public_key,
            "conversation_key": conversation_key,
            "message": chat_request.message,
            "model_name": model_name,
            "temperature": temperature,
            "tools": chat_request.tools,
        }

        # Create a new request entry
        chat_db_request = Requests(
            pubkey=chat_request.public_key,
            conversation_key=conversation_key,
            input_params=input_params,
            message=chat_request.message,
            success=False,
            response=None,
            verbose=None,
        )

        db.add(chat_db_request)
        db.commit()
        db.refresh(chat_db_request)
        request_id = chat_db_request.id

        logger.info(
            f"[LUMOKIT] Created chat request {request_id} for conversation {conversation_key} using model {model_name}, temperature {temperature}"
        )

        # Set up streaming handler
        stream_handler = StreamingCallback(request_id, db)

        # Begin async streaming response
        async def stream_response():
            # First yield the conversation key so the client knows it
            yield json.dumps({"conversation_key": conversation_key}) + "\n"

            # Use a context manager to capture debug output
            with DebugCaptureCallbackHandler(request_id, db) as debug_handler:
                # Get only the 4 most recent conversation history items
                conversation_history = (
                    db.query(Requests)
                    .filter(
                        Requests.pubkey == chat_request.public_key,
                        Requests.conversation_key == conversation_key,
                    )
                    .order_by(Requests.time.desc())
                    .limit(5)
                    .all()
                )  # Fetch 5 to get the 4 most recent + current

                # Reverse to get chronological order
                conversation_history = conversation_history[::-1]

                try:
                    # Set up the agent with tools
                    wallet_portfolio_tool = WalletPortfolioTool()
                    token_identification_tool = TokenIdentificationTool()
                    rugcheck_token_information_tool = RugcheckTokenInformationTool()
                    fluxbeam_token_price_tool = FluxBeamTokenPriceTool()
                    jupiter_token_price_tool = JupiterTokenPriceTool()
                    jupiter_token_information_tool = JupiterTokenInformationTool()
                    jupiter_swap_tool = JupiterSwapTool()
                    dexscreener_top_boosts_tool = DexScreenerTopBoostsTool()
                    dexscreener_token_information_tool = (
                        DexScreenerTokenInformationTool()
                    )
                    birdeye_token_trending_tool = BirdeyeTokenTrendingTool()
                    birdeye_all_time_trades_tool = BirdeyeAllTimeTradesTool()
                    cmc_crypto_news_tool = CMCCryptoNewsTool()
                    cmc_trending_coins_tool = CMCTrendingCoinsTool()
                    cn_memecoins_news_tool = CNMemecoinsNewsTool()
                    geckoterminal_trending_pumpfun_tool = GTPumpFunTrendingTool()
                    coingecko_global_crypto_data_tool = CoinGeckoGlobalCryptoDataTool()
                    coingecko_trending_tool = CoinGeckoTrendingTool()
                    coingecko_exchange_rates_tool = CoinGeckoExchangeRatesTool()
                    coingecko_coin_data_tool = CoinGeckoCoinDataTool()
                    solana_send_sol_tool = SolanaSendSolTool()
                    solana_send_spl_tokens_tool = SolanaSendSplTokensTool()
                    solana_burn_token_tool = SolanaBurnTokenTool()
                    pumpfun_launch_coin_tool = PumpFunLaunchCoinTool()
                    dappradar_game_tracker_tool = DappRadarGameTrackerTool()
                    
                    # Default tools that are always included
                    tools = [wallet_portfolio_tool, token_identification_tool]

                    # Process requested additional tools
                    available_tools = {
                        "rugcheck_token_information_tool": rugcheck_token_information_tool,
                        "fluxbeam_token_price_tool": fluxbeam_token_price_tool,
                        "jupiter_token_price_tool": jupiter_token_price_tool,
                        "jupiter_token_information_tool": jupiter_token_information_tool,
                        "jupiter_swap_tool": jupiter_swap_tool,
                        "dexscreener_top_boosts_tool": dexscreener_top_boosts_tool,
                        "dexscreener_token_information_tool": dexscreener_token_information_tool,
                        "birdeye_token_trending_tool": birdeye_token_trending_tool,
                        "birdeye_all_time_trades_tool": birdeye_all_time_trades_tool,
                        "cmc_crypto_news_tool": cmc_crypto_news_tool,
                        "cmc_trending_coins_tool": cmc_trending_coins_tool,
                        "cn_memecoins_news_tool": cn_memecoins_news_tool,
                        "geckoterminal_trending_pumpfun_tool": geckoterminal_trending_pumpfun_tool,
                        "coingecko_global_crypto_data_tool": coingecko_global_crypto_data_tool,
                        "coingecko_trending_tool": coingecko_trending_tool,
                        "coingecko_exchange_rates_tool": coingecko_exchange_rates_tool,
                        "coingecko_coin_data_tool": coingecko_coin_data_tool,
                        "solana_send_sol_tool": solana_send_sol_tool,
                        "solana_send_spl_tokens_tool": solana_send_spl_tokens_tool,
                        "solana_burn_token_tool": solana_burn_token_tool,
                        "pumpfun_launch_coin_tool": pumpfun_launch_coin_tool,
                        "dappradar_game_tracker_tool": dappradar_game_tracker_tool
                    }

                    requested_tools = [
                        tool for tool in chat_request.tools if tool in available_tools
                    ]

                    # For free users, enforce the limit of one additional tool
                    if not is_pro_user and len(requested_tools) > 1:
                        logger.warning(
                            f"[LUMOKIT] Free user {chat_request.public_key} requested {len(requested_tools)} additional tools, which exceeds the limit"
                        )
                        error_message = {
                            "error": "Free users can only use one additional tool beyond the defaults. Upgrade to Pro for access to more tools."
                        }
                        yield json.dumps(error_message)

                        # Update request with error
                        request = (
                            db.query(Requests).filter(Requests.id == request_id).first()
                        )
                        if request:
                            request.success = False
                            request.response = json.dumps(error_message)
                            db.commit()
                        return

                    # Log the selected tools
                    logger.info(
                        f"[LUMOKIT] User {chat_request.public_key} selected additional tools: {requested_tools}"
                    )

                    # Add the selected tools to the tools list
                    for tool_name in requested_tools:
                        if tool_name in available_tools:
                            tool_instance = available_tools[tool_name]
                            if tool_instance not in tools:  # Avoid duplicates
                                tools.append(tool_instance)

                    # Get the dynamic tool descriptions based on the tools list
                    tools_descriptions = get_tools_system_message(tools)

                    # Construct the system message
                    base_system_message = "You are LumoKit, a helpful AI assistant specialized in Solana actions and queries."

                    # Add wallet information to system message if both agent_public and agent_private are available
                    if (
                        hasattr(chat_request, "agent_public")
                        and chat_request.agent_public
                        and hasattr(chat_request, "agent_private")
                        and chat_request.agent_private
                    ):
                        wallet_info = f"""
                        For any agentic execution, only when required you must use the following information:
                        AGENT WALLET PUBLIC KEY:
                        {chat_request.agent_public}

                        AGENT WALLET ENCRYPTED PRIVATE KEY:
                        {chat_request.agent_private}

                        If you're providing information, always try to provide it in an organised manner, 
                        Use markdown formatting and tables. Use headings judiciously, bullet points, and other formatting to make the information clear and easy to read.
                        """
                        system_message = (
                            base_system_message
                            + wallet_info
                            + "\n\n"
                            + tools_descriptions
                        )
                    else:
                        # Add wallet connection message based on missing parameters
                        missing_wallet_info = ""
                        if (
                            not hasattr(chat_request, "agent_public")
                            or not chat_request.agent_public
                        ):
                            missing_wallet_info += (
                                "The user must first connect an agent wallet.\n"
                            )
                        if (
                            not hasattr(chat_request, "agent_private")
                            or not chat_request.agent_private
                        ):
                            missing_wallet_info += (
                                "The user must first connect an agent wallet.\n"
                            )

                        system_message = (
                            base_system_message
                            + missing_wallet_info
                            + "\n\n"
                            + tools_descriptions
                        )

                    # Initialize LangChain ChatOpenAI with the specified model and temperature
                    if "gpt" in model_name.lower():
                        # For OpenAI GPT models, use the default setup
                        logger.info(
                            f"[LUMOKIT] Using OpenAI direct endpoint for model {model_name}"
                        )
                        chat = ChatOpenAI(
                            model_name=model_name,
                            temperature=temperature,
                            streaming=True,
                            callbacks=[stream_handler],
                        )
                    elif model_name.startswith("lumo-"):
                        # For Lumo models, use Infyr API endpoint (OpenAI compatible)
                        logger.info(
                            f"[LUMOKIT] Using Infyr endpoint for Lumo model {model_name}"
                        )
                        chat = ChatOpenAI(
                            model_name=model_name,
                            temperature=temperature,
                            streaming=True,
                            callbacks=[stream_handler],
                            max_tokens=4096,
                            base_url="https://api.infyr.ai/v1",
                            api_key=CONFIG.INFYR_API_KEY,
                        )
                        # Override tools to be empty for Lumo models
                        tools = []
                        logger.info(f"[LUMOKIT] Disabled all tools for Lumo model {model_name}")
                    else:
                        # For non-GPT models (like Anthropic Claude), use OpenRouter
                        logger.info(
                            f"[LUMOKIT] Using OpenRouter endpoint for model {model_name}"
                        )

                        chat = ChatOpenAI(
                            model_name=model_name,
                            temperature=temperature,
                            streaming=True,
                            callbacks=[stream_handler],
                            base_url="https://openrouter.ai/api/v1",
                            api_key=CONFIG.OPENROUTER_API_KEY,
                        )

                    # Create the prompt template for the agent
                    # For Lumo models, use simpler prompt without tools
                    if model_name.startswith("lumo-"):
                        prompt = ChatPromptTemplate.from_messages(
                            [
                                ("system", base_system_message),
                                MessagesPlaceholder(variable_name="chat_history"),
                                ("human", "{input}"),
                            ]
                        )
                        
                        # For Lumo models, directly use the chat model without agent
                        # Build message history for direct chat
                        chat_history = []
                        
                        # Add previous messages from conversation history
                        for prev_req in conversation_history[:-1]:
                            if prev_req.message:
                                chat_history.append(HumanMessage(content=prev_req.message))
                            if prev_req.response:
                                chat_history.append(AIMessage(content=prev_req.response))
                        
                        # Count input tokens
                        input_token_count = count_tokens(base_system_message, model=model_name)
                        input_token_count += count_tokens(
                            [msg.content for msg in chat_history], model=model_name
                        )
                        input_token_count += count_tokens(
                            chat_request.message, model=model_name
                        )
                        
                        # Build messages for the chat model
                        messages = [SystemMessage(content=base_system_message)]
                        messages.extend(chat_history)
                        messages.append(HumanMessage(content=chat_request.message))
                        
                        # Stream response directly from chat model
                        full_response_text = ""
                        async for chunk in chat.astream(messages):
                            if chunk.content:
                                full_response_text += chunk.content
                                yield chunk.content
                        
                    else:
                        prompt = ChatPromptTemplate.from_messages(
                            [
                                ("system", system_message),
                                MessagesPlaceholder(variable_name="chat_history"),
                                ("human", "{input}"),
                                MessagesPlaceholder(variable_name="agent_scratchpad"),
                            ]
                        )

                        # Create the agent
                        agent = create_openai_tools_agent(chat, tools, prompt)
                        agent_executor = AgentExecutor(
                            agent=agent,
                            tools=tools,
                            verbose=True,
                            handle_parsing_errors=True,
                        )

                        # Build message history
                        chat_history = []

                        # Add previous messages from conversation history (if any)
                        # Only include the two most recent exchanges
                        for prev_req in conversation_history[
                            :-1
                        ]:  # Exclude the current request
                            if prev_req.message:
                                chat_history.append(HumanMessage(content=prev_req.message))
                            if prev_req.response:
                                chat_history.append(AIMessage(content=prev_req.response))

                        # Full response accumulation
                        full_response_text = ""

                        # Count input tokens
                        input_token_count = count_tokens(system_message, model=model_name)
                        input_token_count += count_tokens(
                            [msg.content for msg in chat_history], model=model_name
                        )
                        input_token_count += count_tokens(
                            chat_request.message, model=model_name
                        )

                        # Process the user input with agent using astream_log for granular token streaming
                        async for log_entry in agent_executor.astream_log(
                            {
                                "input": chat_request.message,
                                "chat_history": chat_history,
                                "agent_public": chat_request.agent_public,  # Ensure this is used by prompt or remove
                            },
                            config={},  # Callbacks are handled by stream_handler on LLM and DebugCaptureCallbackHandler
                        ):
                            for op in log_entry.ops:
                                # Check for tokens streamed from the ChatOpenAI LLM
                                # The path indicates an addition to the streamed output string list
                                if (
                                    op["op"] == "add"
                                    and op["path"].startswith("/logs/ChatOpenAI")
                                    and op["path"].endswith("/streamed_output_str/-")
                                ):
                                    token_chunk = op["value"]
                                    if token_chunk:  # Ensure content is not None or empty
                                        full_response_text += token_chunk
                                        yield token_chunk

                    # The full_response_text is now accumulated from streamed log chunks
                    # agent_output is used for token counting and final DB save.
                    agent_output = full_response_text

                    # Count output tokens
                    output_token_count = count_tokens(
                        full_response_text, model=model_name
                    )
                    total_token_count = input_token_count + output_token_count

                    # Log token counts
                    logger.info(
                        f"[LUMOKIT] Token Count - Request {request_id}: Input: {input_token_count}, Output: {output_token_count}, Total: {total_token_count}"
                    )

                    # Store token counts now but don't commit yet
                    request = (
                        db.query(Requests).filter(Requests.id == request_id).first()
                    )
                    if request:
                        # Store token counts in the database
                        request.input_token_count = input_token_count
                        request.output_token_count = output_token_count
                        request.total_token_count = total_token_count

                    # For Lumo models, manually call the end callback
                    if model_name.startswith("lumo-"):
                        stream_handler.on_llm_end(None)

                    # Streaming to the client is already done by the `yield` in the astream_log loop.
                    # The StreamingCallback.on_llm_end handles its version of the final response.
                    # To ensure the DB has the exact text streamed to client and used for token counts:
                    if request:
                        request.response = full_response_text  # Ensure final DB state matches streamed output
                        request.success = True
                        db.commit()

                except Exception as e:
                    logger.error(f"[LUMOKIT] Error generating chat response: {str(e)}")
                    logger.error(traceback.format_exc())
                    yield json.dumps({"error": str(e)})

                    # Update request with error
                    try:
                        request = (
                            db.query(Requests).filter(Requests.id == request_id).first()
                        )
                        if request:
                            request.success = False
                            request.response = f"Error: {str(e)}"
                            # Also record that token counting failed
                            request.input_token_count = 0
                            request.output_token_count = 0
                            request.total_token_count = 0
                            db.commit()
                    except Exception as db_error:
                        logger.error(
                            f"[LUMOKIT] Error updating database with error: {str(db_error)}"
                        )

        return StreamingResponse(stream_response(), media_type="text/plain")

    except Exception as e:
        logger.error(f"[LUMOKIT] Error in process_chat_request: {str(e)}")
        return StreamingResponse(
            iter([json.dumps({"error": f"Internal server error: {str(e)}"})]),
            media_type="application/json",
        )


async def get_last_conversations(request: LastConversationsRequest, db: Session):
    """
    Retrieves the 5 most recent conversations for a user
    1. Verifies signature for authentication
    2. Queries for most recent conversation keys
    3. For each conversation, includes the latest message with preview
    """
    try:
        # Verify signature
        is_valid = await verify_signature(request.public_key, request.signature)
        if not is_valid:
            logger.error(
                f"[LUMOKIT] Authentication failed when retrieving conversations for {request.public_key}"
            )
            return {
                "success": False,
                "conversations": [],
                "error": "Authentication failed, please relogin and try again.",
            }

        # Query to get the most recent unique conversation keys (up to 5)
        # We use a subquery to get the latest request for each conversation key
        latest_conversations_subq = (
            db.query(
                Requests.conversation_key, func.max(Requests.time).label("latest_time")
            )
            .filter(Requests.pubkey == request.public_key)
            .group_by(Requests.conversation_key)
            .subquery()
        )

        # Join with the main table to get the actual request details
        latest_conversations = (
            db.query(Requests)
            .join(
                latest_conversations_subq,
                (
                    Requests.conversation_key
                    == latest_conversations_subq.c.conversation_key
                )
                & (Requests.time == latest_conversations_subq.c.latest_time),
            )
            .filter(Requests.pubkey == request.public_key)
            .order_by(desc(Requests.time))
            .limit(5)
            .all()
        )

        # Format the results
        result_conversations = []
        for convo in latest_conversations:
            # Create a preview of the user's message
            message_preview = convo.message
            if len(message_preview) > 50:
                message_preview = message_preview[:50] + "..."

            # Add to results
            result_conversations.append(
                ConversationSummary(
                    conversation_key=convo.conversation_key,
                    last_message_preview=message_preview,
                    timestamp=convo.time,
                )
            )

        return {"success": True, "conversations": result_conversations}

    except Exception as e:
        logger.error(f"[LUMOKIT] Error retrieving last conversations: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "conversations": [],
            "error": f"Failed to retrieve conversations: {str(e)}",
        }


async def get_conversation_history(request: GetConversationRequest, db: Session):
    """
    Retrieves the full conversation history for a specific conversation key
    1. Verifies user authentication via signature
    2. Ensures the conversation key belongs to the user
    3. Returns all messages and responses in chronological order
    """
    try:
        # Verify signature for authentication
        is_valid = await verify_signature(request.public_key, request.signature)
        if not is_valid:
            logger.error(
                f"[LUMOKIT] Authentication failed when retrieving conversation {request.conversation_key} for {request.public_key}"
            )
            return {
                "success": False,
                "conversation_key": request.conversation_key,
                "messages": [],
                "error": "Authentication failed, please relogin and try again.",
            }

        # Verify the conversation belongs to this user
        conversation_check = (
            db.query(Requests)
            .filter(
                Requests.pubkey == request.public_key,
                Requests.conversation_key == request.conversation_key,
            )
            .first()
        )

        if not conversation_check:
            logger.warning(
                f"[LUMOKIT] No conversation with key {request.conversation_key} found for user {request.public_key}"
            )
            return {
                "success": False,
                "conversation_key": request.conversation_key,
                "messages": [],
                "error": "Conversation not found",
            }

        # Get all messages for this conversation in chronological order
        conversation_messages = (
            db.query(Requests)
            .filter(
                Requests.pubkey == request.public_key,
                Requests.conversation_key == request.conversation_key,
            )
            .order_by(Requests.time.asc())
            .all()
        )

        # Format the results
        result_messages = []
        for msg in conversation_messages:
            # Only include messages with successful responses
            if msg.success:
                result_messages.append(
                    MessageResponse(
                        id=msg.id,
                        message=msg.message,
                        response=msg.response,
                        timestamp=msg.time,
                    )
                )

        logger.info(
            f"[LUMOKIT] Retrieved {len(result_messages)} messages for conversation {request.conversation_key}"
        )

        return {
            "success": True,
            "conversation_key": request.conversation_key,
            "messages": result_messages,
        }

    except Exception as e:
        logger.error(f"[LUMOKIT] Error retrieving conversation: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "conversation_key": request.conversation_key,
            "messages": [],
            "error": f"Failed to retrieve conversation: {str(e)}",
        }
