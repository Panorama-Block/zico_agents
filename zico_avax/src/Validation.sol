// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

contract Validation {
    address public owner;
    uint public taxRate; 

    constructor(uint _taxRate) {
        owner = msg.sender;
        taxRate = _taxRate;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Not authorized");
        _;
    }

    function setTaxRate(uint _taxRate) external onlyOwner {
        require(_taxRate <= 100, "Invalid tax rate");
        taxRate = _taxRate;
    }

    function calculateValue(uint amount) public view returns (uint) {
        return (amount * taxRate) / 100;
    }

    function payAndValidate() external payable returns (uint rest) {
        require(msg.value > 0, "No AVAX sent");

        uint tax = calculateValue(msg.value);
        rest = msg.value - tax;

        payable(owner).transfer(tax);
        payable(msg.sender).transfer(rest);
    }

    function withdraw() external onlyOwner {
        payable(owner).transfer(address(this).balance);
    }
}
