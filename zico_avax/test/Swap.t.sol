// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import {Test, console} from "forge-std/Test.sol";
import {Swap} from "../src/Swap.sol";

contract SwapTest is Test {
    Swap public swap;

    function setUp() public {
        swap = new Swap();
    }

    // Esse teste é só pra mostrar que o contrato foi implantado corretamente
    function testContractDeployment() public {
        assertEq(address(swap) != address(0), true);
    }

    // Valida que a função getTokenAddresses retorna corretamente sem revert
    function testGetTokenAddresses() public {
        (address tokenA, address tokenB) = swap.getTokenAddresses("AVAX/USD");
        console.log("Token A:", tokenA);
        console.log("Token B:", tokenB);
        assertTrue(tokenA != address(0) && tokenB != address(0));
    }

    // Teste que espera erro ao passar par inválido
    function testGetTokenAddressesInvalidPair() public {
        vm.expectRevert(bytes("Unknown Pair"));
        swap.getTokenAddresses("INVALID/PAIR");
    }
}
