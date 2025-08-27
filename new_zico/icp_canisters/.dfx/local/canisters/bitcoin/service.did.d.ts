import type { Principal } from '@dfinity/principal';
import type { ActorMethod } from '@dfinity/agent';
import type { IDL } from '@dfinity/candid';

export type BitcoinAddress = string;
export type Result = { 'ok' : null } |
  { 'err' : string };
export interface _SERVICE {
  'add_mock_balance' : ActorMethod<[BitcoinAddress, bigint], Result>,
  'get_mock_balance' : ActorMethod<[BitcoinAddress], [] | [bigint]>,
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
  'list_mock_addresses' : ActorMethod<[], Array<BitcoinAddress>>,
}
export declare const idlFactory: IDL.InterfaceFactory;
export declare const init: (args: { IDL: typeof IDL }) => IDL.Type[];
