// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "forge-std/Script.sol";
import "../src/Analysis.sol";
import "../src/Swap.sol";

contract DeployScript is Script {
    function run() external {
        vm.startBroadcast();

        Analysis analysis = new Analysis();
        console.log("Analysis deployed at:", address(analysis));

        Swap swap = new Swap();
        console.log("Swap deployed at:", address(swap));

        vm.stopBroadcast();
    }
}
