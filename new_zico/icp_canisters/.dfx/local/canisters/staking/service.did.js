export const idlFactory = ({ IDL }) => {
  const Token = IDL.Variant({
    'ICP' : IDL.Null,
    'CHAT' : IDL.Null,
    'ckBTC' : IDL.Null,
    'ckETH' : IDL.Null,
  });
  const StakeView = IDL.Record({
    'token' : Token,
    'stake_id' : IDL.Nat,
    'reward_rate_bps' : IDL.Nat,
    'amount_e8s' : IDL.Nat,
    'start_time' : IDL.Int,
    'withdrawable' : IDL.Bool,
    'duration_s' : IDL.Nat,
    'accumulated_reward_e8s' : IDL.Nat,
  });
  const StakingParams = IDL.Record({
    'reward_rates' : IDL.Vec(IDL.Tuple(Token, IDL.Nat)),
    'min_stake_amount_e8s' : IDL.Nat,
    'min_duration_s' : IDL.Nat,
    'max_duration_s' : IDL.Nat,
  });
  const Result_2 = IDL.Variant({ 'ok' : IDL.Null, 'err' : IDL.Text });
  const StakeResult = IDL.Record({
    'stake_id' : IDL.Nat,
    'started_at' : IDL.Int,
  });
  const Result_1 = IDL.Variant({ 'ok' : StakeResult, 'err' : IDL.Text });
  const WithdrawResult = IDL.Record({
    'reward_e8s' : IDL.Nat,
    'principal_returned_e8s' : IDL.Nat,
  });
  const Result = IDL.Variant({ 'ok' : WithdrawResult, 'err' : IDL.Text });
  return IDL.Service({
    'get_stake_status' : IDL.Func(
        [IDL.Opt(IDL.Principal)],
        [IDL.Opt(IDL.Record({ 'stakes' : IDL.Vec(StakeView) }))],
        ['query'],
      ),
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
    'params' : IDL.Func([], [StakingParams], ['query']),
    'set_params' : IDL.Func([StakingParams], [Result_2], []),
    'start_staking' : IDL.Func([IDL.Nat, IDL.Nat], [Result_1], []),
    'withdraw_stake' : IDL.Func([IDL.Nat], [Result], []),
  });
};
export const init = ({ IDL }) => { return []; };
