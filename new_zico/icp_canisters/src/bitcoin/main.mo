import Time "mo:base/Time";
import Map "mo:base/HashMap";
import Principal "mo:base/Principal";
import Text "mo:base/Text";
import Nat "mo:base/Nat";
import Nat64 "mo:base/Nat64";
import Int "mo:base/Int";
import Debug "mo:base/Debug";
import Result "mo:base/Result";
import Array "mo:base/Array";
import Iter "mo:base/Iter";
import Blob "mo:base/Blob";

actor BitcoinService {
  // Types for Bitcoin operations
  public type BitcoinAddress = Text;

  public type UTXO = {
    txid: Text;
    vout: Nat;
    value: Nat64; // in satoshis
    height: ?Nat;
  };

  public type Balance = {
    address: BitcoinAddress;
    balance: Nat64; // in satoshis
    unconfirmed_balance: Nat64;
    final_balance: Nat64;
  };

  public type FeePercentiles = {
    percentile_1: Nat64;
    percentile_5: Nat64;
    percentile_10: Nat64;
    percentile_25: Nat64;
    percentile_50: Nat64;
    percentile_75: Nat64;
    percentile_90: Nat64;
    percentile_95: Nat64;
    percentile_99: Nat64;
  };

  public type P2PKHAddress = {
    address: BitcoinAddress;
    public_key: Text;
  };

  // State storage
  private stable var mock_balances: [(BitcoinAddress, Nat64)] = [];
  // explicitamente transitório (corrige M0219)
  private var balances = Map.HashMap<BitcoinAddress, Nat64>(0, Text.equal, Text.hash);

  // Initialize with some mock data
  system func preupgrade() {
    mock_balances := Iter.toArray(balances.entries());
  };

  system func postupgrade() {
    balances := Map.fromIter<BitcoinAddress, Nat64>(mock_balances.vals(), mock_balances.size(), Text.equal, Text.hash);
    mock_balances := [];

    if (balances.size() == 0) {
      initialize_mock_data();
    };
  };

  private func initialize_mock_data() {
    balances.put("bc1q8sxznvhualuyyes0ded7kgt33876phpjhp29rs", 150000000); // 1.5 BTC
    balances.put("bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh", 50000000);  // 0.5 BTC
    balances.put("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", 25000000); // 0.25 BTC
    balances.put("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 0);              // Genesis address
  };

  // HTTP request handler for API endpoints
  public query func http_request(request: {
    url: Text;
    method: Text;
    body: [Nat8];
    headers: [(Text, Text)];
  }): async {
    status_code: Nat16;
    headers: [(Text, Text)];
    body: [Nat8];
  } {
    let path = extract_path(request.url);
    let response_headers = [
      ("Content-Type", "application/json"),
      ("Access-Control-Allow-Origin", "*"),
      ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
      ("Access-Control-Allow-Headers", "Content-Type, Authorization")
    ];

    switch (request.method, path) {
      case ("GET", "/") {
        let welcome_response = "{\"service\":\"Bitcoin Service\",\"status\":\"running\",\"endpoints\":[\"/get-balance\",\"/get-utxos\",\"/get-current-fee-percentiles\",\"/get-p2pkh-address\"]}";
        {
          status_code = 200;
          headers = response_headers;
          body = Blob.toArray(Text.encodeUtf8(welcome_response));
        }
      };
      case ("POST", "/get-balance") {
        handle_get_balance(request.body, response_headers)
      };
      case ("POST", "/get-utxos") {
        handle_get_utxos(request.body, response_headers)
      };
      case ("GET", "/get-current-fee-percentiles") {
        handle_get_fee_percentiles(response_headers)
      };
      case ("GET", "/get-p2pkh-address") {
        handle_get_p2pkh_address(response_headers)
      };
      case ("OPTIONS", _) {
        { status_code = 200; headers = response_headers; body = Blob.toArray(Text.encodeUtf8("{}")) }
      };
      case (_, _) {
        let error_response = "{\"error\":\"Endpoint not found\",\"available_endpoints\":[\"/get-balance\",\"/get-utxos\",\"/get-current-fee-percentiles\",\"/get-p2pkh-address\"]}";
        {
          status_code = 404;
          headers = response_headers;
          body = Blob.toArray(Text.encodeUtf8(error_response));
        }
      };
    }
  };

  private func extract_path(url: Text): Text {
    let parts = Text.split(url, #char '?');
    switch (parts.next()) {
      case (?path) path;
      case null "/";
    }
  };

  private func handle_get_balance(body: [Nat8], headers: [(Text, Text)]): {
    status_code: Nat16;
    headers: [(Text, Text)];
    body: [Nat8];
  } {
    let body_text = switch (Text.decodeUtf8(Blob.fromArray(body))) {
      case (?text) text;
      case null "";
    };

    let address = extract_address_from_json(body_text);

    switch (address) {
      case (?addr) {
        let balance: Nat64 = switch (balances.get(addr)) { case (?bal) bal; case null 0 };
        let response = "{\"address\":\"" # addr # "\",\"balance\":" # Nat64.toText(balance) # ",\"unconfirmed_balance\":0,\"final_balance\":" # Nat64.toText(balance) # "}";
        { status_code = 200; headers = headers; body = Blob.toArray(Text.encodeUtf8(response)) }
      };
      case null {
        let error_response = "{\"error\":\"Invalid address format or missing address field\"}";
        { status_code = 400; headers = headers; body = Blob.toArray(Text.encodeUtf8(error_response)) }
      };
    }
  };

  private func handle_get_utxos(body: [Nat8], headers: [(Text, Text)]): {
    status_code: Nat16;
    headers: [(Text, Text)];
    body: [Nat8];
  } {
    let body_text = switch (Text.decodeUtf8(Blob.fromArray(body))) { case (?text) text; case null "" };
    let address = extract_address_from_json(body_text);

    switch (address) {
      case (?addr) {
        let mock_utxos = "[{\"txid\":\"abc123def456\",\"vout\":0,\"value\":50000000,\"height\":700000},{\"txid\":\"def456ghi789\",\"vout\":1,\"value\":25000000,\"height\":700001}]";
        let response = "{\"address\":\"" # addr # "\",\"utxos\":" # mock_utxos # "}";
        { status_code = 200; headers = headers; body = Blob.toArray(Text.encodeUtf8(response)) }
      };
      case null {
        let error_response = "{\"error\":\"Invalid address format\"}";
        { status_code = 400; headers = headers; body = Blob.toArray(Text.encodeUtf8(error_response)) }
      };
    }
  };

  private func handle_get_fee_percentiles(headers: [(Text, Text)]): {
    status_code: Nat16;
    headers: [(Text, Text)];
    body: [Nat8];
  } {
    let mock_fees = "{\"percentile_1\":1,\"percentile_5\":2,\"percentile_10\":3,\"percentile_25\":5,\"percentile_50\":8,\"percentile_75\":12,\"percentile_90\":20,\"percentile_95\":30,\"percentile_99\":50}";
    { status_code = 200; headers = headers; body = Blob.toArray(Text.encodeUtf8(mock_fees)) }
  };

  private func handle_get_p2pkh_address(headers: [(Text, Text)]): {
    status_code: Nat16;
    headers: [(Text, Text)];
    body: [Nat8];
  } {
    let mock_address = "{\"address\":\"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\",\"public_key\":\"04678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5f\"}";
    { status_code = 200; headers = headers; body = Blob.toArray(Text.encodeUtf8(mock_address)) }
  };

  // sem Text.indexOf: usa split para achar o valor após "address"
  private func extract_address_from_json(json_text: Text): ?Text {
    let segs = Text.split(json_text, #text "\"address\"");
    ignore segs.next(); // antes da chave
    switch (segs.next()) {
      case null { null };
      case (?tail) {
        // pega o primeiro conteúdo entre aspas após a chave
        let parts = Text.split(tail, #char '\"');
        ignore parts.next(); // até a primeira aspa
        switch (parts.next()) { case (?value) ?value; case null null };
      };
    }
  };

  // Admin
  public shared(msg) func add_mock_balance(address: BitcoinAddress, balance: Nat64): async Result.Result<(), Text> {
    balances.put(address, balance);
    #ok(())
  };

  public query func get_mock_balance(address: BitcoinAddress): async ?Nat64 {
    balances.get(address)
  };

  public query func list_mock_addresses(): async [BitcoinAddress] {
    Array.map<(BitcoinAddress, Nat64), BitcoinAddress>(Iter.toArray(balances.entries()), func((addr, _)) = addr)
  };
}
