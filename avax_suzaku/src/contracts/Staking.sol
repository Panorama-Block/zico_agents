// SPDX-License-Identifier: MIT
pragma solidity 0.8.25;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {Factory} from "./Factory.sol";
import {Permit2Lib} from "./libraries/Permit2Lib.sol";
import {IDefaultCollateral} from "src/interfaces/defaultCollateral/IDefaultCollateral.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IERC20Permit} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Permit.sol";
import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";

contract SuzakuStaking is Factory, Initializable {
    using Permit2Lib for IERC20;
    using SafeERC20 for IERC20;
    
    IERC20 public suzakuToken;
    
    struct StakeInfo {
        uint256 amount;
        uint256 startTime;
        uint256 lastRewardCalculation;
        bool isStaking;
    }
    
    mapping(address => StakeInfo) public stakes;
    
    uint256 public rewardRate = 500; 
    uint256 public constant BASIS_POINTS = 10000;
    
    uint256 public constant MINIMUM_STAKING_PERIOD = 30 days;
    
    event Staked(address indexed depositor, address indexed recipient, uint256 amount);
    event Withdrawn(address indexed withdrawer, address indexed recipient, uint256 amount);
    event RewardPaid(address indexed user, uint256 reward);
    
    error AlreadyStaking();
    error NotStaking();
    error MinimumPeriodNotMet();
    error InsufficientBalance();
    error ZeroAmount();
    error InvalidToken();
    error RewardTransferFailed();
    error InsufficientWithdraw();
    error InsufficientDeposit();
    
    constructor(address _suzakuToken) {
        _disableInitializers();
    }

    function initialize(address _suzakuToken) external initializer {
        if (_suzakuToken == address(0)) revert InvalidToken();
        suzakuToken = IERC20(_suzakuToken);
    }
    
    function deposit(address recipient, uint256 amount) public checkEntity(msg.sender) returns (uint256) {
        if (amount == 0) revert InsufficientDeposit();
        if (stakes[recipient].isStaking) revert AlreadyStaking();
        
        if (recipient == msg.sender) {
            _payRewards();
        }
        
        uint256 balanceBefore = suzakuToken.balanceOf(address(this));
        
        suzakuToken.transferFrom2(msg.sender, address(this), amount);
        
        amount = suzakuToken.balanceOf(address(this)) - balanceBefore;
        
        if (amount == 0) revert InsufficientDeposit();
        
        stakes[recipient] = StakeInfo({
            amount: amount,
            startTime: block.timestamp,
            lastRewardCalculation: block.timestamp,
            isStaking: true
        });
        
        emit Staked(msg.sender, recipient, amount);
        
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
        }
        
        suzakuToken.safeTransfer(recipient, amount);
        
        emit Withdrawn(msg.sender, recipient, amount);
    }
    
    function calculatePendingRewards(address _user) public view returns (uint256) {
        StakeInfo memory userStake = stakes[_user];
        if (!userStake.isStaking || userStake.amount == 0) return 0;
        
        uint256 timeElapsed = block.timestamp - userStake.lastRewardCalculation;
        return (userStake.amount * rewardRate * timeElapsed) / (BASIS_POINTS * 365 days);
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

    function getStakeAmount(address _user) external view returns (uint256) {
        return stakes[_user].amount;
    }
    
    function getStakeStartTime(address _user) external view returns (uint256) {
        return stakes[_user].startTime;
    }

    function getStakeInfo(address _user) external view returns (
        uint256 amount,
        uint256 startTime,
        uint256 lastRewardCalculation,
        bool isStaking
    ) {
        StakeInfo memory userStake = stakes[_user];
        return (
            userStake.amount,
            userStake.startTime,
            userStake.lastRewardCalculation,
            userStake.isStaking
        );
    }
}