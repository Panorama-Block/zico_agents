import type { Principal } from '@dfinity/principal';
import type { ActorMethod } from '@dfinity/agent';
import type { IDL } from '@dfinity/candid';

export type Result = { 'ok' : WithdrawResult } |
  { 'err' : string };
export type Result_1 = { 'ok' : StakeResult } |
  { 'err' : string };
export type Result_2 = { 'ok' : null } |
  { 'err' : string };
export interface StakeResult { 'stake_id' : bigint, 'started_at' : bigint }
export interface StakeView {
  'token' : Token,
  'stake_id' : bigint,
  'reward_rate_bps' : bigint,
  'amount_e8s' : bigint,
  'start_time' : bigint,
  'withdrawable' : boolean,
  'duration_s' : bigint,
  'accumulated_reward_e8s' : bigint,
}
export interface StakingParams {
  'reward_rates' : Array<[Token, bigint]>,
  'min_stake_amount_e8s' : bigint,
  'min_duration_s' : bigint,
  'max_duration_s' : bigint,
}
export type Token = { 'ICP' : null } |
  { 'CHAT' : null } |
  { 'ckBTC' : null } |
  { 'ckETH' : null };
export interface WithdrawResult {
  'reward_e8s' : bigint,
  'principal_returned_e8s' : bigint,
}
export interface _SERVICE {
  'get_stake_status' : ActorMethod<
    [[] | [Principal]],
    [] | [{ 'stakes' : Array<StakeView> }]
  >,
  'http_request' : ActorMethod<
    [
      {
        'url' : string,
        'method' : string,
        'body' : Uint8Array | number[],
        'headers' : Array<[string, string]>,
      },
    ],
    {
      'body' : Uint8Array | number[],
      'headers' : Array<[string, string]>,
      'status_code' : number,
    }
  >,
  'params' : ActorMethod<[], StakingParams>,
  'set_params' : ActorMethod<[StakingParams], Result_2>,
  'start_staking' : ActorMethod<[bigint, bigint], Result_1>,
  'withdraw_stake' : ActorMethod<[bigint], Result>,
}
export declare const idlFactory: IDL.InterfaceFactory;
export declare const init: (args: { IDL: typeof IDL }) => IDL.Type[];
