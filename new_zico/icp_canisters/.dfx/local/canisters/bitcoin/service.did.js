export const idlFactory = ({ IDL }) => {
  const BitcoinAddress = IDL.Text;
  const Result = IDL.Variant({ 'ok' : IDL.Null, 'err' : IDL.Text });
  return IDL.Service({
    'add_mock_balance' : IDL.Func([BitcoinAddress, IDL.Nat64], [Result], []),
    'get_mock_balance' : IDL.Func(
        [BitcoinAddress],
        [IDL.Opt(IDL.Nat64)],
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
    'list_mock_addresses' : IDL.Func([], [IDL.Vec(BitcoinAddress)], ['query']),
  });
};
export const init = ({ IDL }) => { return []; };
