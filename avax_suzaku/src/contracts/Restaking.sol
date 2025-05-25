// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Factory} from "./Factory.sol";
import {Permit2Lib} from "./libraries/Permit2Lib.sol";
import {IDefaultCollateral} from "src/interfaces/defaultCollateral/IDefaultCollateral.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IERC20Permit} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Permit.sol";

contract SuzakuRestaking is Factory {
    using Permit2Lib for IERC20;
    using SafeERC20 for IERC20;
    
    IERC20 public suzakuToken;
    
    struct StakeInfo {
        uint256 amount;
        uint256 startTime;
        uint256 lastRewardCalculation;
        bool isStaking;
        uint256 restakeCount;
        uint256 totalRestaked;
    }
    
    mapping(address => StakeInfo) public stakes;
    
    uint256 public rewardRate = 500;
    uint256 public constant BASIS_POINTS = 10000;
    uint256 public constant MINIMUM_STAKING_PERIOD = 30 days;
    uint256 public constant RESTAKE_BONUS_RATE = 50;
    uint256 public constant MAX_RESTAKES = 10;
    uint256 public limit;
    
    event Deposit(address indexed depositor, address indexed recipient, uint256 amount);
    event Withdraw(address indexed withdrawer, address indexed recipient, uint256 amount);
    event RewardPaid(address indexed user, uint256 reward);
    event Restaked(address indexed user, uint256 amount, uint256 restakeCount);
    
    error NotLimitIncreaser();
    error InsufficientDeposit();
    error ExceedsLimit();
    error InsufficientWithdraw();
    error NotStaking();
    error MinimumPeriodNotMet();
    error InsufficientBalance();
    error InvalidToken();
    error MaxRestakesReached();
    error RestakeNotAvailable();
    
    constructor(address _suzakuToken) {
        if (_suzakuToken == address(0)) revert InvalidToken();
        suzakuToken = IERC20(_suzakuToken);
    }

    function deposit(address recipient, uint256 amount) public checkEntity(msg.sender) returns (uint256) {
        if (amount == 0) revert InsufficientDeposit();
        if (stakes[recipient].isStaking) revert NotStaking();
        
        if (recipient == msg.sender) {
            _payRewards();
        }
        
        uint256 balanceBefore = suzakuToken.balanceOf(address(this));
        suzakuToken.transferFrom2(msg.sender, address(this), amount);
        amount = suzakuToken.balanceOf(address(this)) - balanceBefore;
        
        if (amount == 0) revert InsufficientDeposit();
        if (totalSupply() + amount > limit) revert ExceedsLimit();
        
        stakes[recipient] = StakeInfo({
            amount: amount,
            startTime: block.timestamp,
            lastRewardCalculation: block.timestamp,
            isStaking: true,
            restakeCount: 0,
            totalRestaked: 0
        });
        
        emit Deposit(msg.sender, recipient, amount);
        return amount;
    }

    function deposit(
        address recipient,
        uint256 amount,
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external returns (uint256) {
        suzakuToken.tryPermit2(msg.sender, address(this), amount, deadline, v, r, s);
        return deposit(recipient, amount);
    }

    function restake() external checkEntity(msg.sender) returns (uint256) {
        StakeInfo storage userStake = stakes[msg.sender];
        if (!userStake.isStaking) revert NotStaking();
        if (userStake.restakeCount >= MAX_RESTAKES) revert MaxRestakesReached();
        if (block.timestamp < userStake.startTime + MINIMUM_STAKING_PERIOD) revert MinimumPeriodNotMet();
        
        uint256 rewards = calculatePendingRewards(msg.sender);
        uint256 restakeBonus = (userStake.amount * RESTAKE_BONUS_RATE * (userStake.restakeCount + 1)) / BASIS_POINTS;
        
        if (totalSupply() + rewards + restakeBonus > limit) revert ExceedsLimit();
        
        userStake.amount += rewards + restakeBonus;
        userStake.startTime = block.timestamp;
        userStake.lastRewardCalculation = block.timestamp;
        userStake.restakeCount += 1;
        userStake.totalRestaked += rewards + restakeBonus;
        
        emit Restaked(msg.sender, rewards + restakeBonus, userStake.restakeCount);
        return rewards + restakeBonus;
    }

    function withdraw(address recipient, uint256 amount) external checkEntity(msg.sender) {
        if (amount == 0) revert InsufficientWithdraw();
        
        StakeInfo storage userStake = stakes[msg.sender];
        if (!userStake.isStaking) revert NotStaking();
        if (userStake.amount < amount) revert InsufficientBalance();
        if (block.timestamp < userStake.startTime + MINIMUM_STAKING_PERIOD) revert MinimumPeriodNotMet();
        
        _payRewards();
        
        userStake.amount -= amount;
        if (userStake.amount == 0) {
            userStake.isStaking = false;
            userStake.restakeCount = 0;
            userStake.totalRestaked = 0;
        }
        
        suzakuToken.safeTransfer(recipient, amount);
        emit Withdraw(msg.sender, recipient, amount);
    }

    function calculatePendingRewards(address _user) public view returns (uint256) {
        StakeInfo memory userStake = stakes[_user];
        if (!userStake.isStaking || userStake.amount == 0) return 0;
        
        uint256 timeElapsed = block.timestamp - userStake.lastRewardCalculation;
        uint256 baseReward = (userStake.amount * rewardRate * timeElapsed) / (BASIS_POINTS * 365 days);
        uint256 restakeBonus = (baseReward * RESTAKE_BONUS_RATE * userStake.restakeCount) / BASIS_POINTS;
        
        return baseReward + restakeBonus;
    }

    function _payRewards() internal {
        uint256 rewards = calculatePendingRewards(msg.sender);
        if (rewards > 0) {
            suzakuToken.safeTransfer(msg.sender, rewards);
            stakes[msg.sender].lastRewardCalculation = block.timestamp;
            emit RewardPaid(msg.sender, rewards);
        }
    }

    function claimRewards() external checkEntity(msg.sender) {
        if (!stakes[msg.sender].isStaking) revert NotStaking();
        _payRewards();
    }

    function setRewardRate(uint256 _newRate) external {
        require(_newRate <= 1000, "Rate too high");
        rewardRate = _newRate;
    }

    function getStakeInfo(address _user) external view returns (
        uint256 amount,
        uint256 startTime,
        uint256 lastRewardCalculation,
        bool isStaking,
        uint256 restakeCount,
        uint256 totalRestaked
    ) {
        StakeInfo memory userStake = stakes[_user];
        return (
            userStake.amount,
            userStake.startTime,
            userStake.lastRewardCalculation,
            userStake.isStaking,
            userStake.restakeCount,
            userStake.totalRestaked
        );
    }

    function getRestakeBonus(address _user) external view returns (uint256) {
        StakeInfo memory userStake = stakes[_user];
        return (userStake.amount * RESTAKE_BONUS_RATE * userStake.restakeCount) / BASIS_POINTS;
    }

    function totalSupply() public view returns (uint256) {
        return suzakuToken.balanceOf(address(this));
    }
}