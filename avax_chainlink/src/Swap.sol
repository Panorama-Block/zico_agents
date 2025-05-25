// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import "chainlink-brownie-contracts/contracts/src/v0.8/shared/interfaces/AggregatorV3Interface.sol";
import "v2-core/contracts/interfaces/IUniswapV2Factory.sol";
import "v2-core/contracts/interfaces/IUniswapV2Pair.sol";

interface IERC20 {
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
}

contract Swap {
    struct PriceFeedInfo {
        string pair;
        AggregatorV3Interface feed;
    }

    PriceFeedInfo[] public feeds;
    address lastSender;

    constructor() {
        lastSender = msg.sender;
        feeds.push(PriceFeedInfo("AVAX/USD", AggregatorV3Interface(0x0A77230d17318075983913bC2145DB16C7366156)));
        feeds.push(PriceFeedInfo("BTC/USD", AggregatorV3Interface(0x2779D32d5166BAaa2B2b658333bA7e6Ec0C65743)));
        feeds.push(PriceFeedInfo("ETH/USD", AggregatorV3Interface(0x976B3D034E162d8bD72D6b9C989d545b839003b0)));
        feeds.push(PriceFeedInfo("USDC/USD", AggregatorV3Interface(0xF096872672F44d6EBA71458D74fe67F9a77a23B9)));
        feeds.push(PriceFeedInfo("USDT/USD", AggregatorV3Interface(0xEBE676ee90Fe1112671f19b6B7459bC678B67e8a)));
        feeds.push(PriceFeedInfo("DAI/USD", AggregatorV3Interface(0x51D7180edA2260cc4F6e4EebB82FEF5c3c2B8300)));
        feeds.push(PriceFeedInfo("LINK/USD", AggregatorV3Interface(0x49ccd9ca821EfEab2b98c60dC60F518E765EDe9a)));
    }

    function pairFor(address factory, address tokenA, address tokenB) internal pure returns (address pair) {
        (address token0, address token1) = sortTokens(tokenA, tokenB);
        pair = address(uint160(uint256(keccak256(abi.encodePacked(
            hex"ff",
            factory,
            keccak256(abi.encodePacked(token0, token1)),
            hex"96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f" // init code hash UniswapV2
        )))));
    }

    function sortTokens(address tokenA, address tokenB) internal pure returns (address token0, address token1) {
        require(tokenA != tokenB, "Identical addresses");
        (token0, token1) = tokenA < tokenB ? (tokenA, tokenB) : (tokenB, tokenA);
        require(token0 != address(0), "Zero address");
    }

    function getReserves(address factory, address tokenA, address tokenB) internal view returns (uint reserveA, uint reserveB) {
        (address token0,) = sortTokens(tokenA, tokenB);
        address pair = pairFor(factory, tokenA, tokenB);
        (uint reserve0, uint reserve1,) = IUniswapV2Pair(pair).getReserves();
        (reserveA, reserveB) = tokenA == token0 ? (reserve0, reserve1) : (reserve1, reserve0);
    }

    function getPriceInUniswap(address tokenA, address tokenB) external view returns (uint256 price) {
        address factory = 0x740b1c1de25031C31FF4fC9A62f554A55cdC1baD;
        address pair = pairFor(factory, tokenA, tokenB);
        require(pair != address(0), "Pair does not exist");

        (uint reserveA, uint reserveB) = getReserves(factory, tokenA, tokenB);
        require(reserveA > 0 && reserveB > 0, "No reserves");

        price = reserveB * 1e18 / reserveA;
    }

    function getPriceInPangolin(address tokenA, address tokenB) public view returns (uint price) {
        address factory = 0x9Ad6C38BE94206cA50bb0d90783181662f0Cfa10;
        address pair = IUniswapV2Factory(factory).getPair(tokenA, tokenB);
        require(pair != address(0), "Unexistent pair in Pangolin");

        (uint reserve0, uint reserve1, ) = IUniswapV2Pair(pair).getReserves();
        address token0 = IUniswapV2Pair(pair).token0();

        if (tokenA == token0) {
            return (reserve1 * 1e18) / reserve0;
        } else {
            return (reserve0 * 1e18) / reserve1;
        }
    }

    function getMediumPrice (string memory _pair) public view returns(uint) {
        for (uint i = 0; i < feeds.length; i++) {
            if (keccak256(bytes(_pair)) == keccak256(bytes(feeds[i].pair))) {
                (
                , 
                int price,
                ,
                ,
                
            ) = feeds[i].feed.latestRoundData();
            return uint(price);
            }
        }
        revert("Pair not found");
    }

    function makeSwap(string memory _pair, uint amountIn) public returns (string memory, uint amountOut) {
        
        if (lastSender != msg.sender) {
            revert("You didn't send gas to finish this automated swap operation");
        }
        
        uint marketPrice = getMediumPrice(_pair);

        (address tokenA, address tokenB) = getTokenAddresses(_pair);

        uint uniswapPrice = this.getPriceInUniswap(tokenA, tokenB);
        uint pangolinPrice = this.getPriceInPangolin(tokenA, tokenB);

        address factory;
        address pair;
        bool usePangolin;

        if (pangolinPrice < uniswapPrice) {
            if (pangolinPrice <= marketPrice) {
                factory = 0x9Ad6C38BE94206cA50bb0d90783181662f0Cfa10;
                pair = IUniswapV2Factory(factory).getPair(tokenA, tokenB);
                usePangolin = true;
            } else {
                revert("Not ideal: price in Pangolin and Uniswap is above market average.");
            }
        } else {
            if (uniswapPrice <= marketPrice) {
                factory = 0x740b1c1de25031C31FF4fC9A62f554A55cdC1baD;
                pair = pairFor(factory, tokenA, tokenB);
                usePangolin = false;
            } else {
                revert("Not ideal: price in Pangolin and Uniswap is above market average.");
            }
        }

        require(pair != address(0), "Pair not found");
        require(IERC20(tokenA).transferFrom(msg.sender, address(this), amountIn), "TransferFrom failed");
        require(IERC20(tokenA).approve(pair, amountIn), "Approve failed");

        (uint reserveA, uint reserveB) = getReserves(factory, tokenA, tokenB);
        require(reserveA > 0 && reserveB > 0, "No reserves");

        amountOut = ((amountIn * 997) * reserveB) / (reserveA * 1000 + (amountIn * 997));

        require(IERC20(tokenA).transfer(pair, amountIn), "Transfer to pair failed");

        address token0 = IUniswapV2Pair(pair).token0();

        (uint amount0Out, uint amount1Out) = tokenA == token0 ? (uint(0), amountOut) : (amountOut, uint(0));

        IUniswapV2Pair(pair).swap(amount0Out, amount1Out, msg.sender, new bytes(0));
        return (usePangolin ? "Pangolin" : "Uniswap", amountOut);
    }

    function getTokenAddresses(string memory _pair) public pure returns (address tokenA, address tokenB) {
        
        bytes32 pairHash = keccak256(bytes(_pair));
    
        if (pairHash == keccak256(bytes("AVAX/USD"))) {
            return (0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7, 0xA7D7079b0FEaD91F3e65f86E8915Cb59c1a4C664); // AVAX, USDC
        } else if (pairHash == keccak256(bytes("BTC/USD"))) {
            return (0x50b7545627a5162F82A992c33b87aDc75187B218, 0xA7D7079b0FEaD91F3e65f86E8915Cb59c1a4C664); // WBTC, USDC
        } else if (pairHash == keccak256(bytes("ETH/USD"))) {
            return (0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB, 0xA7D7079b0FEaD91F3e65f86E8915Cb59c1a4C664); // WETH, USDC
        } else if (pairHash == keccak256(bytes("USDC/USD"))) {
            return (0xA7D7079b0FEaD91F3e65f86E8915Cb59c1a4C664, 0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E); // USDC, USD (simulado com USDC.e)
        } else if (pairHash == keccak256(bytes("USDT/USD"))) {
            return (0xc7198437980c041c805A1EDcbA50c1Ce5db95118, 0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E); // USDT, USD
        } else if (pairHash == keccak256(bytes("DAI/USD"))) {
            return (0xd586E7F844cEa2F87f50152665BCbc2C279D8d70, 0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E); // DAI, USD
        } else if (pairHash == keccak256(bytes("LINK/USD"))) {
            return (0x5947BB275c521040051D82396192181b413227A3, 0xA7D7079b0FEaD91F3e65f86E8915Cb59c1a4C664); // LINK, USDC
        }else {
            revert("Unknown Pair");
        }
    }

    receive() external payable {
        lastSender = msg.sender;
    }

    fallback() external payable {}

    function balance() public view returns (uint) {
        return address(this).balance;
    }
}
