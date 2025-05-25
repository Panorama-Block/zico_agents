// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {Test} from "forge-std/Test.sol";
import {SuzakuRestaking} from "src/contracts/Restaking.sol";
import {MockERC20} from "./mocks/MockERC20.sol";
import {FeeOnTransferToken} from "./mocks/FeeOnTransferToken.sol";

contract RestakingTest is Test {
    address public constant DEAD = 0x000000000000000000000000000000000000dEaD;
    
    uint256 public alicePrivateKey;
    uint256 public bobPrivateKey;
    address public alice;
    address public bob;
    
    SuzakuRestaking public restakingToken;
    MockERC20 public token;
    FeeOnTransferToken public feeOnTransferToken;
    
    function setUp() public {
        alicePrivateKey = 0xA11CE;
        bobPrivateKey = 0xB0B;
        alice = vm.addr(alicePrivateKey);
        bob = vm.addr(bobPrivateKey);
        
        // Deploy tokens
        token = new MockERC20("Test Token", "TST");
        feeOnTransferToken = new FeeOnTransferToken("Fee Token");
        
        // Deploy restaking contract
        restakingToken = new SuzakuRestaking(address(token));
        
        // Transfer tokens to test accounts
        token.transfer(alice, 1000 * 1e18);
        token.transfer(bob, 1000 * 1e18);
        feeOnTransferToken.transfer(alice, 1000 * 1e18);
        feeOnTransferToken.transfer(bob, 1000 * 1e18);
        
        // Approve tokens
        vm.startPrank(alice);
        token.approve(address(restakingToken), type(uint256).max);
        feeOnTransferToken.approve(address(restakingToken), type(uint256).max);
        vm.stopPrank();
        
        vm.startPrank(bob);
        token.approve(address(restakingToken), type(uint256).max);
        feeOnTransferToken.approve(address(restakingToken), type(uint256).max);
        vm.stopPrank();
    }
    
    function test_InitialDeposit(uint256 amount) public {
        amount = bound(amount, 1e18, 100 * 1e18);
        
        vm.startPrank(alice);
        uint256 depositedAmount = restakingToken.deposit(alice, amount);
        vm.stopPrank();
        
        assertEq(depositedAmount, amount);
        (uint256 stakedAmount, uint256 startTime, , , uint256 restakeCount, uint256 totalRestaked) = restakingToken.getStakeInfo(alice);
        assertEq(stakedAmount, amount);
        assertEq(startTime, block.timestamp);
        assertEq(restakeCount, 0);
        assertEq(totalRestaked, 0);
    }
    
    function test_Restake(uint256 amount) public {
        amount = bound(amount, 1e18, 100 * 1e18);
        
        // Initial deposit
        vm.startPrank(alice);
        restakingToken.deposit(alice, amount);
        
        // Advance time to accumulate rewards
        vm.warp(block.timestamp + 60 days);
        
        // Calculate expected rewards with no bonus
        uint256 baseRewards = restakingToken.calculatePendingRewards(alice);
        assertTrue(baseRewards > 0, "Should have base rewards");
        
        // Perform restake
        restakingToken.restake();
        
        // Check updated stake info
        (uint256 newStakedAmount, , , , uint256 newRestakeCount, uint256 newTotalRestaked) = restakingToken.getStakeInfo(alice);
        assertEq(newStakedAmount, amount + baseRewards);
        assertEq(newRestakeCount, 1);
        assertEq(newTotalRestaked, baseRewards);
        vm.stopPrank();
    }
    
    function test_RestakeWithBonus() public {
        uint256 amount = 100 * 1e18;
        
        vm.startPrank(alice);
        restakingToken.deposit(alice, amount);
        
        // Perform multiple restakes with time advancement
        for(uint256 i = 0; i < 3; i++) {
            // Advance time between restakes
            vm.warp(block.timestamp + 45 days);
            
            (uint256 preRestakeBalance,,,,,) = restakingToken.getStakeInfo(alice);
            uint256 expectedRewards = restakingToken.calculatePendingRewards(alice);
            
            // Calculate bonus (0.5% per previous restake)
            uint256 bonus = (expectedRewards * i * 50) / 10000;
            uint256 totalExpectedRewards = expectedRewards + bonus;
            
            restakingToken.restake();
            
            (uint256 postRestakeBalance,,,,,) = restakingToken.getStakeInfo(alice);
            assertEq(postRestakeBalance, preRestakeBalance + totalExpectedRewards);
        }
        vm.stopPrank();
    }
    
    function test_MaxRestakes() public {
        uint256 amount = 100 * 1e18;
        
        vm.startPrank(alice);
        restakingToken.deposit(alice, amount);
        
        // Perform maximum allowed restakes
        for(uint256 i = 0; i < 10; i++) {
            vm.warp(block.timestamp + 45 days);
            restakingToken.restake();
        }
        
        // Try one more restake, should revert
        vm.warp(block.timestamp + 45 days);
        vm.expectRevert(SuzakuRestaking.MaxRestakesReached.selector);
        restakingToken.restake();
        vm.stopPrank();
    }
    
    function test_WithdrawAfterRestake(uint256 amount, uint8 restakeCount) public {
        amount = bound(amount, 1e18, 100 * 1e18);
        restakeCount = uint8(bound(restakeCount, 0, 10));
        
        vm.startPrank(alice);
        restakingToken.deposit(alice, amount);
        
        // Perform multiple restakes
        for(uint256 i = 0; i < restakeCount; i++) {
            vm.warp(block.timestamp + 45 days);
            restakingToken.restake();
        }
        
        // Advance time past minimum staking period
        vm.warp(block.timestamp + 31 days);
        
        // Get final balance before withdrawal
        (uint256 finalStakedAmount,,,,, uint256 totalRestaked) = restakingToken.getStakeInfo(alice);
        
        // Withdraw everything
        restakingToken.withdraw(alice, finalStakedAmount);
        
        // Verify complete withdrawal
        (uint256 remainingStake,,,,, uint256 finalTotalRestaked) = restakingToken.getStakeInfo(alice);
        assertEq(remainingStake, 0);
        assertEq(finalTotalRestaked, totalRestaked);
        vm.stopPrank();
    }
    
    function test_MultipleUsersRestaking() public {
        uint256 aliceAmount = 100 * 1e18;
        uint256 bobAmount = 150 * 1e18;
        
        // Alice and Bob deposit
        vm.prank(alice);
        restakingToken.deposit(alice, aliceAmount);
        
        vm.prank(bob);
        restakingToken.deposit(bob, bobAmount);
        
        // Advance time and let both restake
        vm.warp(block.timestamp + 60 days);
        
        vm.prank(alice);
        restakingToken.restake();
        
        vm.prank(bob);
        restakingToken.restake();
        
        // Verify both users' restake counts and rewards
        (uint256 aliceStake, , , , uint256 aliceRestakeCount,) = restakingToken.getStakeInfo(alice);
        (uint256 bobStake, , , , uint256 bobRestakeCount,) = restakingToken.getStakeInfo(bob);
        
        assertTrue(aliceStake > aliceAmount);
        assertTrue(bobStake > bobAmount);
        assertEq(aliceRestakeCount, 1);
        assertEq(bobRestakeCount, 1);
    }
    
    function test_RestakeBeforeMinimumPeriod() public {
        vm.startPrank(alice);
        restakingToken.deposit(alice, 100 * 1e18);
        
        // Try to restake before minimum period
        vm.warp(block.timestamp + 15 days);
        vm.expectRevert(SuzakuRestaking.RestakeNotAvailable.selector);
        restakingToken.restake();
        vm.stopPrank();
    }
} 