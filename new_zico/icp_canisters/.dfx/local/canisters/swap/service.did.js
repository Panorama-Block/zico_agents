export const idlFactory = ({ IDL }) => {
  const Token = IDL.Variant({
    'ICP' : IDL.Null,
    'CHAT' : IDL.Null,
    'ckBTC' : IDL.Null,
    'ckETH' : IDL.Null,
  });
  const Pair = IDL.Record({ 'tokenA' : Token, 'tokenB' : Token });
  const Result_3 = IDL.Variant({ 'ok' : IDL.Nat, 'err' : IDL.Text });
  const SwapReceipt = IDL.Record({
    'amount_out_e8s' : IDL.Nat,
    'owner' : IDL.Principal,
    'pair' : Pair,
    'fee_e8s' : IDL.Nat,
    'swap_id' : IDL.Nat,
    'timestamp' : IDL.Int,
    'amount_in_e8s' : IDL.Nat,
  });
  const Result_2 = IDL.Variant({ 'ok' : SwapReceipt, 'err' : IDL.Text });
  const RateView = IDL.Record({
    'spread_bps' : IDL.Nat,
    'fee_bps' : IDL.Nat,
    'mid_e8s' : IDL.Nat,
  });
  const Result_1 = IDL.Variant({ 'ok' : RateView, 'err' : IDL.Text });
  const SwapView = IDL.Record({
    'amount_out_e8s' : IDL.Nat,
    'pair' : Pair,
    'when' : IDL.Int,
    'fee_e8s' : IDL.Nat,
    'swap_id' : IDL.Nat,
    'amount_in_e8s' : IDL.Nat,
  });
  const SwapQuote = IDL.Record({
    'amount_out_e8s' : IDL.Nat,
    'price_impact_bps' : IDL.Nat,
    'fee_bps' : IDL.Nat,
    'route' : IDL.Vec(IDL.Text),
  });
  const Result = IDL.Variant({ 'ok' : SwapQuote, 'err' : IDL.Text });
  return IDL.Service({
    'add_liquidity' : IDL.Func([Pair, IDL.Nat, IDL.Nat], [Result_3], []),
    'create_swap' : IDL.Func([Pair, IDL.Nat, IDL.Nat], [Result_2], []),
    'get_rates' : IDL.Func([Pair], [Result_1], ['query']),
    'http_request' : IDL.Func(
        [
          IDL.Record({
            'url' : IDL.Text,
            'method' : IDL.Text,
            'body' : IDL.Vec(IDL.Nat8),
            'headers' : IDL.Vec(IDL.Tuple(IDL.Text, IDL.Text)),
          }),
        ],
        [
          IDL.Record({
            'body' : IDL.Vec(IDL.Nat8),
            'headers' : IDL.Vec(IDL.Tuple(IDL.Text, IDL.Text)),
            'status_code' : IDL.Nat16,
          }),
        ],
        ['query'],
      ),
    'list_swaps' : IDL.Func(
        [IDL.Principal, IDL.Opt(IDL.Nat)],
        [IDL.Vec(SwapView)],
        ['query'],
      ),
    'quote' : IDL.Func([Pair, IDL.Nat], [Result], ['query']),
  });
};
export const init = ({ IDL }) => { return []; };
