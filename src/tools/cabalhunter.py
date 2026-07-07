from typing import ClassVar, Type

import aiohttp
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from settings.logger import logger

#################################################
#### CABAL-HUNTER EXIT-LIQUIDITY RISK TOOL ####
#################################################


class CabalHunterRiskInput(BaseModel):
    """Input for the Cabal-Hunter exit-liquidity risk tool."""

    token_address: str = Field(
        ..., description="The Solana token mint address to scan for cabal / rug risk"
    )


class CabalHunterRiskTool(BaseTool):
    """Complete pre-trade safety verdict for a Solana token via Cabal-Hunter."""

    name: ClassVar[str] = "cabal_hunter_risk_tool"
    description: ClassVar[str] = (
        "Get a complete pre-trade safety verdict for a Solana token before buying: traces "
        "coordinated wallet / cabal funding clusters, same-block bundle buys, live coordinated "
        "dumps, serial-rug deployer history and honeypot / freeze-authority traps, and returns a "
        "single 0-100 Exit-Liquidity Risk score with a recommendation (AVOID / CAUTION / LOW "
        "SIGNAL). Use before any Solana buy or swap; do not buy if recommendation is AVOID or "
        "cabal_score >= 65."
    )
    args_schema: ClassVar[Type[BaseModel]] = CabalHunterRiskInput

    async def _arun(self, token_address: str) -> str:
        """Execute the Cabal-Hunter risk scan asynchronously."""
        try:
            token_address = token_address.strip()
            logger.info(f"[LUMOKIT] Cabal-Hunter risk scan for: {token_address}")

            api_url = (
                "https://api.cabal-hunter.com/api/scan-cabal"
                f"?mintAddress={token_address}"
            )

            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status != 200:
                        logger.error(
                            f"[LUMOKIT] Error fetching Cabal-Hunter data: "
                            f"{response.status} - {await response.text()}"
                        )
                        return (
                            f"Failed to scan token {token_address}. The token may not exist "
                            f"or the Cabal-Hunter service is unavailable."
                        )
                    data = await response.json()

            if data.get("error"):
                return (
                    f"Cabal-Hunter could not scan {token_address}: "
                    f"{data.get('message', data.get('error'))}"
                )

            name = data.get("token_name") or token_address[:8]
            score = data.get("cabal_score", "?")
            risk = data.get("risk", "?")
            recommendation = data.get("recommendation", "?")
            verdict = data.get("verdict", "")

            lines = [
                f"Cabal-Hunter verdict for {name} ({token_address}):",
                f"Exit-Liquidity Risk score: {score}/100  |  Risk: {risk}  |  "
                f"Recommendation: {recommendation}",
            ]
            if verdict:
                lines += ["", verdict]

            flags = []
            if data.get("time_sync"):
                flags.append(
                    "- Same-block bundle: multiple holders bought in the same block "
                    "(coordinated launch)."
                )
            if data.get("coordinated_exit"):
                flags.append(
                    "- Coordinated dump in progress: multiple holders selling in the "
                    "same block."
                )
            top_holder_pct = data.get("top_holder_pct")
            if top_holder_pct and top_holder_pct >= 15:
                flags.append(
                    f"- Concentration: a single wallet holds {top_holder_pct:.1f}% of supply."
                )
            deployer_verdict = (data.get("deployer") or {}).get("verdict")
            if deployer_verdict and deployer_verdict not in ("FIRST_LAUNCH", "NORMAL"):
                flags.append(f"- Deployer: {deployer_verdict.replace('_', ' ').title()}.")
            honeypot = data.get("honeypot_risk")
            if (honeypot and str(honeypot).lower() != "none") or data.get(
                "freeze_authority_revoked"
            ) is False:
                flags.append("- Honeypot / freeze-authority risk detected.")

            if flags:
                lines += ["", "Flags:"] + flags

            liquidity = data.get("liquidity_usd")
            market_cap = data.get("market_cap")
            if liquidity is not None or market_cap is not None:
                lines.append("")
                lines.append(
                    f"Liquidity: ${liquidity:,.0f}" if liquidity else "Liquidity: unknown"
                )
                if market_cap:
                    lines.append(f"Market cap: ${market_cap:,.0f}")

            lines.append("")
            lines.append(
                "Powered by Cabal-Hunter (https://api.cabal-hunter.com) — "
                "250 free scans/month, no key."
            )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"[LUMOKIT] Error in Cabal-Hunter risk tool: {str(e)}")
            return (
                "Unable to retrieve a Cabal-Hunter verdict at this time. Please try again "
                "later or check that the Solana token address is valid."
            )

    def _run(self, token_address: str) -> str:
        """Synchronous version not implemented."""
        raise NotImplementedError("This tool only supports async execution.")
