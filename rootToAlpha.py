import asyncio
import bittensor as bt
import time
from typing import Dict, Optional, Union
import logging
import os

logging.basicConfig(
    level=logging.INFO,  
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

SUBNET_DISTRIBUTION: Dict[int, Dict[str, float]] = {
    281: {"weight": 0.5, "max_slippage": 0.5},  # netuid: weight and max_slippage
    277: {"weight": 0.3, "max_slippage": 0.3},
    18: {"weight": 0.15, "max_slippage": 0.2},
    5: {"weight": 0.05, "max_slippage": 0.1},
}

WALLET_NAME = os.getenv("BITTENSOR_WALLET_NAME", "test") 
wallet = bt.wallet(name=WALLET_NAME)
wallet.unlock_coldkey()

ROOT_NETUID = 0
ROOT_HOTKEY = os.getenv("ROOT_HOTKEY", "5F9kqc6VJD24vJEZsnkNMHytHqSh6NCx88iZmuLXejvdR6og") 

def parse_balance(balance_obj) -> float:
    try:
        balance_str = str(balance_obj)
        logger.debug(f"Parsing balance string: {balance_str} (Type: {type(balance_str)})")
        
        balance_str = balance_str.replace('τ', '').replace(',', '').strip()
        balance = float(balance_str)
        return balance
    except (AttributeError, ValueError, TypeError) as e:
        logger.error(f"Error parsing balance object: {balance_obj} ({e})")
        return 0.0

async def calculate_slippage(tao_amount: float, subnet) -> float:
    if subnet.alpha_in == 0:
        return float('inf')
    theoretical_alpha = tao_amount / float(subnet.price)
    k = float(subnet.tao_in) * float(subnet.alpha_in)
    new_tao = float(subnet.tao_in) + tao_amount
    new_alpha = k / new_tao
    return ((theoretical_alpha - (float(subnet.alpha_in) - new_alpha)) / theoretical_alpha) * 100 if theoretical_alpha > 0 else float('inf')

async def find_optimal_stake(netuid: int, subnet, max_amount: float, max_slippage: float) -> float:
    tao_amount = 0.0001
    step = max_amount / 10

    while tao_amount <= max_amount:
        slippage = await calculate_slippage(tao_amount, subnet)
        if slippage > max_slippage:
            tao_amount -= step
            step /= 2
        else:
            tao_amount += step

        if step < 0.0001:
            break

    return max(0.0001, tao_amount)

async def process_subnet(subtensor, netuid: int, max_slippage: float, distribute_tao: float) -> float:
    try:
        subnet = await subtensor.subnet(netuid)
        optimal_amount = await find_optimal_stake(netuid, subnet, distribute_tao, max_slippage)

        if optimal_amount >= 0.0001:
            stake_before = await subtensor.get_stake(
                hotkey_ss58=subnet.owner_hotkey,
                coldkey_ss58=wallet.coldkeypub.ss58_address,
                netuid=netuid
            )

            expected_alpha = optimal_amount / float(subnet.price)
            expected_slippage = await calculate_slippage(optimal_amount, subnet)

            logger.info(f"Staking {optimal_amount:.5f} TAO to netuid {netuid}")
            logger.info(f"Expected ALPHA: {expected_alpha:.5f}, Expected Slippage: {expected_slippage:.2f}%")

            await subtensor.add_stake(
                wallet=wallet,
                netuid=netuid,
                hotkey=subnet.owner_hotkey,
                tao_amount=optimal_amount
            )

            # sleep 4 txn to finish
            await asyncio.sleep(12)

            stake_after = await subtensor.get_stake(
                hotkey_ss58=subnet.owner_hotkey,
                coldkey_ss58=wallet.coldkeypub.ss58_address,
                netuid=netuid
            )

            logger.info(f"Stake before: {stake_before}, Stake after: {stake_after}")
            return optimal_amount
    except Exception as e:
        logger.error(f"Error processing subnet {netuid}: {e}")

    return 0

async def distribute_dividends(subtensor, dividends: float):
    total_weight = sum(config["weight"] for config in SUBNET_DISTRIBUTION.values())
    total_spend = 0

    tasks = []
    for netuid, config in SUBNET_DISTRIBUTION.items():
        weight = config["weight"]
        max_slippage = config["max_slippage"]
        distribute_tao = dividends * (weight / total_weight)
        task = asyncio.create_task(
            process_subnet(subtensor, netuid, max_slippage, distribute_tao)
        )
        tasks.append(task)
      
    results = await asyncio.gather(*tasks)
    total_spend = sum(results)
    logger.info(f"Total distributed TAO: {total_spend:.5f}")

async def track_and_distribute(subtensor):
    try:
        balance_dict = await subtensor.get_balance(ROOT_HOTKEY, wallet.coldkeypub.ss58_address)
        balance_obj = balance_dict.get(ROOT_HOTKEY, None)
        
        if balance_obj is None:
            logger.error(f"No balance found for ROOT_HOTKEY: {ROOT_HOTKEY}")
            return
        
        last_balance = parse_balance(balance_obj)
        logger.info(f"Initial Root Balance: {last_balance:.9f} TAO")
    except Exception as e:
        logger.error(f"Error fetching initial balance: {e}")
        return

    while True:
        try:
            balance_dict = await subtensor.get_balance(ROOT_HOTKEY, wallet.coldkeypub.ss58_address)
            balance_obj = balance_dict.get(ROOT_HOTKEY, None)
            
            if balance_obj is None:
                logger.error(f"No balance found for ROOT_HOTKEY: {ROOT_HOTKEY}")
                dividends = 0.0
            else:
                current_balance = parse_balance(balance_obj)
                dividends = current_balance - last_balance

            if dividends > 0:
                logger.info(f"Dividends detected: {dividends:.5f} TAO")
                await distribute_dividends(subtensor, dividends)
                last_balance = current_balance
            else:
                logger.info("No new dividends detected.")

            # check again after block
            await subtensor.wait_for_block()
        except Exception as e:
            logger.error(f"Error during tracking and distribution: {e}")
            await asyncio.sleep(5)

async def main():
    try:
        subtensor = await bt.async_subtensor('test')

        await track_and_distribute(subtensor)
    except Exception as e:
        logger.error(f"Error initializing subtensor connection: {e}")

if __name__ == "__main__":
    asyncio.run(main())
