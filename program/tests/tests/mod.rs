// SPDX-FileCopyrightText: 2021 Chorus One AG
// SPDX-License-Identifier: GPL-3.0

#![cfg(feature = "test-bpf")]

pub mod add_remove_validator;
pub mod change_reward_distribution;
pub mod deposit;
pub mod limits;
pub mod maintainers;
pub mod merge_stake;
pub mod solana_assumptions;
pub mod stake_deposit;
pub mod unstake;
pub mod update_exchange_rate;
pub mod update_stake_account_balance;
pub mod validators_curation;
pub mod withdrawals;
