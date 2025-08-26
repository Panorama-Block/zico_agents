// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "forge-std/Test.sol";
import "../src/Validation.sol"; 

contract ValidationTest is Test {
    Validation validation;
    address owner = address(0xABCD);
    address user = address(0x1234);

    function setUp() public {
        vm.prank(owner);
        validation = new Validation(10); 
    }

    function testInitialTaxRate() public {
        assertEq(validation.taxRate(), 10);
        assertEq(validation.owner(), owner);
    }

    function testSetTaxRateByOwner() public {
        vm.prank(owner);
        validation.setTaxRate(20);
        assertEq(validation.taxRate(), 20);
    }

    function testCalculateValue() public {
        uint amount = 1000;
        uint tax = validation.calculateValue(amount);
        assertEq(tax, 100); 
    }

    function testPayAndValidate() public {
        vm.deal(user, 1 ether);

        vm.prank(user);
        uint rest = validation.payAndValidate{value: 1 ether}();

        uint expectedTax = (1 ether * 10) / 100;
        uint expectedRest = 1 ether - expectedTax;

        assertEq(rest, expectedRest);
        assertEq(owner.balance, expectedTax);
        assertEq(user.balance, expectedRest);
    }

    function testWithdrawNoFunds() public {
        uint balanceBefore = owner.balance;

        vm.prank(owner);
        validation.withdraw();

        uint balanceAfter = owner.balance;
        assertEq(balanceAfter, balanceBefore);
    }


    function test_RevertWhen_NotOwnerSetsTaxRate() public {
    vm.prank(user);
    vm.expectRevert("Not authorized");
    validation.setTaxRate(20);
    }

    function test_RevertWhen_PayAndValidateWithoutValue() public {
        vm.prank(user);
        vm.expectRevert("No AVAX sent");
        validation.payAndValidate();
    }

    function test_RevertWhen_NotOwnerWithdraws() public {
        vm.prank(user);
        vm.expectRevert("Not authorized");
        validation.withdraw();
    }

}
