from .birdeye import BirdeyeAllTimeTradesTool, BirdeyeTokenTrendingTool
from .coingecko import (CoinGeckoCoinDataTool, CoinGeckoExchangeRatesTool,
                        CoinGeckoGlobalCryptoDataTool, CoinGeckoTrendingTool)
from .coinmarketcap import CMCCryptoNewsTool, CMCTrendingCoinsTool
from .common import TokenIdentificationTool, WalletPortfolioTool
from .cryptodotnews import CNMemecoinsNewsTool
from .dappradar import DappRadarGameTrackerTool
from .dexscreener import (DexScreenerTokenInformationTool,
                          DexScreenerTopBoostsTool)
from .fluxbeam import FluxBeamTokenPriceTool
from .geckoterminal import GTPumpFunTrendingTool
from .jupiter import (JupiterSwapTool, JupiterTokenInformationTool,
                      JupiterTokenPriceTool)
from .pumpfun import PumpFunLaunchCoinTool
from .rugcheck import RugcheckTokenInformationTool
from .solana import (SolanaBurnTokenTool, SolanaSendSolTool,
                     SolanaSendSplTokensTool)

###################################################
##### TOOL DESCRIPTIONS ####
###################################################

TOOL_DESCRIPTIONS = {
    "WalletPortfolioTool": "wallet_portfolio_tool: Get detailed information about all tokens, their contract address, held in a wallet. [HIGHEST PRIORITY, SHOULD BE USED IN PLACE: 1]",
    "TokenIdentificationTool": "token_identification_tool: Get token information by name or ticker symbol. Use this to find contract addresses for tokens. [HIGHEST PRIORITY, SHOULD BE USED IN PLACE: 2]",
    "RugcheckTokenInformationTool": "rugcheck_token_information_tool: Get detailed token information including creator details, supply, top holders, and insiders information. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 3]",
    "FluxBeamTokenPriceTool": "fluxbeam_token_price_tool: Get the current price of a token in USD (US Dollars) from FluxBeam. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 4]",
    "JupiterTokenPriceTool": "jupiter_token_price_tool: Get the current price of one or more Solana tokens in USD from Jupiter. Supports multiple comma-separated token addresses. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "JupiterTokenInformationTool": "jupiter_token_information_tool: Get detailed token information and metadata for a specific Solana token from Jupiter. Provides details like name, symbol, decimals, and other token attributes. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "JupiterSwapTool": "jupiter_swap_tool: Swap tokens on Solana using Jupiter. This tool can buy or sell tokens by exchanging one for another. Requires agent wallet authentication. [LOW PRIORITY, SHOULD BE USED IN PLACE: 6]",
    "DexScreenerTopBoostsTool": "dexscreener_top_boosts_tool: Get tokens with the most active boosts on DexScreener, showing popularity and trending projects. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "DexScreenerTokenInformationTool": "dexscreener_token_information_tool: Get detailed DEX information about Solana tokens including price, volume, liquidity, and trading activity. It must be sent token addresses only as input. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "BirdeyeTokenTrendingTool": "birdeye_token_trending_tool: Get a list of top trending tokens on Solana with prices, market caps, and volume data. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "BirdeyeAllTimeTradesTool": "birdeye_all_time_trades_tool: Get comprehensive trade statistics (buys, sells, volumes) of all time for a specific token on Solana. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "CMCCryptoNewsTool": "cmc_crypto_news_tool: Get the latest crypto news from CoinMarketCap including headlines, content and related tickers. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "CMCTrendingCoinsTool": "cmc_trending_coins_tool: Get a list of top cryptocurrencies ranked by market cap with price, market cap, and 24h change data. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "CNMemecoinsNewsTool": "cn_memecoins_news_tool: Get the latest memecoin news from Crypto.news including headlines, content and related tickers. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "GTPumpFunTrendingTool": "geckoterminal_trending_pumpfun_tool: Get the latest trending tokens from the Pump.fun category on GeckoTerminal with price, volume, and market data. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "CoinGeckoGlobalCryptoDataTool": "coingecko_global_crypto_data_tool: Get global cryptocurrency market data including market cap, volume, and dominance percentages. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "CoinGeckoTrendingTool": "coingecko_trending_tool: Get top trending coins and NFTs on CoinGecko based on user searches and trading volume. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "CoinGeckoExchangeRatesTool": "coingecko_exchange_rates_tool: Get Bitcoin-to-currency exchange rates for major cryptocurrencies, fiat currencies, and commodities. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "CoinGeckoCoinDataTool": "coingecko_coin_data_tool: Get detailed market data (price, volume, market cap) for a specific cryptocurrency. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
    "SolanaSendSolTool": "solana_send_sol_tool: Send SOL from your agent wallet to a specified Solana address. Requires your agent wallet's public and encrypted private keys. [LOW PRIORITY, SHOULD BE USED IN PLACE: 6]",
    "SolanaSendSplTokensTool": "solana_send_spl_tokens_tool: Send SPL tokens from your agent wallet to a specified Solana address. Requires your agent wallet's public and encrypted private keys, token address, and amount. [LOW PRIORITY, SHOULD BE USED IN PLACE: 6]",
    "SolanaBurnTokenTool": "solana_burn_token_tool: Burn SPL tokens from your agent wallet, permanently removing them from circulation. Requires your agent wallet's public and encrypted private keys, token address, and amount. [LOW PRIORITY, SHOULD BE USED IN PLACE: 6]",
    "PumpFunLaunchCoinTool": "pumpfun_launch_coin_tool: Launch a new token on Pump.fun platform. Create your own token with custom name, symbol, description, and image. Requires agent wallet for token creation. [LOW PRIORITY, SHOULD BE USED IN PLACE: 6]",
    "DappRadarGameTrackerTool": "dappradar_game_tracker_tool: Track active game projects on various blockchains (Solana, Ethereum, Polygon, etc.) including MMORPG, arcade, staking games, and their token data, player counts, and current status. Perfect for players, investors, game developers, and influencers. [MEDIUM PRIORITY, SHOULD BE USED IN PLACE: 5]",
}


def get_tools_system_message(tools_list):
    """
    Generate the tools section for system messages based on the tools being used

    Args:
        tools_list: List of tool instances that will be used with the agent

    Returns:
        String with formatted tool descriptions for the system message
    """
    if not tools_list:
        return ""

    tools_text = "You have access to tools that you must use sequentially:\n"

    for tool in tools_list:
        tool_class_name = tool.__class__.__name__
        if tool_class_name in TOOL_DESCRIPTIONS:
            tools_text += f"- {TOOL_DESCRIPTIONS[tool_class_name]}\n"

    return tools_text


__all__ = [
    "WalletPortfolioTool",
    "TokenIdentificationTool",
    "RugcheckTokenInformationTool",
    "FluxBeamTokenPriceTool",
    "JupiterTokenPriceTool",
    "JupiterTokenInformationTool",
    "JupiterSwapTool",
    "DappRadarGameTrackerTool",
    "DexScreenerTopBoostsTool",
    "DexScreenerTokenInformationTool",
    "BirdeyeTokenTrendingTool",
    "BirdeyeAllTimeTradesTool",
    "CMCCryptoNewsTool",
    "CMCTrendingCoinsTool",
    "CNMemecoinsNewsTool",
    "GTPumpFunTrendingTool",
    "CoinGeckoGlobalCryptoDataTool",
    "CoinGeckoTrendingTool",
    "CoinGeckoExchangeRatesTool",
    "CoinGeckoCoinDataTool",
    "SolanaSendSolTool",
    "SolanaSendSplTokensTool",
    "SolanaBurnTokenTool",
    "PumpFunLaunchCoinTool",
    "TOOL_DESCRIPTIONS",
    "get_tools_system_message",
]
