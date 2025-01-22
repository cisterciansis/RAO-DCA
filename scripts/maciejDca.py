import asyncio
import bittensor as bt
import time
from typing import Dict

SUBNET_CONFIGS: Dict[int, float] = {
    281: 0.5,  # netuid: max_slippage
}

wallet = bt.wallet(name="default")
wallet.unlock_coldkey()

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

async def process_subnet(subtensor, netuid: int, max_slippage: float, total_tao: float, remaining_tao: float) -> float:
    subnet = await subtensor.subnet(netuid)
    optimal_amount = await find_optimal_stake(netuid, subnet, min(remaining_tao, total_tao / 10), max_slippage)

    if optimal_amount >= 0.0001:
        stake_before = await subtensor.get_stake(
            coldkey_ss58=wallet.coldkeypub.ss58_address,
            hotkey_ss58=subnet.owner_hotkey,
            netuid=netuid
        )

        expected_alpha = optimal_amount / float(subnet.price)
        expected_slippage = await calculate_slippage(optimal_amount, subnet)

        print(f"Staking {optimal_amount:.5f} TAO to netuid {netuid}")
        print(f"Expected ALPHA: {expected_alpha:.5f}, Expected Slippage: {expected_slippage:.2f}%")

        await subtensor.add_stake(wallet=wallet, netuid=netuid, hotkey=subnet.owner_hotkey, tao_amount=optimal_amount)
        
        time.sleep(12)

        stake_after = await subtensor.get_stake(
            coldkey_ss58=wallet.coldkeypub.ss58_address,
            hotkey_ss58=subnet.owner_hotkey,
            netuid=netuid
        )

        print(f"Stake before: {stake_before}, Stake after: {stake_after}")
        return optimal_amount
    return 0

async def main():
    subtensor = await bt.async_subtensor('test')
    total_spend, total_tao = 0, 50
    block_interval = 5

    while total_spend < total_tao:
        for netuid, max_slippage in SUBNET_CONFIGS.items():
            remaining_tao = total_tao - total_spend
            if remaining_tao <= 0:
                break
                
            spent = await process_subnet(subtensor, netuid, max_slippage, total_tao, remaining_tao)
            total_spend += spent

        for _ in range(block_interval):
            await subtensor.wait_for_block()

if __name__ == "__main__":
    asyncio.run(main())
