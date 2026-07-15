from __future__ import annotations

import aiohttp

from config import NFT_CONTRACT_ADDRESS, NFT_RPC_URL

BALANCE_OF_SELECTOR = "0x70a08231"
RPC_TIMEOUT_SECONDS = 10


def is_enabled() -> bool:
    return bool(NFT_CONTRACT_ADDRESS and NFT_RPC_URL)


async def get_nft_balance(wallet_address: str) -> int:
    padded_address = wallet_address.lower().removeprefix("0x").rjust(64, "0")
    call_data = BALANCE_OF_SELECTOR + padded_address

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": NFT_CONTRACT_ADDRESS, "data": call_data}, "latest"],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            NFT_RPC_URL, json=payload, timeout=aiohttp.ClientTimeout(total=RPC_TIMEOUT_SECONDS)
        ) as resp:
            resp.raise_for_status()
            result = await resp.json()

    if "error" in result:
        raise RuntimeError(result["error"].get("message", "RPC error"))

    return int(result["result"], 16)
