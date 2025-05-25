// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.25;

import {Script} from "forge-std/Script.sol";

import {IDefaultCollateralFactory} from "src/interfaces/defaultCollateral/IDefaultCollateralFactory.sol";

contract DefaultCollateralScript is Script {
    function run() external {
        // Get deployment parameters from the environment
        address collateralFactory = vm.envAddress("COLLATERAL_FACTORY");
        address collateralAsset = vm.envAddress("COLLATERAL_ASSET");
        uint256 collateralInitLimit = vm.envUint("COLLATERAL_INIT_LIMIT");
        address collateralLimitIncreaser = vm.envAddress(
            "COLLATERAL_LIMIT_INCREASER"
        );

        vm.startBroadcast();

        IDefaultCollateralFactory(collateralFactory).create(
            collateralAsset,
            collateralInitLimit,
            collateralLimitIncreaser
        );

        vm.stopBroadcast();
    }
}
