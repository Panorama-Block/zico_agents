// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {Test} from "forge-std/Test.sol";
import {StakingFactory} from "src/contracts/StakingFactory.sol";
import {SuzakuStaking} from "src/contracts/Staking.sol";
import {MockERC20} from "./mocks/MockERC20.sol";
import {FeeOnTransferToken} from "./mocks/FeeOnTransferToken.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";


contract StakingTest is Test {
    address public constant COLLATERAL_FACTORY = 0xE5296638Aa86BD4175d802A210E158688e41A93c;

    address[] public collateralTokens;

    mapping(string => address) public collateralBySymbol;

    address public constant DEAD = 0x000000000000000000000000000000000000dEaD;
    
    uint256 public alicePrivateKey;
    uint256 public bobPrivateKey;
    address public alice;
    address public bob;
    
    StakingFactory public stakingFactory;
    SuzakuStaking public stakingToken;
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
        
        // Deploy factory and staking contract
        stakingFactory = new StakingFactory();
        stakingToken = SuzakuStaking(stakingFactory.create(address(token)));
        
        // Transfer tokens to test accounts
        token.transfer(alice, 100 * 1e18);
        token.transfer(bob, 100 * 1e18);
        feeOnTransferToken.transfer(alice, 100 * 1e18);
        feeOnTransferToken.transfer(bob, 100 * 1e18);
        
        // Approve tokens
        vm.startPrank(alice);
        token.approve(address(stakingToken), type(uint256).max);
        feeOnTransferToken.approve(address(stakingToken), type(uint256).max);
        vm.stopPrank();
        
        vm.startPrank(bob);
        token.approve(address(stakingToken), type(uint256).max);
        feeOnTransferToken.approve(address(stakingToken), type(uint256).max);
        vm.stopPrank();

        collateralTokens.push(0xE3C983013B8c5830D866F550a28fD7Ed4393d5B7); // sAVAX
        collateralTokens.push(0x203E9101e09dc87ce391542E705a07522d19dF0d); // BTC.b
        collateralTokens.push(0xa53E127Bfd9C4d0310858D9D5Fcdf1D2617d4C41); // AUSD
        collateralTokens.push(0x1D8bd363922465246A91B7699e7B32BAbf5FEF62); // SolvBTC
        collateralTokens.push(0x8F1dea444380A2DDC5e6669f508d235401CaEE5F); // COQ

        collateralBySymbol["sAVAX"] = collateralTokens[0];
        collateralBySymbol["BTC.b"] = collateralTokens[1];
        collateralBySymbol["AUSD"] = collateralTokens[2];
        collateralBySymbol["SolvBTC"] = collateralTokens[3];
        collateralBySymbol["COQ"] = collateralTokens[4];
    }

    function test_CollateralTokenIsERC20() public {
        for (uint256 i = 0; i < collateralTokens.length; i++) {
            address tokenAddr = collateralTokens[i];
            uint256 balance = IERC20(tokenAddr).balanceOf(address(this));
            assertEq(balance, 0, "Initial balance should be 0");
        }
    }

    
    function test_Deposit(uint256 amount) public {
        amount = bound(amount, 1, 50 * 1e18);
        
        vm.startPrank(alice);
        uint256 depositedAmount = stakingToken.deposit(alice, amount);
        vm.stopPrank();
        
        assertEq(depositedAmount, amount);
        (uint256 stakedAmount, uint256 startTime, ,) = stakingToken.getStakeInfo(alice);
        assertEq(stakedAmount, amount);
        assertEq(startTime, block.timestamp);
    }
    
    function test_DepositWithFeeOnTransfer(uint256 amount) public {
        amount = bound(amount, 2, 50 * 1e18);
        
        vm.startPrank(alice);
        uint256 depositedAmount = stakingToken.deposit(alice, amount);
        vm.stopPrank();
        
        assertEq(depositedAmount, amount - 1); // Fee on transfer takes 1 token
    }
    
    function test_DepositRevertInsufficientDeposit() public {
        vm.startPrank(alice);
        vm.expectRevert(abi.encodeWithSelector(SuzakuStaking.InsufficientDeposit.selector));
        stakingToken.deposit(alice, 0);
        vm.stopPrank();
    }
    
    function test_DepositOnBehalfOf(uint256 amount) public {
        amount = bound(amount, 1, 50 * 1e18);
        
        vm.startPrank(alice);
        uint256 depositedAmount = stakingToken.deposit(bob, amount);
        vm.stopPrank();
        
        assertEq(depositedAmount, amount);
        (uint256 aliceStake, , ,) = stakingToken.getStakeInfo(alice);
        (uint256 bobStake, , ,) = stakingToken.getStakeInfo(bob);
        assertEq(aliceStake, 0);
        assertEq(bobStake, amount);
    }
    
    function test_Withdraw(uint256 amount) public {
        amount = bound(amount, 1, 50 * 1e18);
        
        // First deposit
        vm.startPrank(alice);
        stakingToken.deposit(alice, amount);
        
        // Advance time past minimum staking period
        vm.warp(block.timestamp + 31 days);
        
        uint256 balanceBefore = token.balanceOf(alice);
        stakingToken.withdraw(alice, amount);
        vm.stopPrank();
        
        assertEq(token.balanceOf(alice) - balanceBefore, amount);
        (uint256 stakedAmount, , ,) = stakingToken.getStakeInfo(alice);
        assertEq(stakedAmount, 0);
    }
    
    function test_WithdrawRevertInsufficientWithdraw() public {
        vm.startPrank(alice);
        vm.expectRevert(abi.encodeWithSelector(SuzakuStaking.InsufficientWithdraw.selector));
        stakingToken.withdraw(alice, 0);
        vm.stopPrank();
    }
    
    function test_WithdrawRevertMinimumPeriodNotMet(uint256 amount) public {
        amount = bound(amount, 1, 50 * 1e18);
        
        vm.startPrank(alice);
        stakingToken.deposit(alice, amount);
        
        vm.expectRevert(abi.encodeWithSelector(SuzakuStaking.MinimumPeriodNotMet.selector));
        stakingToken.withdraw(alice, amount);
        vm.stopPrank();
    }
    
    function test_WithdrawPartial(uint256 amount1, uint256 amount2) public {
        amount1 = bound(amount1, 2, 50 * 1e18);
        amount2 = bound(amount2, 1, amount1 - 1);
        
        vm.startPrank(alice);
        stakingToken.deposit(alice, amount1);
        
        // Advance time past minimum staking period
        vm.warp(block.timestamp + 31 days);
        
        uint256 balanceBefore = token.balanceOf(alice);
        stakingToken.withdraw(alice, amount2);
        vm.stopPrank();
        
        assertEq(token.balanceOf(alice) - balanceBefore, amount2);
        (uint256 stakedAmount, , ,) = stakingToken.getStakeInfo(alice);
        assertEq(stakedAmount, amount1 - amount2);
    }
    
    function test_Rewards(uint256 amount, uint256 timeElapsed) public {
        amount = bound(amount, 1e18, 50 * 1e18);
        timeElapsed = bound(timeElapsed, 31 days, 365 days);
        
        vm.startPrank(alice);
        stakingToken.deposit(alice, amount);
        
        // Advance time
        vm.warp(block.timestamp + timeElapsed);
        
        uint256 expectedReward = (amount * 500 * timeElapsed) / (10000 * 365 days);
        uint256 pendingRewards = stakingToken.calculatePendingRewards(alice);
        
        assertEq(pendingRewards, expectedReward);
        
        uint256 balanceBefore = token.balanceOf(alice);
        stakingToken.claimRewards();
        
        assertEq(token.balanceOf(alice) - balanceBefore, expectedReward);
        vm.stopPrank();
    }
    
    function test_MultipleUsers(uint256 amount1, uint256 amount2, uint256 timeElapsed) public {
        amount1 = bound(amount1, 1e18, 50 * 1e18);
        amount2 = bound(amount2, 1e18, 50 * 1e18);
        timeElapsed = bound(timeElapsed, 31 days, 365 days);
        
        vm.startPrank(alice);
        stakingToken.deposit(alice, amount1);
        vm.stopPrank();
        
        vm.startPrank(bob);
        stakingToken.deposit(bob, amount2);
        vm.stopPrank();
        
        // Advance time
        vm.warp(block.timestamp + timeElapsed);
        
        uint256 expectedReward1 = (amount1 * 500 * timeElapsed) / (10000 * 365 days);
        uint256 expectedReward2 = (amount2 * 500 * timeElapsed) / (10000 * 365 days);
        
        assertEq(stakingToken.calculatePendingRewards(alice), expectedReward1);
        assertEq(stakingToken.calculatePendingRewards(bob), expectedReward2);
    }
    
    function test_UpdateRewardRate() public {
        uint256 newRate = 1000; // 10%
        
        vm.startPrank(alice);
        stakingToken.setRewardRate(newRate);
        assertEq(stakingToken.rewardRate(), newRate);
        vm.stopPrank();
    }
    
    function test_UpdateRewardRateRevertTooHigh() public {
        uint256 newRate = 1001; // > 10%
        
        vm.startPrank(alice);
        vm.expectRevert("Rate too high");
        stakingToken.setRewardRate(newRate);
        vm.stopPrank();
    }
} 