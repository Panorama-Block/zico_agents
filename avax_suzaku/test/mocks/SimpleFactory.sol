// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: Copyright 2024 Symbiotic
pragma solidity 0.8.25;

import {Factory} from "src/contracts/Factory.sol";

contract SimpleFactory is Factory {
    function create() external returns (address) {
        _addEntity(msg.sender);
        return msg.sender;
    }
}
