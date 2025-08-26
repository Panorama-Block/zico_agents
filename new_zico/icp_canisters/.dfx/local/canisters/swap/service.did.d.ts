import type { Principal } from '@dfinity/principal';
import type { ActorMethod } from '@dfinity/agent';
import type { IDL } from '@dfinity/candid';

export interface Pair { 'tokenA' : Token, 'tokenB' : Token }
export interface RateView {
  'spread_bps' : bigint,
  'fee_bps' : bigint,
  'mid_e8s' : bigint,
}
export type Result = { 'ok' : SwapQuote } |
  { 'err' : string };
export type Result_1 = { 'ok' : RateView } |
  { 'err' : string };
export type Result_2 = { 'ok' : SwapReceipt } |
  { 'err' : string };
export type Result_3 = { 'ok' : bigint } |
  { 'err' : string };
export interface SwapQuote {
  'amount_out_e8s' : bigint,
  'price_impact_bps' : bigint,
  'fee_bps' : bigint,
  'route' : Array<string>,
}
export interface SwapReceipt {
  'amount_out_e8s' : bigint,
  'owner' : Principal,
  'pair' : Pair,
  'fee_e8s' : bigint,
  'swap_id' : bigint,
  'timestamp' : bigint,
  'amount_in_e8s' : bigint,
}
export interface SwapView {
  'amount_out_e8s' : bigint,
  'pair' : Pair,
  'when' : bigint,
  'fee_e8s' : bigint,
  'swap_id' : bigint,
  'amount_in_e8s' : bigint,
}
export type Token = { 'ICP' : null } |
  { 'CHAT' : null } |
  { 'ckBTC' : null } |
  { 'ckETH' : null };
export interface _SERVICE {
  'add_liquidity' : ActorMethod<[Pair, bigint, bigint], Result_3>,
  'create_swap' : ActorMethod<[Pair, bigint, bigint], Result_2>,
  'get_rates' : ActorMethod<[Pair], Result_1>,
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
  'list_swaps' : ActorMethod<[Principal, [] | [bigint]], Array<SwapView>>,
  'quote' : ActorMethod<[Pair, bigint], Result>,
}
export declare const idlFactory: IDL.InterfaceFactory;
export declare const init: (args: { IDL: typeof IDL }) => IDL.Type[];
