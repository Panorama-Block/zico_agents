import Time "mo:base/Time";
import Map "mo:base/HashMap";
import Principal "mo:base/Principal";
import Int "mo:base/Int";
import Nat "mo:base/Nat";
import Nat32 "mo:base/Nat32";
import Debug "mo:base/Debug";
import Result "mo:base/Result";
import Array "mo:base/Array";
import Iter "mo:base/Iter";
import Float "mo:base/Float";
import Text "mo:base/Text";
import Blob "mo:base/Blob";
import Char "mo:base/Char";

actor SwapCanister {
    // Types
    public type Token = {
        #ICP;
        #ckBTC;
        #ckETH;
        #CHAT;
    };

    public type Pair = {
        tokenA: Token;
        tokenB: Token;
    };

    public type Pool = {
        tokenA: Token;
        tokenB: Token;
        reserveA_e8s: Nat;
        reserveB_e8s: Nat;
        fee_bps: Nat;
        total_supply: Nat;
    };

    public type SwapQuote = {
        amount_out_e8s: Nat;
        fee_bps: Nat;
        route: [Text];
        price_impact_bps: Nat;
    };

    public type SwapReceipt = {
        swap_id: Nat;
        owner: Principal;
        pair: Pair;
        amount_in_e8s: Nat;
        amount_out_e8s: Nat;
        fee_e8s: Nat;
        timestamp: Int;
    };

    public type RateView = {
        mid_e8s: Nat;
        fee_bps: Nat;
        spread_bps: Nat;
    };

    public type SwapView = {
        swap_id: Nat;
        when: Int;
        pair: Pair;
        amount_in_e8s: Nat;
        amount_out_e8s: Nat;
        fee_e8s: Nat;
    };

    // State
    private stable var next_swap_id: Nat = 1;
    private stable var pools_stable: [(Text, Pool)] = [];
    private stable var swaps_stable: [(Nat, SwapReceipt)] = [];
    
    private var pools = Map.HashMap<Text, Pool>(0, Text.equal, Text.hash);
    private var swaps = Map.HashMap<Nat, SwapReceipt>(0, Nat.equal, func(x: Nat) : Nat32 { Nat32.fromNat(x) });

    // Initialize pools with some liquidity
    private stable var initialized = false;

    // System lifecycle
    system func preupgrade() {
        pools_stable := Iter.toArray(pools.entries());
        swaps_stable := Iter.toArray(swaps.entries());
    };

    system func postupgrade() {
        pools := Map.fromIter<Text, Pool>(pools_stable.vals(), pools_stable.size(), Text.equal, Text.hash);
        swaps := Map.fromIter<Nat, SwapReceipt>(swaps_stable.vals(), swaps_stable.size(), Nat.equal, func(x: Nat) : Nat32 { Nat32.fromNat(x) });
        pools_stable := [];
        swaps_stable := [];

        if (not initialized) {
            initialize_pools();
            initialized := true;
        };
    };

    // Helper functions
    private func token_to_text(token: Token): Text {
        switch (token) {
            case (#ICP) "ICP";
            case (#ckBTC) "ckBTC";
            case (#ckETH) "ckETH";
            case (#CHAT) "CHAT";
        }
    };

    private func pair_to_key(pair: Pair): Text {
        let tokenA_text = token_to_text(pair.tokenA);
        let tokenB_text = token_to_text(pair.tokenB);
        tokenA_text # "/" # tokenB_text
    };

    private func initialize_pools() {
        // Initialize some basic pools with mock liquidity
        let icp_ckbtc_pool: Pool = {
            tokenA = #ICP;
            tokenB = #ckBTC;
            reserveA_e8s = 1_000_000_000_000; // 10,000 ICP
            reserveB_e8s = 2_500_000_000; // 25 ckBTC (assuming 1 BTC = 4000 ICP ratio)
            fee_bps = 30; // 0.3% fee
            total_supply = 1_000_000_000;
        };

        let icp_cketh_pool: Pool = {
            tokenA = #ICP;
            tokenB = #ckETH;
            reserveA_e8s = 800_000_000_000; // 8,000 ICP
            reserveB_e8s = 300_000_000_000; // 3,000 ETH (assuming 1 ETH = 266 ICP ratio)
            fee_bps = 30;
            total_supply = 800_000_000;
        };

        let icp_chat_pool: Pool = {
            tokenA = #ICP;
            tokenB = #CHAT;
            reserveA_e8s = 500_000_000_000; // 5,000 ICP
            reserveB_e8s = 4_166_666_666_667; // ~41,667 CHAT (assuming 1 ICP = 8.33 CHAT)
            fee_bps = 50; // 0.5% fee for newer token
            total_supply = 500_000_000;
        };

        pools.put(pair_to_key({tokenA = #ICP; tokenB = #ckBTC}), icp_ckbtc_pool);
        pools.put(pair_to_key({tokenA = #ckBTC; tokenB = #ICP}), icp_ckbtc_pool);
        
        pools.put(pair_to_key({tokenA = #ICP; tokenB = #ckETH}), icp_cketh_pool);
        pools.put(pair_to_key({tokenA = #ckETH; tokenB = #ICP}), icp_cketh_pool);
        
        pools.put(pair_to_key({tokenA = #ICP; tokenB = #CHAT}), icp_chat_pool);
        pools.put(pair_to_key({tokenA = #CHAT; tokenB = #ICP}), icp_chat_pool);
    };

    private func calculate_swap_output(pool: Pool, amount_in_e8s: Nat, is_tokenA_to_tokenB: Bool): (Nat, Nat, Nat) {
        let (reserve_in, reserve_out) = if (is_tokenA_to_tokenB) {
            (pool.reserveA_e8s, pool.reserveB_e8s)
        } else {
            (pool.reserveB_e8s, pool.reserveA_e8s)
        };

        // Apply trading fee
        let fee_e8s = (amount_in_e8s * pool.fee_bps) / 10_000;
        let amount_in_after_fee = amount_in_e8s - fee_e8s;

        // Constant product formula: (x + Δx) * (y - Δy) = x * y
        // Δy = (y * Δx) / (x + Δx)
        let numerator = reserve_out * amount_in_after_fee;
        let denominator = reserve_in + amount_in_after_fee;
        let amount_out_e8s = numerator / denominator;

        // Calculate price impact
        let price_before = (reserve_out * 10_000) / reserve_in;
        let new_reserve_in = reserve_in + amount_in_e8s;
        let new_reserve_out = reserve_out - amount_out_e8s;
        let price_after = (new_reserve_out * 10_000) / new_reserve_in;
        let price_impact_bps = if (price_after > price_before) {
            ((price_after - price_before) * 10_000) / price_before
        } else {
            ((price_before - price_after) * 10_000) / price_before
        };

        (amount_out_e8s, fee_e8s, price_impact_bps)
    };

    // Public query methods
    public query func quote(pair: Pair, amount_in_e8s: Nat): async Result.Result<SwapQuote, Text> {
        quote_sync(pair, amount_in_e8s)
    };
    
    private func quote_sync(pair: Pair, amount_in_e8s: Nat): Result.Result<SwapQuote, Text> {
        let key = pair_to_key(pair);
        switch (pools.get(key)) {
            case null #err("Pool not found for pair");
            case (?pool) {
                let is_tokenA_to_tokenB = pool.tokenA == pair.tokenA;
                let (amount_out_e8s, fee_e8s, price_impact_bps) = calculate_swap_output(pool, amount_in_e8s, is_tokenA_to_tokenB);
                
                #ok({
                    amount_out_e8s = amount_out_e8s;
                    fee_bps = pool.fee_bps;
                    route = [token_to_text(pair.tokenA) # "->" # token_to_text(pair.tokenB)];
                    price_impact_bps = price_impact_bps;
                })
            };
        }
    };

    public query func get_rates(pair: Pair): async Result.Result<RateView, Text> {
        get_rates_sync(pair)
    };
    
    private func get_rates_sync(pair: Pair): Result.Result<RateView, Text> {
        let key = pair_to_key(pair);
        switch (pools.get(key)) {
            case null #err("Pool not found for pair");
            case (?pool) {
                let is_tokenA_to_tokenB = pool.tokenA == pair.tokenA;
                let (reserve_in, reserve_out) = if (is_tokenA_to_tokenB) {
                    (pool.reserveA_e8s, pool.reserveB_e8s)
                } else {
                    (pool.reserveB_e8s, pool.reserveA_e8s)
                };

                let mid_rate_e8s = (reserve_out * 100_000_000) / reserve_in;
                
                #ok({
                    mid_e8s = mid_rate_e8s;
                    fee_bps = pool.fee_bps;
                    spread_bps = 10; // Fixed 0.1% spread for simplicity
                })
            };
        }
    };

    public query func list_swaps(user: Principal, cursor: ?Nat): async [SwapView] {
        list_swaps_sync(user, cursor)
    };
    
    private func list_swaps_sync(user: Principal, cursor: ?Nat): [SwapView] {
        let user_swaps = Array.mapFilter<(Nat, SwapReceipt), SwapView>(
            Iter.toArray(swaps.entries()),
            func((id, receipt)) = 
                if (receipt.owner == user) {
                    ?{
                        swap_id = receipt.swap_id;
                        when = receipt.timestamp;
                        pair = receipt.pair;
                        amount_in_e8s = receipt.amount_in_e8s;
                        amount_out_e8s = receipt.amount_out_e8s;
                        fee_e8s = receipt.fee_e8s;
                    }
                } else null
        );

        // Return last 50 swaps (simplified pagination)
        let start_index = switch (cursor) {
            case (?c) if (c < user_swaps.size()) c else 0;
            case null 0;
        };
        
        let end_index = Nat.min(start_index + 50, user_swaps.size());
        if (start_index < end_index) {
            Array.subArray<SwapView>(user_swaps, start_index, end_index - start_index)
        } else {
            []
        }
    };

    // Public update methods
    public shared(msg) func create_swap(pair: Pair, amount_in_e8s: Nat, min_out_e8s: Nat): async Result.Result<SwapReceipt, Text> {
        if (amount_in_e8s == 0) {
            return #err("Amount must be greater than zero");
        };

        let key = pair_to_key(pair);
        switch (pools.get(key)) {
            case null #err("Pool not found for pair");
            case (?pool) {
                let is_tokenA_to_tokenB = pool.tokenA == pair.tokenA;
                let (amount_out_e8s, fee_e8s, price_impact_bps) = calculate_swap_output(pool, amount_in_e8s, is_tokenA_to_tokenB);

                if (amount_out_e8s < min_out_e8s) {
                    return #err("Output amount below minimum acceptable");
                };

                // Update pool reserves
                let updated_pool = if (is_tokenA_to_tokenB) {
                    {
                        pool with
                        reserveA_e8s = pool.reserveA_e8s + amount_in_e8s;
                        reserveB_e8s = pool.reserveB_e8s - amount_out_e8s;
                    }
                } else {
                    {
                        pool with
                        reserveB_e8s = pool.reserveB_e8s + amount_in_e8s;
                        reserveA_e8s = pool.reserveA_e8s - amount_out_e8s;
                    }
                };

                pools.put(key, updated_pool);

                // Record swap
                let swap_id = next_swap_id;
                next_swap_id += 1;

                let receipt: SwapReceipt = {
                    swap_id = swap_id;
                    owner = msg.caller;
                    pair = pair;
                    amount_in_e8s = amount_in_e8s;
                    amount_out_e8s = amount_out_e8s;
                    fee_e8s = fee_e8s;
                    timestamp = Time.now();
                };

                swaps.put(swap_id, receipt);

                #ok(receipt)
            };
        }
    };

    // HTTP facade for REST API access
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
        let headersCORS = [
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type, Authorization")
        ];
        
        // Handle CORS preflight
        if (request.method == "OPTIONS") {
            return {
                status_code = 200;
                headers = headersCORS;
                body = Blob.toArray(Text.encodeUtf8("{}"));
            };
        };
        
        let path = extract_path(request.url);
        let queryParams = parse_query_string(request.url);
        
        switch (path) {
            case ("/") {
                let welcome_response = "{\"service\":\"Swap Service\",\"status\":\"running\",\"endpoints\":[\"/swap/rates\",\"/swap/quote\",\"/swap/history\"]}";
                {
                    status_code = 200;
                    headers = headersCORS;
                    body = Blob.toArray(Text.encodeUtf8(welcome_response));
                }
            };
            case ("/swap/rates") {
                handle_get_rates(queryParams, headersCORS)
            };
            case ("/swap/quote") {
                handle_get_quote(queryParams, headersCORS)
            };
            case ("/swap/history") {
                handle_get_history(queryParams, headersCORS)
            };
            case (_) {
                let error_response = "{\"error\":\"Endpoint not found\",\"available_endpoints\":[\"/swap/rates\",\"/swap/quote\",\"/swap/history\"]}";
                {
                    status_code = 404;
                    headers = headersCORS;
                    body = Blob.toArray(Text.encodeUtf8(error_response));
                }
            };
        }
    };
    
    private func extract_path(url: Text): Text {
        // Extrai path da URL (simplificado)
        let parts = Text.split(url, #char '?');
        switch (parts.next()) {
            case (?path) path;
            case null "/";
        }
    };
    
    private func parse_query_string(url: Text): Map.HashMap<Text, Text> {
        let params = Map.HashMap<Text, Text>(0, Text.equal, Text.hash);
        
        // Procurar por '?' na URL usando Text.contains e Text.split
        let urlParts = Text.split(url, #char '?');
        ignore urlParts.next(); // primeira parte (antes do ?)
        switch (urlParts.next()) {
            case null { params }; // Sem query string
            case (?queryString) {
                let pairs = Text.split(queryString, #char '&');
                
                for (pair in pairs) {
                    let keyValue = Text.split(pair, #char '=');
                    switch (keyValue.next(), keyValue.next()) {
                        case (?key, ?value) {
                            params.put(key, value);
                        };
                        case (_, _) { /* Ignorar pares inválidos */ };
                    };
                };
                params
            };
        }
    };
    
    private func text_to_token(text: Text): ?Token {
        switch (text) {
            case ("ICP") { ?#ICP };
            case ("ckBTC") { ?#ckBTC };
            case ("ckETH") { ?#ckETH };
            case ("CHAT") { ?#CHAT };
            case (_) { null };
        }
    };
    
    private func handle_get_rates(queryParams: Map.HashMap<Text, Text>, headers: [(Text, Text)]): {
        status_code: Nat16;
        headers: [(Text, Text)];
        body: [Nat8];
    } {
        switch (queryParams.get("tokenA"), queryParams.get("tokenB")) {
            case (?tokenAText, ?tokenBText) {
                switch (text_to_token(tokenAText), text_to_token(tokenBText)) {
                    case (?tokenA, ?tokenB) {
                        let pair = { tokenA = tokenA; tokenB = tokenB };
                        switch (get_rates_sync(pair)) {
                            case (#ok(rates)) {
                                let response = debug_show(rates);
                                {
                                    status_code = 200;
                                    headers = headers;
                                    body = Blob.toArray(Text.encodeUtf8(response));
                                }
                            };
                            case (#err(error)) {
                                let error_response = "{\"error\":\"" # error # "\"}";
                                {
                                    status_code = 400;
                                    headers = headers;
                                    body = Blob.toArray(Text.encodeUtf8(error_response));
                                }
                            };
                        };
                    };
                    case (_, _) {
                        let error_response = "{\"error\":\"Invalid token symbols\"}";
                        {
                            status_code = 400;
                            headers = headers;
                            body = Blob.toArray(Text.encodeUtf8(error_response));
                        }
                    };
                };
            };
            case (_, _) {
                let error_response = "{\"error\":\"Missing tokenA and tokenB parameters\"}";
                {
                    status_code = 400;
                    headers = headers;
                    body = Blob.toArray(Text.encodeUtf8(error_response));
                }
            };
        }
    };
    
    private func handle_get_quote(queryParams: Map.HashMap<Text, Text>, headers: [(Text, Text)]): {
        status_code: Nat16;
        headers: [(Text, Text)];
        body: [Nat8];
    } {
        switch (queryParams.get("tokenA"), queryParams.get("tokenB"), queryParams.get("amount_e8s")) {
            case (?tokenAText, ?tokenBText, ?amountText) {
                switch (text_to_token(tokenAText), text_to_token(tokenBText)) {
                    case (?tokenA, ?tokenB) {
                        // Converter amount_e8s para Nat
                        switch (nat_from_text(amountText)) {
                            case (?amount) {
                                let pair = { tokenA = tokenA; tokenB = tokenB };
                                switch (quote_sync(pair, amount)) {
                                    case (#ok(quote_result)) {
                                        let response = debug_show(quote_result);
                                        {
                                            status_code = 200;
                                            headers = headers;
                                            body = Blob.toArray(Text.encodeUtf8(response));
                                        }
                                    };
                                    case (#err(error)) {
                                        let error_response = "{\"error\":\"" # error # "\"}";
                                        {
                                            status_code = 400;
                                            headers = headers;
                                            body = Blob.toArray(Text.encodeUtf8(error_response));
                                        }
                                    };
                                };
                            };
                            case null {
                                let error_response = "{\"error\":\"Invalid amount_e8s parameter\"}";
                                {
                                    status_code = 400;
                                    headers = headers;
                                    body = Blob.toArray(Text.encodeUtf8(error_response));
                                }
                            };
                        };
                    };
                    case (_, _) {
                        let error_response = "{\"error\":\"Invalid token symbols\"}";
                        {
                            status_code = 400;
                            headers = headers;
                            body = Blob.toArray(Text.encodeUtf8(error_response));
                        }
                    };
                };
            };
            case (_, _, _) {
                let error_response = "{\"error\":\"Missing tokenA, tokenB, and amount_e8s parameters\"}";
                {
                    status_code = 400;
                    headers = headers;
                    body = Blob.toArray(Text.encodeUtf8(error_response));
                }
            };
        }
    };
    
    private func handle_get_history(queryParams: Map.HashMap<Text, Text>, headers: [(Text, Text)]): {
        status_code: Nat16;
        headers: [(Text, Text)];
        body: [Nat8];
    } {
        switch (queryParams.get("principal")) {
            case (?principalText) {
                switch (principal_from_text_safe(principalText)) {
                    case (?user) {
                        let limit = switch (queryParams.get("limit")) {
                            case (?limitText) { nat_from_text(limitText) };
                            case null { ?50 };
                        };
                        
                        let user_swaps = list_swaps_sync(user, null);
                        let response = "{\"swaps\":" # debug_show(user_swaps) # "}";
                        
                        {
                            status_code = 200;
                            headers = headers;
                            body = Blob.toArray(Text.encodeUtf8(response));
                        }
                    };
                    case null {
                        let error_response = "{\"error\":\"Invalid principal format\"}";
                        {
                            status_code = 400;
                            headers = headers;
                            body = Blob.toArray(Text.encodeUtf8(error_response));
                        }
                    };
                };
            };
            case null {
                let error_response = "{\"error\":\"Missing principal parameter\"}";
                {
                    status_code = 400;
                    headers = headers;
                    body = Blob.toArray(Text.encodeUtf8(error_response));
                }
            };
        }
    };
    
    private func nat_from_text(text: Text): ?Nat {
        // Implementação simplificada para converter Text para Nat
        // Em produção, usar parser mais robusto
        var result: Nat = 0;
        var multiplier: Nat = 1;
        
        let digits = Text.toArray(text);
        var i = digits.size();
        
        while (i > 0) {
            i -= 1;
            let char = digits[i];
            let charCode = Char.toNat32(char);
            if (charCode >= 48 and charCode <= 57) { // '0' to '9'
                result += Nat32.toNat(charCode - 48) * multiplier;
                multiplier *= 10;
            } else {
                return null; // Caractere inválido
            };
        };
        
        ?result
    };
    
    private func principal_from_text_safe(text: Text): ?Principal {
        // Implementação simplificada para converter texto para Principal
        // Em produção, usar bibliotecas mais robustas
        // Verificação básica de formato antes de tentar converter
        if (Text.size(text) < 5) {
            return null;
        };
        
        // Tentativa de conversão com verificação de padrão básico
        if (Text.contains(text, #char '-')) {
            // Formato esperado de Principal contém hífens
            ?Principal.fromText(text)
        } else {
            null
        }
    };

    // Admin functions
    public shared(msg) func add_liquidity(pair: Pair, amountA_e8s: Nat, amountB_e8s: Nat): async Result.Result<Nat, Text> {
        // Simplified liquidity addition (in production, would need proper LP token logic)
        let key = pair_to_key(pair);
        switch (pools.get(key)) {
            case null {
                let new_pool: Pool = {
                    tokenA = pair.tokenA;
                    tokenB = pair.tokenB;
                    reserveA_e8s = amountA_e8s;
                    reserveB_e8s = amountB_e8s;
                    fee_bps = 30; // Default 0.3%
                    total_supply = Nat.min(amountA_e8s, amountB_e8s);
                };
                pools.put(key, new_pool);
                #ok(new_pool.total_supply)
            };
            case (?existing_pool) {
                let updated_pool = {
                    existing_pool with
                    reserveA_e8s = existing_pool.reserveA_e8s + amountA_e8s;
                    reserveB_e8s = existing_pool.reserveB_e8s + amountB_e8s;
                };
                pools.put(key, updated_pool);
                #ok(Nat.min(amountA_e8s, amountB_e8s))
            };
        }
    };

    // Initialize on deploy when needed
}
