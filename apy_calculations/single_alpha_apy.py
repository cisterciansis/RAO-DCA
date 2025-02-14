import bittensor as bt
import numpy as np

def calculate_apy(netuid: int, hotkey: str, network: str = 'finney', tao_weight: float = 0.18):
    # Connect to the subtensor network
    sub = bt.subtensor(network)
    meta = sub.metagraph(netuid)

    # Get emission rate per block
    emission_per_block = np.array(meta.emission)  # Convert to NumPy array if not already

    # Return 0% APY if emission is zero
    if np.all(emission_per_block == 0):
        return {"local_apy": 0.0, "root_apy": 0.0}

    # Get hotkey's staked Alpha
    alpha_stake_dict = dict(zip(meta.hotkeys, meta.alpha_stake))
    alpha_staked = alpha_stake_dict.get(hotkey, 0)

    # Get TAO stake from root (NetUID 0) and convert using tao_weight
    tao_stake_dict = dict(zip(meta.hotkeys, meta.S))
    tao_staked = tao_stake_dict.get(hotkey, 0) * tao_weight  # Convert TAO stake to Alpha-equivalent

    # Check which validator the hotkey is staked to and their take rate
    validator_stake_dict = dict(zip(meta.hotkeys, meta.validator_permit))
    validator_hotkey = validator_stake_dict.get(hotkey, None)
    validator_take_rate = 0.1  # Default 10%, update if known

    # Adjust stake for validator's take rate
    if validator_hotkey:
        alpha_staked *= (1 - validator_take_rate)
        tao_staked *= (1 - validator_take_rate)

    # Total effective stake
    total_staked = alpha_staked + tao_staked

    # If no effective stake, return 0% APY
    if total_staked == 0:
        return {"local_apy": 0.0, "root_apy": 0.0}

    # Calculate local stake APY
    local_stake_apy = ((1 + (emission_per_block.mean() * 7200 / total_staked)) ** 365) - 1

    # Calculate root stake APY across all subnets
    root_meta = sub.metagraph(0)
    root_stake = sum(root_meta.S) * tao_weight
    root_apy = ((1 + (np.mean(root_meta.emission) * 7200 / root_stake)) ** 365) - 1 if root_stake > 0 else 0.0

    return {
        "local_apy": local_stake_apy * 100,  # Convert to percentage
        "root_apy": root_apy * 100  # Convert to percentage
    }

# Example Usage
if __name__ == "__main__":
    NETUID = 0  # Replace with your subnet NetUID
    HOTKEY = "xxxx"  # Replace with your actual hotkey
    apy_values = calculate_apy(NETUID, HOTKEY)
    print(f"Estimated Local APY for subnet {NETUID}: {apy_values['local_apy']:.2f}%")
    print(f"Estimated Root APY across subnets: {apy_values['root_apy']:.2f}%")
