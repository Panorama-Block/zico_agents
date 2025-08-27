// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "forge-std/Script.sol";
import "../src/Analysis.sol";
import "../src/Swap.sol";
import "../src/Validation.sol";

contract DeployScript is Script {
    function run() external {
        vm.startBroadcast();

        Analysis analysis = new Analysis();
        console.log("Analysis deployed at:", address(analysis));

        Swap swap = new Swap();
        console.log("Swap deployed at:", address(swap));

        Validation validation = new Validation();
        console.log("Validation deployed at:", address(validation));

        vm.stopBroadcast();
    }
}
