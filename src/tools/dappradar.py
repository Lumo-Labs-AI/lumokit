from typing import ClassVar, Optional, Type

import aiohttp
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from settings.config import CONFIG
from settings.logger import logger

#################################################
#### DAPPRADAR GAME TRACKER TOOL ####
#################################################


class DappRadarGameTrackerInput(BaseModel):
    """Input for the DappRadar Game Tracker tool."""

    limit: int = Field(default=10, description="Number of games to retrieve (max 20)")
    chain: str = Field(
        default="solana",
        description="Chain to search games on (solana, ethereum, etc.)",
    )
    category: Optional[str] = Field(
        default=None,
        description="Game category filter: 'MMORPG', 'FPS', 'Idle', 'Arcade', 'Card', 'RPG', 'Strategy', etc.",
    )


class DappRadarGameTrackerTool(BaseTool):
    """Tool for tracking active blockchain games and their token data using DappRadar."""

    name: ClassVar[str] = "dappradar_game_tracker_tool"
    description: ClassVar[str] = (
        "Track active game projects on various blockchains (Solana, Ethereum, Polygon, etc.) "
        "including MMORPG, arcade, staking games, and their token data, player counts, and current status. "
        "Perfect for players, investors, game developers, and influencers."
    )
    args_schema: ClassVar[Type[BaseModel]] = DappRadarGameTrackerInput

    async def _arun(
        self, limit: int = 10, chain: str = "solana", category: Optional[str] = None
    ) -> str:
        """Execute the DappRadar game tracking lookup asynchronously."""
        try:
            logger.info(
                f"[LUMOKIT] DappRadar Game Tracker lookup - limit: {limit}, chain: {chain}, category: {category}"
            )

            # Validate and cap the limit
            if limit <= 0:
                limit = 10
            elif limit > 20:
                limit = 20

            # Validate chain support
            supported_chains = ["solana", "ethereum", "polygon", "bsc", "avalanche"]
            if chain.lower() not in supported_chains:
                return f"Chain '{chain}' is not supported. Supported chains: {', '.join(supported_chains)}"

            # Fetch games data from DappRadar
            games_data = await self._fetch_games_data(limit, chain.lower(), category)

            if not games_data:
                return f"No {chain} games data could be retrieved at this time. Please try again later."

            # Format the result
            return self._format_games_result(games_data, chain, category)

        except Exception as e:
            logger.error(f"[LUMOKIT] Error in DappRadar Game Tracker tool: {str(e)}")
            return f"Failed to retrieve {chain} games data: {str(e)}"

    async def _fetch_games_data(
        self, limit: int, chain: str, category: Optional[str]
    ) -> list:
        """Fetch games data from DappRadar API."""
        try:
            logger.info(
                f"[LUMOKIT] Fetching {chain} games from DappRadar - limit: {limit}, category: {category}"
            )

            # API URL
            url = "https://apis.dappradar.com/v2/dapps/top/uaw"

            # Set up the parameters
            params = {"top": limit, "category": "games", "chain": chain}

            # Set up headers with API key
            headers = {
                "X-API-KEY": CONFIG.DAPPRADAR_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # Log API call information (without exposing the key)
            logger.info(f"[LUMOKIT] Calling DappRadar API: {url} with params: {params}")

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        logger.warning(
                            f"[LUMOKIT] DappRadar API error: {response.status}"
                        )
                        error_text = await response.text()
                        logger.error(f"[LUMOKIT] Error response: {error_text[:500]}")
                        return []

                    data = await response.json()
                    logger.info(
                        f"[LUMOKIT] DappRadar response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}"
                    )

                    # Try different response structures
                    results = data.get(
                        "results", data.get("data", data.get("dapps", []))
                    )

                    if not results:
                        logger.warning(
                            f"[LUMOKIT] No results found in DappRadar response"
                        )
                        return []

                    games = []
                    for game in results:
                        # Check if it's actually a game on the requested chain
                        chains = game.get("chains", [])
                        if not any(
                            chain.lower() in game_chain.lower() for game_chain in chains
                        ):
                            logger.debug(
                                f"[LUMOKIT] Skipping non-{chain} game: {game.get('name')} on chains {chains}"
                            )
                            continue

                        # Filter by category if specified
                        game_categories = game.get("categories", [])
                        category_name = (
                            game_categories[0] if game_categories else "Games"
                        )

                        if category and category.lower() not in category_name.lower():
                            continue

                        # Extract metrics data
                        metrics = game.get("metrics", {})
                        daily_users = metrics.get("uaw", 0)  # Unique Active Wallets
                        daily_volume = metrics.get("volume", 0)
                        daily_transactions = metrics.get("transactions", 0)

                        games.append(
                            {
                                "name": game.get("name", "Unknown Game"),
                                "description": game.get(
                                    "description", "No description available"
                                ),
                                "full_description": game.get("fullDescription", ""),
                                "category": category_name.title(),
                                "website": game.get("website", ""),
                                "logo": game.get("logo", ""),
                                "daily_users": daily_users,
                                "daily_volume": daily_volume,
                                "daily_transactions": daily_transactions,
                                "chains": chains,
                                "status": "Live"
                                if game.get("isActive", True)
                                else "Inactive",
                                "social_links": game.get("socialLinks", []),
                                "tags": game.get("tags", []),
                                "dapp_id": game.get("dappId", ""),
                                "dappradar_link": game.get("link", ""),
                                "balance": metrics.get("balance", 0),
                                "transactions_change": metrics.get(
                                    "transactionsPercentageChange", 0
                                ),
                                "uaw_change": metrics.get("uawPercentageChange", 0),
                                "volume_change": metrics.get(
                                    "volumePercentageChange", 0
                                ),
                            }
                        )

                        if len(games) >= limit:
                            break

                    logger.info(
                        f"[LUMOKIT] Successfully fetched {len(games)} {chain} games from DappRadar"
                    )

                    return games[:limit]

        except Exception as e:
            logger.error(f"[LUMOKIT] Error fetching from DappRadar: {str(e)}")
            return []

    def _format_games_result(
        self, games: list, chain: str, category: Optional[str]
    ) -> str:
        """Format the games data into a readable result."""
        if not games:
            return f"No {chain} games found matching your criteria."

        category_filter = f" in {category} category" if category else ""
        result = f"## Top {len(games)} {chain.capitalize()} Blockchain Games{category_filter}\n\n"

        for i, game in enumerate(games, 1):
            result += f"### {i}. {game['name']}\n"
            result += f"**Category**: {game['category']}\n"
            result += f"**Chain**: {chain.capitalize()}\n"
            result += f"**Status**: {game['status']}\n"

            # Description with smart truncation
            if description := game.get("description"):
                result += f"**Description**: {description}\n"

            # Metrics section
            if daily_users := game.get("daily_users"):
                result += f"**Daily Active Users**: {daily_users:,}"
                if uaw_change := game.get("uaw_change"):
                    change_icon = (
                        "📈" if uaw_change > 0 else "📉" if uaw_change < 0 else "➡️"
                    )
                    result += f" ({uaw_change:+.1f}% {change_icon})"
                result += "\n"

            if daily_transactions := game.get("daily_transactions"):
                if daily_transactions > 0:
                    result += f"**Daily Transactions**: {daily_transactions:,}"
                    if tx_change := game.get("transactions_change"):
                        change_icon = (
                            "📈" if tx_change > 0 else "📉" if tx_change < 0 else "➡️"
                        )
                        result += f" ({tx_change:+.1f}% {change_icon})"
                    result += "\n"

            if daily_volume := game.get("daily_volume"):
                if daily_volume > 0:
                    result += f"**Daily Volume**: ${daily_volume:,.2f}"
                    if volume_change := game.get("volume_change"):
                        change_icon = (
                            "📈"
                            if volume_change > 0
                            else "📉"
                            if volume_change < 0
                            else "➡️"
                        )
                        result += f" ({volume_change:+.1f}% {change_icon})"
                    result += "\n"

            if balance := game.get("balance"):
                if balance > 0:
                    result += f"**Balance**: ${balance:,.2f}\n"

            # Links and external info
            if website := game.get("website"):
                result += f"**Website**: {website}\n"

            if dappradar_link := game.get("dappradar_link"):
                result += f"**DappRadar**: {dappradar_link}\n"

            # Additional chains if multichain
            if chains := game.get("chains"):
                if len(chains) > 1:
                    other_chains = [
                        c.capitalize() for c in chains if c.lower() != chain.lower()
                    ]
                    if other_chains:
                        result += f"**Also Available On**: {', '.join(other_chains)}\n"

            # Tags
            if tags := game.get("tags"):
                if tags and len(tags) > 0:
                    tags_str = [
                        t
                        if isinstance(t, str)
                        else (
                            t.get("name") or t.get("title") or t.get("slug") or str(t)
                        )
                        for t in tags
                    ]
                    result += f"**Tags**: {', '.join(tags_str[:5])}\n"  # Limit to first 5 tags

            # Social links
            if social_links := game.get("social_links"):
                if social_links and len(social_links) > 0:
                    social_platforms = []
                    for link in social_links[:3]:  # Limit to first 3 social links
                        if isinstance(link, dict):
                            if title := link.get("title", "").title():
                                if url := link.get("url"):
                                    social_platforms.append(f"[{title}]({url})")

                    if social_platforms:
                        result += f"**Social**: {' | '.join(social_platforms)}\n"

            # Full description
            if full_desc := game.get("full_description"):
                result += f"**Details**: {full_desc}\n"

            # DappId for reference
            if dapp_id := game.get("dapp_id"):
                result += f"**DApp ID**: {dapp_id}\n"

            result += "\n"

        result += "*Data sourced from DappRadar API*"
        return result

    def _run(
        self, limit: int = 10, chain: str = "solana", category: Optional[str] = None
    ) -> str:
        """Synchronous version returns a message instead of raising an error."""
        return "This tool only supports asynchronous execution. Please use the async version instead."
