// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import {Analysis} from "../src/Analysis.sol";

contract AnalysisTest is Test {
    Analysis public analysis;

    function setUp() public {
        analysis = new Analysis();
    }

    function testGetTokenAddressesValid() public view {
        (address tokenA, address tokenB) = analysis.getTokenAddresses("AVAX/USD");
        assertEq(tokenA, 0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7);
        assertEq(tokenB, 0xA7D7079b0FEaD91F3e65f86E8915Cb59c1a4C664);
    }

    function testGetTokenAddressesInvalidReverts() public {
        vm.expectRevert("Unknown Pair");
        analysis.getTokenAddresses("INVALID/PAIR");
    }

    function testBalanceInitialZero() public view {
        uint bal = analysis.balance();
        assertEq(bal, 0);
    }
}
