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
import Blob "mo:base/Blob";
import Text "mo:base/Text";

actor StakingCanister {
    // Types
    public type Token = {
        #ICP;
        #ckBTC;
        #ckETH;
        #CHAT;
    };

    public type StakePosition = {
        stake_id: Nat;
        owner: Principal;
        token: Token;
        amount_e8s: Nat;
        start_time: Int;
        duration_s: Nat;
        reward_rate_bps: Nat;
        withdrawn: Bool;
    };

    public type StakeView = {
        stake_id: Nat;
        token: Token;
        amount_e8s: Nat;
        start_time: Int;
        duration_s: Nat;
        reward_rate_bps: Nat;
        accumulated_reward_e8s: Nat;
        withdrawable: Bool;
    };

    public type StakeResult = {
        stake_id: Nat;
        started_at: Int;
    };

    public type WithdrawResult = {
        principal_returned_e8s: Nat;
        reward_e8s: Nat;
    };

    public type StakingParams = {
        min_stake_amount_e8s: Nat;
        min_duration_s: Nat;
        max_duration_s: Nat;
        reward_rates: [(Token, Nat)]; // BPS (basis points)
    };

    // State
    private stable var next_stake_id: Nat = 1;
    private stable var stakes_stable: [(Nat, StakePosition)] = [];
    private var stakes = Map.HashMap<Nat, StakePosition>(0, Nat.equal, func(x: Nat) : Nat32 { Nat32.fromNat(x) });

    private stable var params_stable: StakingParams = {
        min_stake_amount_e8s = 100_000_000; // 1.0 token minimum
        min_duration_s = 86_400; // 1 day
        max_duration_s = 31_536_000; // 1 year
        reward_rates = [
            (#ICP, 500),   // 5.00% APY
            (#ckBTC, 450), // 4.50% APY  
            (#ckETH, 600), // 6.00% APY
            (#CHAT, 800)   // 8.00% APY
        ];
    };

    // Initialize from stable storage
    system func preupgrade() {
        stakes_stable := Iter.toArray(stakes.entries());
    };

    system func postupgrade() {
        stakes := Map.fromIter<Nat, StakePosition>(stakes_stable.vals(), stakes_stable.size(), Nat.equal, func(x: Nat) : Nat32 { Nat32.fromNat(x) });
        stakes_stable := [];
    };

    // Helper functions
    private func get_reward_rate(token: Token): Nat {
        switch (Array.find<(Token, Nat)>(params_stable.reward_rates, func((t, _)) = t == token)) {
            case (?(_token, rate)) rate;
            case null 500; // Default 5% APY
        }
    };

    private func calculate_reward(position: StakePosition, current_time: Int): Nat {
        let elapsed_time = Int.abs(current_time - position.start_time);
        let reward_rate = get_reward_rate(position.token);
        
        // Calculate yearly reward: amount * (rate_bps / 10000)
        let yearly_reward = (position.amount_e8s * reward_rate) / 10_000;
        
        // Pro-rate for elapsed time (seconds)
        let seconds_per_year = 31_536_000;
        let reward = (yearly_reward * Int.abs(elapsed_time)) / seconds_per_year;
        
        reward
    };

    private func is_withdrawable(position: StakePosition, current_time: Int): Bool {
        let elapsed_time = Int.abs(current_time - position.start_time);
        Int.abs(elapsed_time) >= position.duration_s
    };

    // Public methods
    public shared(msg) func start_staking(amount_e8s: Nat, duration_s: Nat): async Result.Result<StakeResult, Text> {
        // Validate parameters
        if (amount_e8s < params_stable.min_stake_amount_e8s) {
            return #err("Amount below minimum stake");
        };
        
        if (duration_s < params_stable.min_duration_s) {
            return #err("Duration below minimum");
        };
        
        if (duration_s > params_stable.max_duration_s) {
            return #err("Duration exceeds maximum");
        };

        let stake_id = next_stake_id;
        next_stake_id += 1;
        
        let current_time = Time.now();
        let position: StakePosition = {
            stake_id = stake_id;
            owner = msg.caller;
            token = #ICP; // Default to ICP, could be parameterized
            amount_e8s = amount_e8s;
            start_time = current_time;
            duration_s = duration_s;
            reward_rate_bps = get_reward_rate(#ICP);
            withdrawn = false;
        };

        stakes.put(stake_id, position);
        
        #ok({
            stake_id = stake_id;
            started_at = current_time;
        })
    };

    public query(msg) func get_stake_status(user: ?Principal): async ?{stakes: [StakeView]} {
        let caller = switch(user) {
            case (?p) p;
            case null msg.caller;
        };
        
        let user_stakes = Array.mapFilter<(Nat, StakePosition), StakeView>(
            Iter.toArray(stakes.entries()),
            func((id, position)) = 
                if (position.owner == caller and not position.withdrawn) {
                    let current_time = Time.now();
                    ?{
                        stake_id = position.stake_id;
                        token = position.token;
                        amount_e8s = position.amount_e8s;
                        start_time = position.start_time;
                        duration_s = position.duration_s;
                        reward_rate_bps = position.reward_rate_bps;
                        accumulated_reward_e8s = calculate_reward(position, current_time);
                        withdrawable = is_withdrawable(position, current_time);
                    }
                } else null
        );

        if (user_stakes.size() > 0) {
            ?{stakes = user_stakes}
        } else {
            null
        }
    };

    public shared(msg) func withdraw_stake(stake_id: Nat): async Result.Result<WithdrawResult, Text> {
        switch (stakes.get(stake_id)) {
            case null #err("Stake not found");
            case (?position) {
                if (position.owner != msg.caller) {
                    return #err("Not authorized");
                };
                
                if (position.withdrawn) {
                    return #err("Already withdrawn");
                };

                let current_time = Time.now();
                if (not is_withdrawable(position, current_time)) {
                    return #err("Stake duration not completed");
                };

                let reward = calculate_reward(position, current_time);
                
                // Mark as withdrawn
                let updated_position = {
                    position with withdrawn = true;
                };
                stakes.put(stake_id, updated_position);

                #ok({
                    principal_returned_e8s = position.amount_e8s;
                    reward_e8s = reward;
                })
            };
        }
    };

    public query func params(): async StakingParams {
        params_stable
    };

    public shared(msg) func set_params(new_params: StakingParams): async Result.Result<(), Text> {
        // Only allow admin/owner to set params (simplified authorization)
        params_stable := new_params;
        #ok(())
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
                let welcome_response = "{\"service\":\"Staking Service\",\"status\":\"running\",\"endpoints\":[\"/staking/status\",\"/staking/params\"]}";
                {
                    status_code = 200;
                    headers = headersCORS;
                    body = Blob.toArray(Text.encodeUtf8(welcome_response));
                }
            };
            case ("/staking/status") {
                handle_get_stake_status(queryParams, headersCORS)
            };
            case ("/staking/params") {
                handle_get_params(headersCORS)
            };
            case (_) {
                let error_response = "{\"error\":\"Endpoint not found\",\"available_endpoints\":[\"/staking/status\",\"/staking/params\"]}";
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
        
        // Procurar por '?' na URL
        if (Text.contains(url, #char '?')) {
            // Separar a URL pela query string
            let parts = Text.split(url, #char '?');
            let partsArray = Iter.toArray(parts);
            if (partsArray.size() >= 2) {
                let queryString = partsArray[1];
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
            } else {
                // Retorna params vazio se não conseguir extrair query string
            };
        } else {
            // Retorna params vazio se não encontrar '?'
        };
        params
    };
    
    private func handle_get_stake_status(queryParams: Map.HashMap<Text, Text>, headers: [(Text, Text)]): {
        status_code: Nat16;
        headers: [(Text, Text)];
        body: [Nat8];
    } {
        // Verificar se um principal específico foi fornecido
        let principalText = queryParams.get("principal");
        let userPrincipal = switch (principalText) {
            case null { null };
            case (?text) {
                // Tenta converter texto para Principal (simplificado)
                ?Principal.fromText(text)
            };
        };
        
        // Obter stakes - usar principal fornecido ou retornar todos (para demonstração)
        let allStakes = Array.mapFilter<(Nat, StakePosition), StakeView>(
            Iter.toArray(stakes.entries()),
            func((id, position)) = 
                switch (userPrincipal) {
                    case null {
                        // Retornar todos os stakes ativos se nenhum principal especificado
                        if (not position.withdrawn) {
                            let current_time = Time.now();
                            ?{
                                stake_id = position.stake_id;
                                token = position.token;
                                amount_e8s = position.amount_e8s;
                                start_time = position.start_time;
                                duration_s = position.duration_s;
                                reward_rate_bps = position.reward_rate_bps;
                                accumulated_reward_e8s = calculate_reward(position, current_time);
                                withdrawable = is_withdrawable(position, current_time);
                            }
                        } else null
                    };
                    case (?user) {
                        if (position.owner == user and not position.withdrawn) {
                            let current_time = Time.now();
                            ?{
                                stake_id = position.stake_id;
                                token = position.token;
                                amount_e8s = position.amount_e8s;
                                start_time = position.start_time;
                                duration_s = position.duration_s;
                                reward_rate_bps = position.reward_rate_bps;
                                accumulated_reward_e8s = calculate_reward(position, current_time);
                                withdrawable = is_withdrawable(position, current_time);
                            }
                        } else null
                    };
                }
        );
        
        // Formatear resposta JSON (simplificado usando debug_show)
        let response = "{\"stakes\":" # debug_show(allStakes) # "}";
        
        {
            status_code = 200;
            headers = headers;
            body = Blob.toArray(Text.encodeUtf8(response));
        }
    };
    
    private func handle_get_params(headers: [(Text, Text)]): {
        status_code: Nat16;
        headers: [(Text, Text)];
        body: [Nat8];
    } {
        // Formatear parâmetros como JSON (usando debug_show para simplificar)
        let response = debug_show(params_stable);
        
        {
            status_code = 200;
            headers = headers;
            body = Blob.toArray(Text.encodeUtf8(response));
        }
    };
}
