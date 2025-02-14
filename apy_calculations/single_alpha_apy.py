import bittensor as bt

def calculate_apy(netuid: int, hotkey: str, network: str = 'finney'):
    # Connect to the subtensor network
    sub = bt.subtensor(network)
    meta = sub.metagraph(netuid)
    
    # Get emission rate per block
    emission_per_block = meta.emission  # Alpha emission rate per block
    
    # Get hotkey's staked Alpha
    alpha_staked = meta.alpha_stake.get(hotkey, 0)
    if alpha_staked == 0:
        raise ValueError("No Alpha staked for the given hotkey.")
    
    # Constants
    blocks_per_day = 7200  # Approximate number of blocks per day
    
    # Calculate daily rewards
    daily_rewards = (emission_per_block * blocks_per_day) * (alpha_staked / meta.total_stake)
    
    # Calculate APY using compounding formula
    apy = ((1 + (daily_rewards / alpha_staked)) ** 365) - 1
    
    return apy * 100  # Convert to percentage

# Example Usage
if __name__ == "__main__":
    NETUID = 3  # Replace with your subnet NetUID
    HOTKEY = "your_hotkey_here"  # Replace with your actual hotkey
    apy = calculate_apy(NETUID, HOTKEY)
    print(f"Estimated APY for subnet {NETUID}: {apy:.2f}%")
