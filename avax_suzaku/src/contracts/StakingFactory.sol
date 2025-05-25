// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {Factory} from "./Factory.sol";
import {SuzakuStaking} from "./Staking.sol";
import {Clones} from "@openzeppelin/contracts/proxy/Clones.sol";

contract StakingFactory is Factory {
    using Clones for address;

    address private immutable STAKING_IMPLEMENTATION;

    constructor() {
        STAKING_IMPLEMENTATION = address(new SuzakuStaking(address(0))); // Deploy implementation
    }

    function create(address asset) external returns (address) {
        address staking = STAKING_IMPLEMENTATION.clone();
        SuzakuStaking(staking).initialize(asset); // Initialize the proxy
        
        _addEntity(staking);
        
        return staking;
    }
} 