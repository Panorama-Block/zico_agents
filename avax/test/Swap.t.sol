// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import {Swap} from "../src/Swap.sol";

contract SwapTest is Test {
    Swap public swap;

    function setUp() public {
        swap = new Swap();
    }

    function testGetMediumPriceAVAX() public view {
        uint price = swap.getMediumPrice("AVAX/USD");
        console.log("AVAX/USD Price:", price);
        assertGt(price, 0);
    }

    function testGetMediumPriceInvalidPair() public {
        vm.expectRevert(bytes("Pair not found"));
        swap.getMediumPrice("INVALID/PAIR");
    }
}