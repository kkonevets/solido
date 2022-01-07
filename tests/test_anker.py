#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2021 Chorus One AG
# SPDX-License-Identifier: GPL-3.0

"""
This script calls 'solana' and 'solido' to confirm that functionality works.

It exits with exit code 0 if everything works as expected, or with a nonzero
exit code if anything fails. It expects a test validator to be running at at the
default localhost port, and it expects a keypair at ~/.config/solana/id.json
that corresponds to a sufficiently funded account.
"""
import os
from typing import Any, Dict, Optional

from util import (
    create_test_account,
    get_approve_and_execute,
    get_solido_program_path,
    multisig,
    solana_program_deploy,
    solido,
    spl_token,
    spl_token_balance,
    create_spl_token_account,
)

print('Creating test accounts ...')
os.makedirs('tests/.keys', exist_ok=True)
test_addrs = [
    create_test_account('tests/.keys/test-key-1.json'),
    create_test_account('tests/.keys/test-key-2.json'),
]
print(f'> {test_addrs}')

treasury_account_owner = create_test_account('tests/.keys/treasury-key.json')
print(f'> Treasury account owner:      {treasury_account_owner}')

developer_account_owner = create_test_account('tests/.keys/developer-fee-key.json')
print(f'> Developer fee account owner: {developer_account_owner}')


print('\nSetting up UST mint ...')
ust_mint_address = create_test_account('tests/.keys/ust_mint_address.json', fund=False)
spl_token('create-token', 'tests/.keys/ust_mint_address.json', '--decimals', '6')
print(f'> UST mint is {ust_mint_address.pubkey}.')

print('\nUploading Multisig program ...')
multisig_program_id = solana_program_deploy(
    get_solido_program_path() + '/serum_multisig.so'
)
print(f'> Multisig program id is {multisig_program_id}.')

print('\nUploading Solido program ...')
solido_program_id = solana_program_deploy(get_solido_program_path() + '/lido.so')
print(f'> Solido program id is {solido_program_id}.')

print('\nUploading Anker program ...')
anker_program_id = solana_program_deploy(get_solido_program_path() + '/anker.so')
print(f'> Anker program id is {anker_program_id}.')

print('\nDeploying Orca Token Swap program ...')
orca_token_swap_program_id = solana_program_deploy(
    get_solido_program_path() + '/orca_token_swap_v2.so'
)
print(f'> Orca program id is {orca_token_swap_program_id}.')

print('\nCreating new multisig ...')
multisig_data = multisig(
    'create-multisig',
    '--multisig-program-id',
    multisig_program_id,
    '--threshold',
    '1',
    '--owners',
    ','.join(t.pubkey for t in test_addrs),
)
multisig_instance = multisig_data['multisig_address']
multisig_pda = multisig_data['multisig_program_derived_address']
print(f'> Created instance at {multisig_instance}.')


approve_and_execute = get_approve_and_execute(
    multisig_program_id=multisig_program_id,
    multisig_instance=multisig_instance,
    signer_keypair_paths=[t.keypair_path for t in test_addrs],
)


print('\nCreating Solido instance ...')
result = solido(
    'create-solido',
    '--multisig-program-id',
    multisig_program_id,
    '--solido-program-id',
    solido_program_id,
    '--max-validators',
    '9',
    '--max-maintainers',
    '1',
    '--treasury-fee-share',
    '4',
    '--validation-fee-share',
    '5',
    '--developer-fee-share',
    '1',
    '--st-sol-appreciation-share',
    '90',
    '--treasury-account-owner',
    treasury_account_owner.pubkey,
    '--developer-account-owner',
    developer_account_owner.pubkey,
    '--multisig-address',
    multisig_instance,
    keypair_path=test_addrs[0].keypair_path,
)

solido_address = result['solido_address']
treasury_account = result['treasury_account']
developer_account = result['developer_account']
st_sol_mint_address = result['st_sol_mint_address']

print(f'> Created instance at {solido_address}.')

print('\nCreating Token Pool accounts ...')
print('> Creating UST token pool account ...')
ust_pool_account = create_spl_token_account(
    test_addrs[0].keypair_path, ust_mint_address.pubkey
)

print('> Creating stSOL token pool account ...')
st_sol_pool_account = create_spl_token_account(
    test_addrs[0].keypair_path, st_sol_mint_address
)

print('> Adding liquidity ...')
print(' > Depositing 1 Sol to Solido')
result = solido(
    'deposit',
    '--solido-program-id',
    solido_program_id,
    '--solido-address',
    solido_address,
    '--amount-sol',
    '1',
)
print(' > Transfering to pool\'s stSOL account.')
spl_token('transfer', st_sol_mint_address, '1', st_sol_pool_account)
print(' > Minting to pool\'s UST account.')
spl_token('mint', ust_mint_address.pubkey, '1', ust_pool_account)

print('\nCreating token pool instance ...')
result = solido(
    'anker',
    'create-token-pool',
    '--token-swap-program-id',
    orca_token_swap_program_id,
    '--st-sol-account',
    st_sol_pool_account,
    '--ust-account',
    ust_pool_account,
    '--ust-mint-address',
    ust_mint_address.pubkey,
    keypair_path=test_addrs[0].keypair_path,
)
token_pool_address = result['pool_address']
print(f'> Created instance at {token_pool_address}.')

print('\nCreating Anker instance ...')
terra_rewards_address = 'terra18aqm668ygwppxnmkmjn4wrtgdweq5ay7rs42ch'
result = solido(
    'anker',
    'create',
    '--solido-program-id',
    solido_program_id,
    '--solido-address',
    solido_address,
    '--anker-program-id',
    anker_program_id,
    '--ust-mint-address',
    ust_mint_address.pubkey,
    '--token-swap-pool',
    token_pool_address,
    '--wormhole-core-bridge-program-id',
    # Wormhole's testnet address. TODO: Replace with a new localhost program instance.
    '3u8hJUVTA4jH1wYAyUur7FFZVQ8H635K3tSHHF4ssjQ5',
    '--wormhole-token-bridge-program-id',
    # Wormhole's testnet address. TODO: Replace with a new localhost program instance.
    'DZnkkTmCiFWfYTfT41X3Rd1kDgozqzxWaHqsw6W4x2oe',
    '--terra-rewards-address',
    terra_rewards_address,
)
# TODO: Also provide --mint-address, we need to be sure that that one works.
anker_address = result['anker_address']
anker_st_sol_reserve_account = result['st_sol_reserve_account']
anker_ust_reserve_account = result['ust_reserve_account']
b_sol_mint_address = result['b_sol_mint_address']
print(f'> Created instance at {anker_address}.')


print('\nVerifying Anker instance with `solido anker show` ...')
result = solido('anker', 'show', '--anker-address', anker_address)

# Some addresses are generated and it's tedious here in this test to know what
# they are ahead of time, so we don't check those against a reference, instead
# we store them so we can use them later in this test.
reserve_authority = result.pop('reserve_authority')
b_sol_mint_authority = result.pop('b_sol_mint_authority')

# We do check the remaining fields.
expected_result = {
    'anker_address': anker_address,
    'anker_program_id': anker_program_id,
    'solido_address': solido_address,
    'solido_program_id': solido_program_id,
    'b_sol_mint': b_sol_mint_address,
    'st_sol_reserve': anker_st_sol_reserve_account,
    'ust_reserve': anker_ust_reserve_account,
    'terra_rewards_destination': terra_rewards_address,
    'ust_reserve_balance_micro_ust': 0,
    'st_sol_reserve_balance_st_lamports': 0,
    'st_sol_reserve_value_lamports': None,
    'b_sol_supply_b_lamports': 0,
}
assert result == expected_result, f'Expected {result} to be {expected_result}'
print('> Instance parameters are as expected.')


def perform_maintenance() -> Optional[Dict[str, Any]]:
    return solido(
        'perform-maintenance',
        '--solido-program-id',
        solido_program_id,
        '--solido-address',
        solido_address,
        '--anker-program-id',
        anker_program_id,
        '--stake-time',
        'anytime',
    )


# There shouldn't be any maintenance to perform at this point.
result = perform_maintenance()
assert result is None, f'Did not expect maintenance here, but got {result}'


def deposit_solido_sol(amount_sol: float) -> str:
    """
    Deposit SOL to Solido to get stSOL, return the recipient address.
    """
    deposit_result = solido(
        'deposit',
        '--solido-address',
        solido_address,
        '--solido-program-id',
        solido_program_id,
        '--amount-sol',
        str(amount_sol),
    )
    recipient: str = deposit_result['recipient']
    return recipient


# However, if we donate some stSOL to the reserve, then we should be able to
# sell that.
print('\nDonating 1 stSOL to the Anker reserve ...')
st_sol_account = deposit_solido_sol(1.0)
spl_token(
    'transfer',
    st_sol_mint_address,
    '1',
    anker_st_sol_reserve_account,
    '--from',
    st_sol_account,
)

result = solido('anker', 'show', '--anker-address', anker_address)
assert result['st_sol_reserve_balance_st_lamports'] == 1_000_000_000
print('> Anker stSOL reserve now contains 1 SOL.')

print('\nPerforming maintenance to swap that stSOL for UST ...')
result = perform_maintenance()
assert result == {
    'SellRewards': {
        'st_sol_amount_st_lamports': 1_000_000_000,
    }
}, f'Expected SellRewards, but got {result}'

result = solido('anker', 'show', '--anker-address', anker_address)
assert result['st_sol_reserve_balance_st_lamports'] == 0
# The pool contained 1 stSOL and 1 UST, we doubled the amount of stSOL, so to
# keep the product constant, there is now 0.5 UST in the pool, and the other
# 0.5 UST went to Anker.
assert result['ust_reserve_balance_micro_ust'] == 500_000
print('> Anker stSOL reserve now contains 0.5 UST.')


print('\nDepositing 1 stSOL to Anker ...')
st_sol_account = deposit_solido_sol(1.0)
result = solido(
    'anker',
    'deposit',
    '--anker-address',
    anker_address,
    '--from-st-sol-address',
    st_sol_account,
    '--amount-st-sol',
    '1.0',
)
b_sol_account: str = result['b_sol_account']
assert result['created_associated_b_sol_account'] == True

b_sol_balance = spl_token_balance(b_sol_account)
assert b_sol_balance.balance_raw == 1_000_000_000
print(f'> We now have 1 bSOL in account {b_sol_account}.')
