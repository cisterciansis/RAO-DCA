# DCA 1000 TAO into these subnets over many blocks
to_buy = [1, 277, 18, 5]
increment = 0.01
total_spend = 0
stake = {}
while total_spend < 1000:
    for netuid in to_buy:
        subnet = await sub.subnet(netuid)
        await sub.add_stake( 
            wallet = wallet, 
            netuid = netuid, 
            hotkey = subnet.owner_hotkey, 
            tao_amount = increment, 
        )
        current_stake = await sub.get_stake(
            coldkey_ss58 = wallet.coldkeypub.ss58_address,
            hotkey_ss58 = subnet.owner_hotkey,
            netuid = netuid,
        )
        stake[netuid] = current_stake
        total_spend += increment
    print ('netuid', netuid, 'price', subnet.price, 'stake', current_stake )
    await sub.wait_for_block()
